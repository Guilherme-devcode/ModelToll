"""
ModelToll Model Router
──────────────────────
Determines which approved, cost-optimized model should handle a request that
was originally targeted at an expensive or unauthorized model.

The router:
  1. Loads routing rules from config/model_routing.json
  2. Matches the requested model against source_pattern (partial/regex match)
  3. Returns the cheapest approved target model + cost metadata
  4. Calculates per-request savings for the cost arbitrage billing engine
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
import tiktoken

log = structlog.get_logger(__name__)

_DEFAULT_ENCODING = "cl100k_base"  # works for most modern models


# ── Data models ────────────────────────────────────────────────────────────────

@dataclass
class RouteDecision:
    source_model: str
    target_model: str
    target_provider: str
    target_endpoint: str
    cost_input_per_1m_source: float
    cost_input_per_1m_target: float
    cost_output_per_1m_source: float
    cost_output_per_1m_target: float
    reason: str
    is_default: bool = False


@dataclass
class CostEstimate:
    input_tokens: int
    output_tokens_estimated: int
    source_cost_usd: float
    target_cost_usd: float
    savings_usd: float
    savings_percent: float


# ── Router ─────────────────────────────────────────────────────────────────────

class ModelRouter:
    """
    Usage::

        router = ModelRouter.from_config("config/model_routing.json", default_model="gpt-4o-mini")
        decision = router.route("gpt-4o")
        estimate = router.estimate_cost(decision, input_text="...", output_tokens=500)
    """

    def __init__(self, routes: list[dict[str, Any]], default_route: dict[str, Any]) -> None:
        self._raw_routes = routes
        self._default = default_route
        self._compiled: list[tuple[re.Pattern[str], dict[str, Any]]] = [
            (re.compile(r["source_pattern"], re.IGNORECASE), r)
            for r in routes
        ]

    @classmethod
    def from_config(cls, config_path: str | Path, default_model: str = "gpt-4o-mini") -> "ModelRouter":
        p = Path(config_path)
        if not p.exists():
            log.warning("routing_config_missing", path=str(p))
            return cls(routes=[], default_route=_fallback_default(default_model))
        with p.open() as f:
            data = json.load(f)
        log.info("routing_config_loaded", routes=len(data.get("routes", [])))
        return cls(
            routes=data.get("routes", []),
            default_route=data.get("default_route", _fallback_default(default_model)),
        )

    # ── Core routing ───────────────────────────────────────────────────────────

    def route(self, requested_model: str) -> RouteDecision:
        """Return the approved target model for a given requested model name."""
        for pattern, rule in self._compiled:
            if pattern.search(requested_model):
                log.info(
                    "route_matched",
                    source=requested_model,
                    target=rule["target_model"],
                    reason=rule.get("reason", ""),
                )
                return RouteDecision(
                    source_model=requested_model,
                    target_model=rule["target_model"],
                    target_provider=rule["target_provider"],
                    target_endpoint=rule["target_endpoint"],
                    cost_input_per_1m_source=rule.get("cost_input_per_1m_source", 0.0),
                    cost_input_per_1m_target=rule.get("cost_input_per_1m_target", 0.0),
                    cost_output_per_1m_source=rule.get("cost_output_per_1m_source", 0.0),
                    cost_output_per_1m_target=rule.get("cost_output_per_1m_target", 0.0),
                    reason=rule.get("reason", "policy route"),
                )

        log.info("route_default", source=requested_model, target=self._default["target_model"])
        d = self._default
        return RouteDecision(
            source_model=requested_model,
            target_model=d["target_model"],
            target_provider=d["target_provider"],
            target_endpoint=d["target_endpoint"],
            cost_input_per_1m_source=d.get("cost_input_per_1m_source", 5.0),
            cost_input_per_1m_target=d.get("cost_input_per_1m_target", 0.15),
            cost_output_per_1m_source=d.get("cost_output_per_1m_source", 15.0),
            cost_output_per_1m_target=d.get("cost_output_per_1m_target", 0.60),
            reason="default approved model",
            is_default=True,
        )

    # ── Cost estimation ────────────────────────────────────────────────────────

    def estimate_cost(
        self,
        decision: RouteDecision,
        input_text: str = "",
        input_tokens: int | None = None,
        output_tokens: int = 500,
    ) -> CostEstimate:
        """Estimate cost savings for a routing decision."""
        if input_tokens is None:
            input_tokens = _count_tokens(input_text)

        source_cost = (
            input_tokens / 1_000_000 * decision.cost_input_per_1m_source
            + output_tokens / 1_000_000 * decision.cost_output_per_1m_source
        )
        target_cost = (
            input_tokens / 1_000_000 * decision.cost_input_per_1m_target
            + output_tokens / 1_000_000 * decision.cost_output_per_1m_target
        )
        savings = max(0.0, source_cost - target_cost)
        savings_pct = (savings / source_cost * 100) if source_cost > 0 else 0.0

        return CostEstimate(
            input_tokens=input_tokens,
            output_tokens_estimated=output_tokens,
            source_cost_usd=source_cost,
            target_cost_usd=target_cost,
            savings_usd=savings,
            savings_percent=savings_pct,
        )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _count_tokens(text: str) -> int:
    try:
        enc = tiktoken.get_encoding(_DEFAULT_ENCODING)
        return len(enc.encode(text))
    except Exception:
        # Rough estimate: 1 token ≈ 4 chars
        return max(1, len(text) // 4)


def _fallback_default(model: str) -> dict[str, Any]:
    return {
        "target_model": model,
        "target_provider": "openai",
        "target_endpoint": "https://api.openai.com/v1/chat/completions",
        "cost_input_per_1m_target": 0.15,
        "cost_output_per_1m_target": 0.60,
    }
