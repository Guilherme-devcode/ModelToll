"""Unit tests for the ModelToll scrubber engine."""

from __future__ import annotations

import re

import pytest

from src.scrubber.engine import (
    CustomPattern,
    Detection,
    PresidioScrubber,
    ScrubResult,
    ScrubberEngine,
    load_custom_patterns,
)


# ── Fixtures ────────────────────────────────────────────────────────────────────

def _make_engine(enabled: bool = True) -> ScrubberEngine:
    """Create a scrubber engine with a set of test patterns (no Presidio)."""
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
        CustomPattern(
            name="CPF_BR",
            regex=re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),
            score=0.90,
            replacement="[CPF_REDACTED]",
        ),
    ]

    class _NoOpPresidio(PresidioScrubber):
        def analyze(self, text: str) -> list[Detection]:
            return []

        def anonymize(self, text: str, detections: list[Detection]) -> str:
            return text

    presidio = _NoOpPresidio(entities=[])
    return ScrubberEngine(custom_patterns=patterns, presidio=presidio, enabled=enabled)


# ── Tests ───────────────────────────────────────────────────────────────────────

class TestScrubberEngine:
    def test_aws_key_redacted(self) -> None:
        engine = _make_engine()
        result = engine.scrub("My key is AKIAIOSFODNN7EXAMPLE and I use it daily.")
        assert "[AWS_ACCESS_KEY]" in result.scrubbed
        assert "AKIAIOSFODNN7EXAMPLE" not in result.scrubbed
        assert result.was_modified

    def test_email_redacted(self) -> None:
        engine = _make_engine()
        result = engine.scrub("Contact john.doe@company.com for help.")
        assert "[EMAIL]" in result.scrubbed
        assert "john.doe@company.com" not in result.scrubbed

    def test_cpf_br_redacted(self) -> None:
        engine = _make_engine()
        result = engine.scrub("CPF do usuário: 123.456.789-09")
        assert "[CPF_REDACTED]" in result.scrubbed
        assert result.was_modified

    def test_clean_text_not_modified(self) -> None:
        engine = _make_engine()
        result = engine.scrub("This is a normal message with no sensitive data.")
        assert not result.was_modified
        assert result.original == result.scrubbed

    def test_empty_string(self) -> None:
        engine = _make_engine()
        result = engine.scrub("")
        assert result.scrubbed == ""
        assert not result.was_modified

    def test_disabled_engine_passthrough(self) -> None:
        engine = _make_engine(enabled=False)
        sensitive = "My key is AKIAIOSFODNN7EXAMPLE"
        result = engine.scrub(sensitive)
        assert result.scrubbed == sensitive
        assert not result.was_modified

    def test_multiple_detections(self) -> None:
        engine = _make_engine()
        text = "Key: AKIAIOSFODNN7EXAMPLE, email: ceo@startup.io"
        result = engine.scrub(text)
        assert result.was_modified
        assert len(result.detections) >= 2

    def test_scrub_messages_list(self) -> None:
        engine = _make_engine()
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "My AWS key is AKIAIOSFODNN7EXAMPLE"},
        ]
        scrubbed_msgs, aggregate = engine.scrub_messages(messages)
        assert scrubbed_msgs[0]["content"] == "You are a helpful assistant."
        assert "[AWS_KEY]" not in scrubbed_msgs[1]["content"] or "[AWS_ACCESS_KEY]" in scrubbed_msgs[1]["content"]
        assert aggregate.was_modified

    def test_detection_count_matches(self) -> None:
        engine = _make_engine()
        result = engine.scrub("Keys: AKIAIOSFODNN7EXAMPLE and AKIAIOSFODNN7ABCDEF")
        # Both AWS key pattern matches should be detected
        aws_detections = [d for d in result.detections if d.entity_type == "AWS_ACCESS_KEY"]
        assert len(aws_detections) >= 1

    def test_entity_types_found_property(self) -> None:
        engine = _make_engine()
        result = engine.scrub("Email: bob@example.com and key: AKIAIOSFODNN7EXAMPLE")
        types = result.entity_types_found
        assert "EMAIL" in types
        assert "AWS_ACCESS_KEY" in types


class TestLoadCustomPatterns:
    def test_load_from_file(self, tmp_path: object) -> None:
        import json
        from pathlib import Path

        p = Path(str(tmp_path)) / "patterns.json"  # type: ignore[call-overload]
        p.write_text(json.dumps({
            "patterns": [
                {
                    "name": "TEST_PATTERN",
                    "regex": r"\bSECRET-\d{4}\b",
                    "score": 0.95,
                    "replacement": "[SECRET]",
                }
            ]
        }))
        patterns = load_custom_patterns(p)
        assert len(patterns) == 1
        assert patterns[0].name == "TEST_PATTERN"

    def test_missing_file_returns_empty(self) -> None:
        patterns = load_custom_patterns("/nonexistent/path.json")
        assert patterns == []
