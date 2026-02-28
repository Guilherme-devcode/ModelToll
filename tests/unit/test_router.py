"""Unit tests for the ModelToll model router."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.router.model_router import CostEstimate, ModelRouter, RouteDecision, _count_tokens


# ── Fixtures ────────────────────────────────────────────────────────────────────

ROUTING_CONFIG = {
    "routes": [
        {
            "source_pattern": "gpt-4o",
            "target_model": "gpt-4o-mini",
            "target_provider": "openai",
            "target_endpoint": "https://api.openai.com/v1/chat/completions",
            "cost_input_per_1m_source": 5.00,
            "cost_input_per_1m_target": 0.15,
            "cost_output_per_1m_source": 15.00,
            "cost_output_per_1m_target": 0.60,
            "reason": "gpt-4o → gpt-4o-mini: 97% cheaper",
        },
        {
            "source_pattern": "claude-opus",
            "target_model": "claude-haiku-4-5-20251001",
            "target_provider": "anthropic",
            "target_endpoint": "https://api.anthropic.com/v1/messages",
            "cost_input_per_1m_source": 15.00,
            "cost_input_per_1m_target": 0.80,
            "cost_output_per_1m_source": 75.00,
            "cost_output_per_1m_target": 4.00,
            "reason": "claude-opus → claude-haiku",
        },
    ],
    "default_route": {
        "target_model": "gpt-4o-mini",
        "target_provider": "openai",
        "target_endpoint": "https://api.openai.com/v1/chat/completions",
        "cost_input_per_1m_target": 0.15,
        "cost_output_per_1m_target": 0.60,
    },
}


@pytest.fixture()
def router(tmp_path: Path) -> ModelRouter:
    config_file = tmp_path / "routing.json"
    config_file.write_text(json.dumps(ROUTING_CONFIG))
    return ModelRouter.from_config(config_file)


# ── Tests ───────────────────────────────────────────────────────────────────────

class TestModelRouter:
    def test_route_gpt4o_to_mini(self, router: ModelRouter) -> None:
        decision = router.route("gpt-4o")
        assert decision.target_model == "gpt-4o-mini"
        assert decision.target_provider == "openai"
        assert not decision.is_default

    def test_route_gpt4o_versioned(self, router: ModelRouter) -> None:
        decision = router.route("gpt-4o-2024-11-20")
        assert decision.target_model == "gpt-4o-mini"

    def test_route_claude_opus(self, router: ModelRouter) -> None:
        decision = router.route("claude-opus-4-6")
        assert decision.target_model == "claude-haiku-4-5-20251001"
        assert decision.target_provider == "anthropic"

    def test_route_unknown_model_uses_default(self, router: ModelRouter) -> None:
        decision = router.route("some-random-model-x99")
        assert decision.is_default
        assert decision.target_model == "gpt-4o-mini"

    def test_route_case_insensitive(self, router: ModelRouter) -> None:
        decision = router.route("GPT-4O")
        assert decision.target_model == "gpt-4o-mini"

    def test_missing_config_returns_default(self, tmp_path: Path) -> None:
        router = ModelRouter.from_config(tmp_path / "nonexistent.json")
        decision = router.route("gpt-4o")
        assert decision.is_default

    def test_estimate_cost_savings(self, router: ModelRouter) -> None:
        decision = router.route("gpt-4o")
        estimate = router.estimate_cost(decision, input_tokens=1000, output_tokens=500)
        # gpt-4o input: 1000/1M * $5 = $0.005; target: 1000/1M * $0.15 = $0.00015
        assert estimate.savings_usd > 0
        assert estimate.savings_percent > 90  # ~97% cheaper

    def test_estimate_cost_no_savings_when_same_price(self, router: ModelRouter) -> None:
        decision = router.route("gpt-4o")
        # Manually override costs to equal
        decision.cost_input_per_1m_source = decision.cost_input_per_1m_target
        decision.cost_output_per_1m_source = decision.cost_output_per_1m_target
        estimate = router.estimate_cost(decision, input_tokens=1000, output_tokens=500)
        assert estimate.savings_usd == 0.0

    def test_estimate_cost_with_text(self, router: ModelRouter) -> None:
        decision = router.route("gpt-4o")
        text = "Hello, this is a test prompt with some tokens."
        estimate = router.estimate_cost(decision, input_text=text, output_tokens=100)
        assert estimate.input_tokens > 0
        assert estimate.source_cost_usd > 0


class TestTokenCounter:
    def test_count_tokens_returns_positive(self) -> None:
        n = _count_tokens("Hello world!")
        assert n > 0

    def test_empty_string(self) -> None:
        assert _count_tokens("") >= 1  # returns max(1, ...)

    def test_longer_text_more_tokens(self) -> None:
        short = _count_tokens("Hi")
        long = _count_tokens("Hi " * 100)
        assert long > short
