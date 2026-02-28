"""
ModelToll Proxy Gateway
------------------------
The core ASGI request handler that intercepts outbound AI API calls,
runs them through the scrubber + router pipeline, and forwards them
to the approved model endpoint.

Supported intercept modes:
  * Transparent HTTP proxy  -- client sets Host header / uses CONNECT
  * API gateway mode        -- client sends requests directly to ModelToll

Flow per request:
  1. Hard-block check (policy violations -> 403)
  2. Passthrough check (unmonitored hosts -> forward as-is)
  3. Parse body -> extract model name + messages
  4. Scrub PII and proprietary data
  5. Route to approved cheaper model
  6. Forward to approved endpoint (streaming or buffered)
  7. Record audit log entry asynchronously
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncGenerator
from typing import Any

import httpx
import structlog
from fastapi import Request, Response
from fastapi.responses import StreamingResponse

from src.audit.logger import AuditLogger
from src.audit.models import RequestAction
from src.config.settings import Settings
from src.router.model_router import ModelRouter
from src.scrubber.engine import ScrubberEngine

log = structlog.get_logger(__name__)


class ProxyGateway:
    """
    Main gateway that wires scrubber + router + audit together.

    Attach to a FastAPI app via the route handlers in src/proxy/routes.py.
    """

    def __init__(
        self,
        settings: Settings,
        scrubber: ScrubberEngine,
        router: ModelRouter,
        audit: AuditLogger,
    ) -> None:
        self._settings = settings
        self._scrubber = scrubber
        self._router = router
        self._audit = audit
        self._client = httpx.AsyncClient(
            timeout=settings.proxy_timeout_seconds,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=200, max_keepalive_connections=50),
        )

    async def close(self) -> None:
        await self._client.aclose()

    # ── Main entry point ─────────────────────────────────────────────────────────

    async def handle(self, request: Request, tenant_id: str = "default") -> Response:
        """Handle an intercepted AI API request end-to-end."""
        t_start = time.monotonic()

        # 1. Parse body
        try:
            body = await _read_body(request, max_mb=self._settings.max_body_size_mb)
        except ValueError as exc:
            return Response(content=str(exc), status_code=413)

        payload = _parse_json_safe(body)
        original_host = _extract_host(request)
        original_model = _extract_model(payload)
        original_endpoint = str(request.url)

        # 2. Hard-block check (explicit policy violations)
        if original_host in self._settings.hard_blocked_hosts_set:
            log.warning("request_hard_blocked", host=original_host, tenant=tenant_id)
            entry = self._audit.build_entry(
                tenant_id=tenant_id,
                original_host=original_host,
                action=RequestAction.BLOCKED,
                original_model=original_model,
                original_endpoint=original_endpoint,
                ip_address=_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                latency_ms=_elapsed_ms(t_start),
            )
            self._audit.record(entry)
            return Response(
                content='{"error":"This AI provider is blocked by company policy."}',
                status_code=403,
                media_type="application/json",
            )

        # 3. Passthrough: if host is not monitored, forward as-is
        if original_host not in self._settings.monitored_hosts_set:
            log.info("request_passthrough", host=original_host, tenant=tenant_id)
            entry = self._audit.build_entry(
                tenant_id=tenant_id,
                original_host=original_host,
                action=RequestAction.PASSTHROUGH,
                original_model=original_model,
                original_endpoint=original_endpoint,
                ip_address=_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                latency_ms=_elapsed_ms(t_start),
            )
            self._audit.record(entry)
            target_url = f"https://{original_host}{request.url.path}"
            if request.url.query:
                target_url += f"?{request.url.query}"
            try:
                upstream = await self._client.request(
                    method=request.method,
                    url=target_url,
                    content=body,
                    headers=_build_forward_headers(request, self._settings),
                )
                return Response(
                    content=upstream.content,
                    status_code=upstream.status_code,
                    headers={k: v for k, v in upstream.headers.items()
                             if k.lower() not in {"transfer-encoding", "connection"}},
                    media_type=upstream.headers.get("content-type"),
                )
            except httpx.RequestError as exc:
                return Response(
                    content=f'{{"error":"Upstream error: {exc}"}}',
                    status_code=502,
                    media_type="application/json",
                )

        # 4. Scrub PII and proprietary data
        messages = payload.get("messages", []) if payload else []
        scrubbed_messages, scrub_result = self._scrubber.scrub_messages(messages)

        if scrub_result.was_modified and payload is not None:
            payload = {**payload, "messages": scrubbed_messages}
            body = _serialize_json(payload)

        # 5. Route to approved cheaper model
        decision = self._router.route(original_model or "unknown")
        if payload is not None:
            payload = {**payload, "model": decision.target_model}
            body = _serialize_json(payload)

        # 6. Estimate cost (pre-response; updated with actual tokens after)
        input_text = " ".join(
            m.get("content", "") for m in messages if isinstance(m.get("content"), str)
        )
        cost_estimate = self._router.estimate_cost(
            decision, input_text=input_text, output_tokens=500
        )

        # 7. Forward (streaming or buffered)
        forward_headers = _build_forward_headers(request, self._settings)
        target_url = decision.target_endpoint
        is_streaming = bool(payload and payload.get("stream", False))

        if is_streaming:
            return await self._handle_streaming(
                request=request,
                body=body,
                target_url=target_url,
                forward_headers=forward_headers,
                tenant_id=tenant_id,
                original_host=original_host,
                original_model=original_model,
                original_endpoint=original_endpoint,
                decision=decision,
                scrub_result=scrub_result,
                cost_estimate=cost_estimate,
                t_start=t_start,
            )

        # Buffered
        try:
            upstream = await self._client.post(
                target_url,
                content=body,
                headers=forward_headers,
            )
        except httpx.RequestError as exc:
            log.error("upstream_request_failed", error=str(exc), target=target_url)
            return Response(
                content=f'{{"error":"Upstream request failed: {exc}"}}',
                status_code=502,
                media_type="application/json",
            )

        latency_ms = _elapsed_ms(t_start)
        upstream_body = upstream.content
        upstream_json = _parse_json_safe(upstream_body)
        output_tokens = _extract_output_tokens(upstream_json) or 500

        cost_estimate = self._router.estimate_cost(
            decision,
            input_tokens=cost_estimate.input_tokens,
            output_tokens=output_tokens,
        )

        # 8. Audit
        entry = self._audit.build_entry(
            tenant_id=tenant_id,
            original_host=original_host,
            action=RequestAction.FORWARDED,
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            original_model=original_model,
            original_endpoint=original_endpoint,
            input_tokens=cost_estimate.input_tokens,
            scrubber_triggered=scrub_result.was_modified,
            scrubber_detection_count=scrub_result.detection_count,
            scrubber_entity_types=scrub_result.entity_types_found if scrub_result.was_modified else None,
            routed_model=decision.target_model,
            routed_provider=decision.target_provider,
            route_reason=decision.reason,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            response_status=upstream.status_code,
            source_cost_usd=cost_estimate.source_cost_usd,
            target_cost_usd=cost_estimate.target_cost_usd,
            savings_usd=cost_estimate.savings_usd,
            savings_percent=cost_estimate.savings_percent,
        )
        self._audit.record(entry)

        log.info(
            "request_handled",
            tenant=tenant_id,
            original_model=original_model,
            routed_model=decision.target_model,
            scrubbed=scrub_result.was_modified,
            savings_usd=round(cost_estimate.savings_usd, 6),
            latency_ms=latency_ms,
        )

        response_headers = {
            k: v for k, v in upstream.headers.items()
            if k.lower() not in {"content-encoding", "transfer-encoding", "connection"}
        }
        response_headers["x-modeltoll-routed-model"] = decision.target_model
        response_headers["x-modeltoll-savings-usd"] = str(round(cost_estimate.savings_usd, 6))
        response_headers["x-modeltoll-scrubbed"] = "1" if scrub_result.was_modified else "0"

        return Response(
            content=upstream_body,
            status_code=upstream.status_code,
            headers=response_headers,
            media_type=upstream.headers.get("content-type", "application/json"),
        )

    # ── Streaming handler ────────────────────────────────────────────────────────

    async def _handle_streaming(
        self,
        *,
        request: Request,
        body: bytes,
        target_url: str,
        forward_headers: dict[str, str],
        tenant_id: str,
        original_host: str,
        original_model: str | None,
        original_endpoint: str,
        decision: Any,
        scrub_result: Any,
        cost_estimate: Any,
        t_start: float,
    ) -> StreamingResponse:
        """Forward an SSE streaming request and audit once the stream closes."""

        audit_ref: dict[str, Any] = {"output_tokens": 0, "latency_ms": 0, "status": 200}

        async def _stream_generator() -> AsyncGenerator[bytes, None]:
            output_tokens = 0
            try:
                async with self._client.stream(
                    "POST",
                    target_url,
                    content=body,
                    headers=forward_headers,
                ) as upstream_stream:
                    audit_ref["status"] = upstream_stream.status_code
                    async for chunk in upstream_stream.aiter_bytes():
                        yield chunk
                        # Extract token usage from OpenAI SSE chunks
                        try:
                            text = chunk.decode("utf-8", errors="ignore")
                            for line in text.splitlines():
                                if line.startswith("data: ") and line != "data: [DONE]":
                                    data = json.loads(line[6:])
                                    usage = data.get("usage") or {}
                                    if usage.get("completion_tokens"):
                                        output_tokens = int(usage["completion_tokens"])
                        except Exception:
                            pass
            except httpx.RequestError as exc:
                log.error("streaming_upstream_failed", error=str(exc))
                yield b'data: {"error":"Upstream stream failed"}\n\ndata: [DONE]\n\n'
            finally:
                audit_ref["output_tokens"] = output_tokens or 300
                audit_ref["latency_ms"] = _elapsed_ms(t_start)
                final_cost = self._router.estimate_cost(
                    decision,
                    input_tokens=cost_estimate.input_tokens,
                    output_tokens=audit_ref["output_tokens"],
                )
                entry = self._audit.build_entry(
                    tenant_id=tenant_id,
                    original_host=original_host,
                    action=RequestAction.FORWARDED,
                    ip_address=_client_ip(request),
                    user_agent=request.headers.get("user-agent"),
                    original_model=original_model,
                    original_endpoint=original_endpoint,
                    input_tokens=cost_estimate.input_tokens,
                    scrubber_triggered=scrub_result.was_modified,
                    scrubber_detection_count=scrub_result.detection_count,
                    scrubber_entity_types=scrub_result.entity_types_found if scrub_result.was_modified else None,
                    routed_model=decision.target_model,
                    routed_provider=decision.target_provider,
                    route_reason=decision.reason,
                    output_tokens=audit_ref["output_tokens"],
                    latency_ms=audit_ref["latency_ms"],
                    response_status=audit_ref["status"],
                    source_cost_usd=final_cost.source_cost_usd,
                    target_cost_usd=final_cost.target_cost_usd,
                    savings_usd=final_cost.savings_usd,
                    savings_percent=final_cost.savings_percent,
                    extra={"streaming": True},
                )
                self._audit.record(entry)

        return StreamingResponse(
            _stream_generator(),
            media_type="text/event-stream",
            headers={
                "x-modeltoll-routed-model": decision.target_model,
                "x-modeltoll-scrubbed": "1" if scrub_result.was_modified else "0",
                "cache-control": "no-cache",
                "connection": "keep-alive",
            },
        )


# ── Helpers ──────────────────────────────────────────────────────────────────────

async def _read_body(request: Request, max_mb: int) -> bytes:
    body = await request.body()
    if len(body) > max_mb * 1024 * 1024:
        raise ValueError(f"Request body exceeds {max_mb}MB limit")
    return body


def _parse_json_safe(data: bytes | str) -> dict[str, Any] | None:
    if not data:
        return None
    try:
        return json.loads(data)
    except Exception:
        return None


def _serialize_json(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False).encode()


def _extract_host(request: Request) -> str:
    host = request.headers.get("host", "")
    return host.split(":")[0].lower()


def _extract_model(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    return payload.get("model")


def _extract_output_tokens(payload: dict[str, Any] | None) -> int | None:
    if not payload:
        return None
    usage = payload.get("usage", {})
    if usage:
        return usage.get("completion_tokens") or usage.get("output_tokens")
    return None


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _elapsed_ms(t_start: float) -> int:
    return int((time.monotonic() - t_start) * 1000)


def _build_forward_headers(request: Request, settings: Settings) -> dict[str, str]:
    """Build headers for the upstream (approved model) request."""
    headers: dict[str, str] = {}
    for name in ("authorization", "x-api-key", "anthropic-version", "openai-organization"):
        val = request.headers.get(name)
        if val:
            headers[name] = val
    headers["content-type"] = "application/json"
    headers["user-agent"] = f"ModelToll/{settings.app_version}"
    headers["accept"] = "application/json, text/event-stream"
    return headers
