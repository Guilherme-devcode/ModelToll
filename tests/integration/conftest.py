"""
Integration test fixtures for ModelToll.

Uses:
  - FastAPI TestClient (synchronous requests in tests)
  - SQLite in-memory database (no external PostgreSQL required)
  - Mocked httpx upstream (no real LLM API calls)
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.audit.logger import AuditLogger
from src.audit.models import Base
from src.config.settings import Settings
from src.main import create_app
from src.router.model_router import ModelRouter
from src.scrubber.engine import CustomPattern, PresidioScrubber, ScrubberEngine
import re


# ── Test settings ─────────────────────────────────────────────────────────────

TEST_SETTINGS = Settings(
    database_url="sqlite+aiosqlite:///./test_integration.db",
    redis_url="redis://localhost:6379/0",
    admin_api_key="test-admin-key",
    secret_key="a" * 32,
    monitored_ai_hosts="api.openai.com,api.anthropic.com",
    hard_blocked_hosts="blocked.example.com",
    scrubber_enabled=True,
    environment="testing",
)


# ── Minimal scrubber (regex-only, no NLP) ─────────────────────────────────────

def _make_test_scrubber() -> ScrubberEngine:
    """Lightweight scrubber with just a few patterns — no Presidio/spacy."""
    patterns = [
        CustomPattern(
            name="AWS_ACCESS_KEY",
            regex=re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
            score=0.99,
            replacement="[AWS_ACCESS_KEY]",
        ),
        CustomPattern(
            name="EMAIL",
            regex=re.compile(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}"),
            score=0.90,
            replacement="[EMAIL]",
        ),
    ]

    class _NoPresidio(PresidioScrubber):
        def analyze(self, text: str) -> list:
            return []

        def anonymize(self, text: str, detections: list) -> str:
            return text

    return ScrubberEngine(
        custom_patterns=patterns,
        presidio=_NoPresidio(entities=[]),
        enabled=True,
    )


# ── Minimal router ─────────────────────────────────────────────────────────────

def _make_test_router() -> ModelRouter:
    return ModelRouter(
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


# ── Fake upstream response ─────────────────────────────────────────────────────

FAKE_UPSTREAM_RESPONSE = {
    "id": "chatcmpl-test",
    "object": "chat.completion",
    "choices": [{"message": {"role": "assistant", "content": "Hello!"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
}


# ── App fixture ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture()
def test_client() -> Generator[TestClient, None, None]:
    """
    Full FastAPI app with:
    - SQLite in-memory DB
    - No-op scrubber (regex only, no NLP)
    - Mocked httpx upstream (no real API calls)
    """
    scrubber = _make_test_scrubber()
    router = _make_test_router()

    # Patch settings globally so the app factory picks up test config
    with patch("src.config.settings.settings", TEST_SETTINGS), \
         patch("src.main.settings", TEST_SETTINGS), \
         patch("src.proxy.gateway.Settings", return_value=TEST_SETTINGS), \
         patch("src.dashboard.api.settings", TEST_SETTINGS):

        app = create_app()

        # Override startup — swap in test scrubber/router
        from src.proxy.gateway import ProxyGateway

        @app.on_event("startup")
        async def override_startup() -> None:
            engine = create_async_engine("sqlite+aiosqlite:///./test_integration.db")
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            audit = AuditLogger(
                database_url="sqlite+aiosqlite:///./test_integration.db",
                savings_share_percent=20.0,
            )
            await audit.start()
            app.state.gateway = ProxyGateway(
                settings=TEST_SETTINGS,
                scrubber=scrubber,
                router=router,
                audit=audit,
            )
            app.state.session_factory = session_factory

        with TestClient(app, raise_server_exceptions=True) as client:
            yield client
