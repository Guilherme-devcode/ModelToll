"""
ModelToll Proxy Gateway
────────────────────────
The core ASGI request handler that intercepts outbound AI API calls,
runs them through the scrubber + router pipeline, and forwards them
to the approved model endpoint.

Supported intercept modes:
  • Transparent HTTP proxy  — client sets Host header / uses CONNECT
  • API gateway mode        — client sends requests directly to ModelToll

Flow per request:
  1. Detect AI destination (host matching)
  2. Parse body → extract model name + messages
  3. Scrub PII and proprietary data
  4. Route to approved cheaper model
  5. Forward to approved endpoint with company API key
  6. Stream response back to client
  7. Record audit log entry asynchronously
"""

from __future__ import annotations

import time
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

# AI provider hosts that are always intercepted
_AI_HOSTS = {
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "api.cohere.ai",
    "api.mistral.ai",
    "api.together.xyz",
    "api.groq.com",
    "api.perplexity.ai",
    "api-inference.huggingface.co",
}


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

    # ── Main entry point ───────────────────────────────────────────────────────

    async def handle(self, request: Request, tenant_id: str = "default") -> Response:
        """Handle an intercepted AI API request end-to-end."""
        t_start = time.monotonic()

        # ── 1. Parse body ──────────────────────────────────────────────────────
        try:
            body = await _read_body(request, max_mb=self._settings.max_body_size_mb)
        except ValueError as exc:
            return Response(content=str(exc), status_code=413)

        payload = _parse_json_safe(body)
        original_host = _extract_host(request)
        original_model = _extract_model(payload)
        original_endpoint = str(request.url)

        # ── 2. Block check ─────────────────────────────────────────────────────
        if original_host in self._settings.blocked_hosts_set:
            log.warning("request_blocked", host=original_host, tenant=tenant_id)
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
                content='{"error":"This AI provider is not approved. ModelToll has blocked this request."}',
                status_code=403,
                media_type="application/json",
            )

        # ── 3. Scrub ───────────────────────────────────────────────────────────
        messages = payload.get("messages", []) if payload else []
        scrubbed_messages, scrub_result = self._scrubber.scrub_messages(messages)

        if scrub_result.was_modified and payload is not None:
            payload = {**payload, "messages": scrubbed_messages}
            body = _serialize_json(payload)

        # ── 4. Route ───────────────────────────────────────────────────────────
        decision = self._router.route(original_model or "unknown")
        if payload is not None:
            payload = {**payload, "model": decision.target_model}
            body = _serialize_json(payload)

        # ── 5. Estimate cost ───────────────────────────────────────────────────
        input_text = " ".join(m.get("content", "") for m in messages if isinstance(m.get("content"), str))
        cost_estimate = self._router.estimate_cost(
            decision,
            input_text=input_text,
            output_tokens=500,  # estimated; updated with actual after response
        )

        # ── 6. Forward ─────────────────────────────────────────────────────────
        forward_headers = _build_forward_headers(request, self._settings)
        target_url = decision.target_endpoint

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

        # ── 7. Extract output tokens from response ─────────────────────────────
        upstream_body = upstream.content
        upstream_json = _parse_json_safe(upstream_body)
        output_tokens = _extract_output_tokens(upstream_json)

        # Re-calculate cost with actual output tokens
        cost_estimate = self._router.estimate_cost(
            decision,
            input_tokens=cost_estimate.input_tokens,
            output_tokens=output_tokens or 500,
        )

        # ── 8. Audit ───────────────────────────────────────────────────────────
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
            output_tokens=output_tokens or 0,
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

        # ── 9. Return response ─────────────────────────────────────────────────
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


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _read_body(request: Request, max_mb: int) -> bytes:
    body = await request.body()
    if len(body) > max_mb * 1024 * 1024:
        raise ValueError(f"Request body exceeds {max_mb}MB limit")
    return body


def _parse_json_safe(data: bytes | str) -> dict[str, Any] | None:
    if not data:
        return None
    import json
    try:
        return json.loads(data)
    except Exception:
        return None


def _serialize_json(obj: Any) -> bytes:
    import json
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
    # OpenAI format
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

    # Pass through auth headers from the original request
    for name in ("authorization", "x-api-key", "anthropic-version", "openai-organization"):
        val = request.headers.get(name)
        if val:
            headers[name] = val

    headers["content-type"] = "application/json"
    headers["user-agent"] = f"ModelToll/{settings.app_version}"
    headers["accept"] = "application/json"

    return headers
