"""
ModelToll Scrubber Engine
─────────────────────────
Detects and redacts PII, secrets, and proprietary data from prompts before
forwarding them to any LLM provider.

Strategy (layered):
  1. Custom regex patterns (fastest — catches secrets, keys, internal codes)
  2. Microsoft Presidio NLP-based PII detection (names, emails, phones, …)
  3. Score-threshold filtering so low-confidence matches are not redacted
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger(__name__)


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class Detection:
    entity_type: str
    start: int
    end: int
    score: float
    text: str


@dataclass
class ScrubResult:
    original: str
    scrubbed: str
    detections: list[Detection] = field(default_factory=list)
    was_modified: bool = False

    @property
    def detection_count(self) -> int:
        return len(self.detections)

    @property
    def entity_types_found(self) -> list[str]:
        return list({d.entity_type for d in self.detections})


# ── Custom-pattern loader ──────────────────────────────────────────────────────

@dataclass
class CustomPattern:
    name: str
    regex: re.Pattern[str]
    score: float
    replacement: str


def load_custom_patterns(path: str | Path) -> list[CustomPattern]:
    p = Path(path)
    if not p.exists():
        log.warning("custom_patterns_file_missing", path=str(p))
        return []
    with p.open() as f:
        data = json.load(f)
    patterns: list[CustomPattern] = []
    for item in data.get("patterns", []):
        try:
            patterns.append(
                CustomPattern(
                    name=item["name"],
                    regex=re.compile(item["regex"], re.MULTILINE | re.DOTALL),
                    score=float(item.get("score", 0.8)),
                    replacement=item.get("replacement", f"[{item['name']}]"),
                )
            )
        except re.error as exc:
            log.error("invalid_custom_pattern", name=item.get("name"), error=str(exc))
    log.info("custom_patterns_loaded", count=len(patterns))
    return patterns


# ── Presidio wrapper ───────────────────────────────────────────────────────────

class PresidioScrubber:
    """Lazy-loaded Presidio analyzer + anonymizer."""

    def __init__(self, entities: list[str], score_threshold: float = 0.6) -> None:
        self._entities = entities
        self._threshold = score_threshold
        self._analyzer: Any = None
        self._anonymizer: Any = None

    def _ensure_loaded(self) -> None:
        if self._analyzer is not None:
            return
        try:
            from presidio_analyzer import AnalyzerEngine  # type: ignore[import]
            from presidio_anonymizer import AnonymizerEngine  # type: ignore[import]

            self._analyzer = AnalyzerEngine()
            self._anonymizer = AnonymizerEngine()
            log.info("presidio_loaded")
        except ImportError:
            log.warning(
                "presidio_not_installed",
                hint="pip install presidio-analyzer presidio-anonymizer",
            )

    def analyze(self, text: str) -> list[Detection]:
        self._ensure_loaded()
        if self._analyzer is None:
            return []
        results = self._analyzer.analyze(
            text=text,
            entities=self._entities,
            language="en",
            score_threshold=self._threshold,
        )
        return [
            Detection(
                entity_type=r.entity_type,
                start=r.start,
                end=r.end,
                score=r.score,
                text=text[r.start : r.end],
            )
            for r in results
        ]

    def anonymize(self, text: str, detections: list[Detection]) -> str:
        self._ensure_loaded()
        if self._anonymizer is None or not detections:
            return text
        from presidio_anonymizer.entities import OperatorConfig, RecognizerResult  # type: ignore[import]

        recognizer_results = [
            RecognizerResult(
                entity_type=d.entity_type,
                start=d.start,
                end=d.end,
                score=d.score,
            )
            for d in detections
        ]
        result = self._anonymizer.anonymize(
            text=text,
            analyzer_results=recognizer_results,
            operators={
                "DEFAULT": OperatorConfig("replace", {"new_value": "<REDACTED>"})
            },
        )
        return result.text


# ── Main scrubber ──────────────────────────────────────────────────────────────

class ScrubberEngine:
    """
    Unified scrubbing pipeline.

    Usage::

        engine = ScrubberEngine.from_settings(settings)
        result = engine.scrub("Send this to john@acme.com: AKIA1234567890ABCDEF")
        assert result.was_modified
    """

    def __init__(
        self,
        custom_patterns: list[CustomPattern],
        presidio: PresidioScrubber,
        enabled: bool = True,
    ) -> None:
        self._custom = custom_patterns
        self._presidio = presidio
        self._enabled = enabled

    @classmethod
    def from_settings(cls, settings: Any) -> "ScrubberEngine":
        from src.config.settings import Settings

        s: Settings = settings
        patterns = load_custom_patterns(s.custom_patterns_path)
        presidio = PresidioScrubber(
            entities=s.pii_entity_list,
            score_threshold=0.6,
        )
        return cls(
            custom_patterns=patterns,
            presidio=presidio,
            enabled=s.scrubber_enabled,
        )

    # ── Public API ─────────────────────────────────────────────────────────────

    def scrub(self, text: str) -> ScrubResult:
        if not self._enabled or not text:
            return ScrubResult(original=text, scrubbed=text)

        detections: list[Detection] = []
        working = text

        # Layer 1: custom regex (faster, no ML overhead)
        working, regex_detections = self._apply_custom_patterns(working)
        detections.extend(regex_detections)

        # Layer 2: Presidio NLP PII detection
        presidio_hits = self._presidio.analyze(working)
        if presidio_hits:
            working = self._presidio.anonymize(working, presidio_hits)
            detections.extend(presidio_hits)

        result = ScrubResult(
            original=text,
            scrubbed=working,
            detections=detections,
            was_modified=(working != text),
        )

        if result.was_modified:
            log.info(
                "prompt_scrubbed",
                detection_count=result.detection_count,
                entity_types=result.entity_types_found,
                chars_before=len(text),
                chars_after=len(working),
            )

        return result

    def scrub_messages(self, messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], ScrubResult]:
        """Scrub the content of all messages in an OpenAI-style messages array."""
        all_text = "\n".join(
            m.get("content", "") for m in messages if isinstance(m.get("content"), str)
        )
        # Quick check — scrub combined text to detect, then scrub each individually
        combined_result = self.scrub(all_text)

        scrubbed_messages = []
        all_detections: list[Detection] = []
        modified = False

        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                r = self.scrub(content)
                all_detections.extend(r.detections)
                if r.was_modified:
                    modified = True
                scrubbed_messages.append({**msg, "content": r.scrubbed})
            else:
                scrubbed_messages.append(msg)

        aggregate = ScrubResult(
            original=all_text,
            scrubbed="\n".join(m.get("content", "") for m in scrubbed_messages if isinstance(m.get("content"), str)),
            detections=all_detections,
            was_modified=modified,
        )
        return scrubbed_messages, aggregate

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _apply_custom_patterns(self, text: str) -> tuple[str, list[Detection]]:
        detections: list[Detection] = []
        for pattern in self._custom:
            for match in pattern.regex.finditer(text):
                detections.append(
                    Detection(
                        entity_type=pattern.name,
                        start=match.start(),
                        end=match.end(),
                        score=pattern.score,
                        text=match.group(),
                    )
                )
        # Replace all matches (in reverse order to preserve offsets)
        working = text
        for pattern in self._custom:
            working = pattern.regex.sub(pattern.replacement, working)
        return working, detections
