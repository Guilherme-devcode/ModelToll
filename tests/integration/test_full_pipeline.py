"""
Integration tests for the ModelToll proxy pipeline.

Tests the full request lifecycle:
  Request -> [scrubber] -> [router] -> [mock upstream] -> [audit] -> Response

No real LLM API calls are made — httpx is mocked.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

ADMIN_KEY = "test-admin-key"
ADMIN_HEADERS = {"X-Admin-Api-Key": ADMIN_KEY}

OPENAI_HOST_HEADER = {"host": "api.openai.com"}

FAKE_UPSTREAM = {
    "id": "chatcmpl-test",
    "object": "chat.completion",
    "choices": [{"message": {"role": "assistant", "content": "Hello!"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
}


def _make_fake_response(status: int = 200, body: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        json=body or FAKE_UPSTREAM,
        headers={"content-type": "application/json"},
    )


# ── Health check ─────────────────────────────────────────────────────────────

def test_health(test_client: TestClient) -> None:
    res = test_client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "version" in data


# ── Hard-blocked host ─────────────────────────────────────────────────────────

def test_hard_blocked_host_returns_403(test_client: TestClient) -> None:
    """Requests to hosts in hard_blocked_hosts should be rejected with 403."""
    payload = {"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]}
    res = test_client.post(
        "/v1/chat/completions",
        json=payload,
        headers={"host": "blocked.example.com"},
    )
    assert res.status_code == 403
    assert "blocked" in res.json().get("error", "").lower()


# ── Unmonitored host passthrough ──────────────────────────────────────────────

def test_unmonitored_host_passthrough(test_client: TestClient) -> None:
    """Requests to hosts NOT in monitored_ai_hosts are forwarded as-is (PASSTHROUGH)."""
    payload = {"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]}

    mock_upstream = _make_fake_response()
    with patch.object(
        test_client.app.state.gateway._client,
        "request",
        new_callable=AsyncMock,
        return_value=mock_upstream,
    ):
        res = test_client.post(
            "/v1/chat/completions",
            json=payload,
            headers={"host": "internal.mycompany.ai"},
        )
    # Passthrough: no modeltoll headers, forwarded as-is
    assert res.status_code == 200
    # x-modeltoll-routed-model should NOT be present on passthrough
    assert "x-modeltoll-routed-model" not in res.headers


# ── Model rerouting ───────────────────────────────────────────────────────────

def test_model_rerouted_to_cheaper(test_client: TestClient) -> None:
    """gpt-4o requests should be rerouted to gpt-4o-mini."""
    payload = {"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello!"}]}

    mock_upstream = _make_fake_response()
    with patch.object(
        test_client.app.state.gateway._client,
        "post",
        new_callable=AsyncMock,
        return_value=mock_upstream,
    ) as mock_post:
        res = test_client.post(
            "/v1/chat/completions",
            json=payload,
            headers={"host": "api.openai.com"},
        )

    assert res.status_code == 200
    # Response must carry ModelToll routing header
    assert res.headers.get("x-modeltoll-routed-model") == "gpt-4o-mini"
    # Upstream must receive gpt-4o-mini in the body
    call_kwargs = mock_post.call_args
    sent_body = json.loads(call_kwargs.kwargs.get("content") or call_kwargs.args[1])
    assert sent_body["model"] == "gpt-4o-mini"


# ── PII scrubbing ─────────────────────────────────────────────────────────────

def test_pii_scrubbed_before_forwarding(test_client: TestClient) -> None:
    """Email and AWS key in the prompt must be redacted before reaching upstream."""
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "My email is ceo@company.com and key AKIAIOSFODNN7EXAMPLE"}
        ],
    }

    mock_upstream = _make_fake_response()
    with patch.object(
        test_client.app.state.gateway._client,
        "post",
        new_callable=AsyncMock,
        return_value=mock_upstream,
    ) as mock_post:
        res = test_client.post(
            "/v1/chat/completions",
            json=payload,
            headers={"host": "api.openai.com"},
        )

    assert res.status_code == 200
    assert res.headers.get("x-modeltoll-scrubbed") == "1"

    call_kwargs = mock_post.call_args
    sent_body = json.loads(call_kwargs.kwargs.get("content") or call_kwargs.args[1])
    sent_content = sent_body["messages"][0]["content"]
    # Sensitive data must NOT appear in the upstream payload
    assert "ceo@company.com" not in sent_content
    assert "AKIAIOSFODNN7EXAMPLE" not in sent_content
    # Redaction placeholders must be present
    assert "[EMAIL]" in sent_content or "[AWS_ACCESS_KEY]" in sent_content


def test_clean_prompt_not_flagged(test_client: TestClient) -> None:
    """A prompt with no sensitive data should NOT trigger the scrubber."""
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "What is the capital of France?"}],
    }

    mock_upstream = _make_fake_response()
    with patch.object(
        test_client.app.state.gateway._client,
        "post",
        new_callable=AsyncMock,
        return_value=mock_upstream,
    ):
        res = test_client.post(
            "/v1/chat/completions",
            json=payload,
            headers={"host": "api.openai.com"},
        )

    assert res.status_code == 200
    assert res.headers.get("x-modeltoll-scrubbed") == "0"


# ── Cost savings header ───────────────────────────────────────────────────────

def test_savings_header_present(test_client: TestClient) -> None:
    """Forwarded requests should return x-modeltoll-savings-usd header > 0."""
    payload = {"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello!"}]}

    mock_upstream = _make_fake_response()
    with patch.object(
        test_client.app.state.gateway._client,
        "post",
        new_callable=AsyncMock,
        return_value=mock_upstream,
    ):
        res = test_client.post(
            "/v1/chat/completions",
            json=payload,
            headers={"host": "api.openai.com"},
        )

    assert res.status_code == 200
    savings = float(res.headers.get("x-modeltoll-savings-usd", "0"))
    assert savings > 0


# ── Admin API ─────────────────────────────────────────────────────────────────

def test_admin_requires_api_key(test_client: TestClient) -> None:
    res = test_client.get("/dashboard/summary")
    assert res.status_code in (403, 422)  # missing header


def test_admin_rejects_wrong_key(test_client: TestClient) -> None:
    res = test_client.get("/dashboard/summary", headers={"X-Admin-Api-Key": "wrong-key"})
    assert res.status_code == 403


def test_admin_summary_accessible(test_client: TestClient) -> None:
    res = test_client.get("/dashboard/summary", headers=ADMIN_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "total_requests" in data
    assert "total_savings_usd" in data


def test_admin_routing_rules(test_client: TestClient) -> None:
    res = test_client.get("/dashboard/routing-rules", headers=ADMIN_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "routes" in data
    assert "default_model" in data


def test_admin_config_get(test_client: TestClient) -> None:
    res = test_client.get("/dashboard/config", headers=ADMIN_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "scrubber_enabled" in data
    assert "savings_share_percent" in data
    assert "monitored_ai_hosts" in data


def test_admin_config_patch(test_client: TestClient) -> None:
    """PATCH /dashboard/config should update and return the new config."""
    res = test_client.patch(
        "/dashboard/config",
        json={"savings_share_percent": 25.0},
        headers=ADMIN_HEADERS,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["savings_share_percent"] == 25.0
