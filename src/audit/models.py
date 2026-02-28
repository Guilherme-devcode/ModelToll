"""
SQLAlchemy ORM models for ModelToll audit log and cost tracking.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RequestAction(str, PyEnum):
    FORWARDED = "FORWARDED"      # Scrubbed + rerouted to approved model
    BLOCKED = "BLOCKED"          # Blocked by policy
    PASSTHROUGH = "PASSTHROUGH"  # Allowed to pass through unchanged


class AuditLog(Base):
    """One row per intercepted AI request."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    # ── Identity ───────────────────────────────────────────────────────────────
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    user_id: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    user_email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # ── Original request ───────────────────────────────────────────────────────
    original_host: Mapped[str] = mapped_column(String(256))
    original_model: Mapped[str | None] = mapped_column(String(256), nullable=True)
    original_endpoint: Mapped[str | None] = mapped_column(String(512), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)

    # ── Scrubber ───────────────────────────────────────────────────────────────
    scrubber_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    scrubber_detection_count: Mapped[int] = mapped_column(Integer, default=0)
    scrubber_entity_types: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # ── Routing ────────────────────────────────────────────────────────────────
    action: Mapped[RequestAction] = mapped_column(
        Enum(RequestAction), default=RequestAction.FORWARDED
    )
    routed_model: Mapped[str | None] = mapped_column(String(256), nullable=True)
    routed_provider: Mapped[str | None] = mapped_column(String(128), nullable=True)
    route_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # ── Response ───────────────────────────────────────────────────────────────
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Cost arbitrage ─────────────────────────────────────────────────────────
    source_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    target_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    savings_usd: Mapped[float] = mapped_column(Float, default=0.0)
    savings_percent: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Extra metadata ─────────────────────────────────────────────────────────
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class DailyCostSummary(Base):
    """Aggregated daily cost savings per tenant — pre-computed for dashboard performance."""

    __tablename__ = "daily_cost_summaries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "date", name="uq_daily_cost_tenant_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    total_requests: Mapped[int] = mapped_column(Integer, default=0)
    forwarded_requests: Mapped[int] = mapped_column(Integer, default=0)
    blocked_requests: Mapped[int] = mapped_column(Integer, default=0)
    scrubbed_requests: Mapped[int] = mapped_column(Integer, default=0)

    total_input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    total_output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)

    source_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    target_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    total_savings_usd: Mapped[float] = mapped_column(Float, default=0.0)

    modeltoll_fee_usd: Mapped[float] = mapped_column(Float, default=0.0)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
