"""Central settings for ModelToll — loaded from environment / .env file."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "ModelToll"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: LogLevel = LogLevel.INFO
    secret_key: str = Field(default="change-me-in-production-32-chars-min")

    # ── Server ────────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8080
    workers: int = 1

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://modeltoll:modeltoll@localhost:5432/modeltoll"

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Proxy ─────────────────────────────────────────────────────────────────
    proxy_timeout_seconds: int = 120
    max_body_size_mb: int = 10

    # ── Scrubber ──────────────────────────────────────────────────────────────
    scrubber_enabled: bool = True
    # Comma-separated Presidio entity types to redact
    pii_entities: str = (
        "PERSON,EMAIL_ADDRESS,PHONE_NUMBER,CREDIT_CARD,"
        "CRYPTO,IBAN_CODE,IP_ADDRESS,US_SSN,US_PASSPORT,"
        "MEDICAL_RECORD,URL,NRP,LOCATION,DATE_TIME"
    )
    # Regex patterns for proprietary data (added by enterprise admins)
    custom_patterns_path: str = "config/custom_patterns.json"

    # ── Model Router ──────────────────────────────────────────────────────────
    # JSON mapping of source model → approved cheaper target model + cost info
    model_routing_config_path: str = "config/model_routing.json"
    default_approved_model: str = "gpt-4o-mini"

    # ── Cost Arbitrage ────────────────────────────────────────────────────────
    savings_share_percent: float = 20.0  # ModelToll keeps 20% of savings

    # ── Blocked destinations ──────────────────────────────────────────────────
    # Comma-separated hostnames that are always blocked
    blocked_ai_hosts: str = (
        "api.openai.com,api.anthropic.com,generativelanguage.googleapis.com,"
        "api.cohere.ai,api.mistral.ai,api.together.xyz,api.groq.com,"
        "api.perplexity.ai,api-inference.huggingface.co"
    )

    # ── Admin API ─────────────────────────────────────────────────────────────
    admin_api_key: str = "change-me-admin-key"
    dashboard_allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    # ── Metrics ───────────────────────────────────────────────────────────────
    metrics_enabled: bool = True

    @field_validator("pii_entities", "blocked_ai_hosts", "dashboard_allowed_origins")
    @classmethod
    def split_csv(cls, v: str) -> Any:  # kept as str at runtime; helpers parse it
        return v

    @property
    def pii_entity_list(self) -> list[str]:
        return [e.strip() for e in self.pii_entities.split(",") if e.strip()]

    @property
    def blocked_hosts_set(self) -> set[str]:
        return {h.strip() for h in self.blocked_ai_hosts.split(",") if h.strip()}

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.dashboard_allowed_origins.split(",") if o.strip()]


settings = Settings()
