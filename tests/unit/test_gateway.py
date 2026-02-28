"""Unit tests for the ProxyGateway pipeline (no real HTTP calls)."""

from __future__ import annotations

import json
import re
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from src.audit.logger import AuditLogger
from src.audit.models import RequestAction
from src.config.settings import Settings
from src.proxy.gateway import (
    ProxyGateway,
    _build_forward_headers,
    _count_tokens,
    _extract_model,
    _extract_output_tokens,
    _parse_json_safe,
)
from src.router.model_router import ModelRouter
from src.scrubber.engine import ScrubberEngine


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _make_settings(**overrides) -> Settings:
    defaults = {
        "database_url": "postgresql+asyncpg://x:x@localhost/x",
        "redis_url": "redis://localhost:6379/0",
        "admin_api_key": "test-key",
        "secret_key": "a" * 32,
        "scrubber_enabled": True,
        "blocked_ai_hosts": "blocked.example.com",
    }
    defaults.update(overrides)
    return Settings(**defaults)


# ── Tests: parse helpers ────────────────────────────────────────────────────────

class TestParseHelpers:
    def test_parse_valid_json(self) -> None:
        data = json.dumps({"model": "gpt-4o", "messages": []}).encode()
        result = _parse_json_safe(data)
        assert result is not None
        assert result["model"] == "gpt-4o"

    def test_parse_invalid_json_returns_none(self) -> None:
        assert _parse_json_safe(b"not json") is None

    def test_parse_empty_returns_none(self) -> None:
        assert _parse_json_safe(b"") is None

    def test_extract_model_from_payload(self) -> None:
        payload = {"model": "gpt-4o", "messages": []}
        assert _extract_model(payload) == "gpt-4o"

    def test_extract_model_none_when_missing(self) -> None:
        assert _extract_model({}) is None
        assert _extract_model(None) is None

    def test_extract_output_tokens_openai(self) -> None:
        payload = {"usage": {"prompt_tokens": 100, "completion_tokens": 50}}
        assert _extract_output_tokens(payload) == 50

    def test_extract_output_tokens_none(self) -> None:
        assert _extract_output_tokens(None) is None
        assert _extract_output_tokens({}) is None


# ── Tests: gateway pipeline (mocked) ───────────────────────────────────────────

class TestProxyGateway:
    def _make_gateway(self) -> tuple[ProxyGateway, MagicMock]:
        settings = _make_settings()

        # Mock scrubber that doesn't modify anything
        scrubber = MagicMock(spec=ScrubberEngine)
        from src.scrubber.engine import ScrubResult
        scrubber.scrub_messages.return_value = (
            [{"role": "user", "content": "Hello"}],
            ScrubResult(original="Hello", scrubbed="Hello", was_modified=False),
        )

        # Real router with minimal config
        router = ModelRouter(
            routes=[
                {
                    "source_pattern": "gpt-4o",
                    "target_model": "gpt-4o-mini",
                    "target_provider": "openai",
                    "target_endpoint": "https://api.openai.com/v1/chat/completions",
                    "cost_input_per_1m_source": 5.0,
                    "cost_input_per_1m_target": 0.15,
                    "cost_output_per_1m_source": 15.0,
                    "cost_output_per_1m_target": 0.60,
                    "reason": "test route",
                }
            ],
            default_route={
                "target_model": "gpt-4o-mini",
                "target_provider": "openai",
                "target_endpoint": "https://api.openai.com/v1/chat/completions",
                "cost_input_per_1m_target": 0.15,
                "cost_output_per_1m_target": 0.60,
            },
        )

        audit = MagicMock(spec=AuditLogger)
        audit.build_entry.return_value = MagicMock()
        audit.record = MagicMock()

        gw = ProxyGateway(
            settings=settings,
            scrubber=scrubber,
            router=router,
            audit=audit,
        )
        return gw, audit

    @pytest.mark.asyncio
    async def test_blocked_host_returns_403(self) -> None:
        gw, audit = self._make_gateway()

        request = MagicMock()
        request.body = AsyncMock(return_value=b'{"model": "gpt-4o", "messages": []}')
        request.headers = {"host": "blocked.example.com"}
        request.url = MagicMock()
        request.url.__str__ = lambda s: "http://blocked.example.com/v1/chat/completions"
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        response = await gw.handle(request, tenant_id="test-tenant")
        assert response.status_code == 403
        audit.record.assert_called_once()
        # Verify the recorded entry was for a blocked action
        entry_call = audit.build_entry.call_args
        assert entry_call.kwargs["action"] == RequestAction.BLOCKED

    @pytest.mark.asyncio
    async def test_scrubbed_request_forwarded(self) -> None:
        gw, audit = self._make_gateway()

        # Scrubber detects sensitive content
        from src.scrubber.engine import Detection, ScrubResult
        gw._scrubber.scrub_messages.return_value = (
            [{"role": "user", "content": "My key is [AWS_ACCESS_KEY]"}],
            ScrubResult(
                original="My key is AKIAIOSFODNN7EXAMPLE",
                scrubbed="My key is [AWS_ACCESS_KEY]",
                detections=[
                    Detection("AWS_ACCESS_KEY", 10, 30, 0.99, "AKIAIOSFODNN7EXAMPLE")
                ],
                was_modified=True,
            ),
        )

        mock_response = httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}], "usage": {"completion_tokens": 10}},
        )
        gw._client.post = AsyncMock(return_value=mock_response)

        request = MagicMock()
        request.body = AsyncMock(return_value=json.dumps({
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "My key is AKIAIOSFODNN7EXAMPLE"}],
        }).encode())
        request.headers = {"host": "api.openai.com"}
        request.url = MagicMock()
        request.url.__str__ = lambda s: "http://api.openai.com/v1/chat/completions"
        request.client = MagicMock()
        request.client.host = "10.0.0.1"

        response = await gw.handle(request, tenant_id="test-tenant")
        assert response.status_code == 200
        assert response.headers.get("x-modeltoll-scrubbed") == "1"
        assert response.headers.get("x-modeltoll-routed-model") == "gpt-4o-mini"
