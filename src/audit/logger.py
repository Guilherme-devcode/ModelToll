"""
ModelToll Audit Logger
──────────────────────
Async writer for audit log entries. Uses SQLAlchemy async session with
a background queue to avoid adding latency to the proxy hot path.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.audit.models import AuditLog, Base, DailyCostSummary, RequestAction

log = structlog.get_logger(__name__)

_QUEUE_MAXSIZE = 10_000


class AuditLogger:
    """
    Non-blocking audit logger backed by a bounded asyncio queue.

    A background worker drains the queue and writes to PostgreSQL.
    If the DB is unavailable the entries are silently dropped after
    logging an error — audit must never block the proxy response.
    """

    def __init__(self, database_url: str, savings_share_percent: float = 20.0) -> None:
        self._engine = create_async_engine(database_url, pool_size=5, max_overflow=10)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)
        self._savings_share = savings_share_percent / 100.0
        self._queue: asyncio.Queue[AuditLog] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._worker_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self._worker_task = asyncio.create_task(self._drain_queue(), name="audit-worker")
        log.info("audit_logger_started")

    async def stop(self) -> None:
        if self._worker_task:
            self._worker_task.cancel()
        await self._engine.dispose()
        log.info("audit_logger_stopped")

    # ── Public write API ───────────────────────────────────────────────────────

    def record(self, entry: AuditLog) -> None:
        """Fire-and-forget: enqueue an audit entry without blocking the caller."""
        try:
            self._queue.put_nowait(entry)
        except asyncio.QueueFull:
            log.error("audit_queue_full_entry_dropped", entry_id=str(entry.id))

    def build_entry(
        self,
        *,
        tenant_id: str,
        original_host: str,
        action: RequestAction,
        user_id: str | None = None,
        user_email: str | None = None,
        session_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        original_model: str | None = None,
        original_endpoint: str | None = None,
        input_tokens: int = 0,
        scrubber_triggered: bool = False,
        scrubber_detection_count: int = 0,
        scrubber_entity_types: list[str] | None = None,
        routed_model: str | None = None,
        routed_provider: str | None = None,
        route_reason: str | None = None,
        output_tokens: int = 0,
        latency_ms: int = 0,
        response_status: int | None = None,
        source_cost_usd: float = 0.0,
        target_cost_usd: float = 0.0,
        savings_usd: float = 0.0,
        savings_percent: float = 0.0,
        extra: dict[str, Any] | None = None,
    ) -> AuditLog:
        return AuditLog(
            id=uuid.uuid4(),
            created_at=datetime.now(UTC),
            tenant_id=tenant_id,
            user_id=user_id,
            user_email=user_email,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            original_host=original_host,
            original_model=original_model,
            original_endpoint=original_endpoint,
            input_tokens=input_tokens,
            scrubber_triggered=scrubber_triggered,
            scrubber_detection_count=scrubber_detection_count,
            scrubber_entity_types=scrubber_entity_types,
            action=action,
            routed_model=routed_model,
            routed_provider=routed_provider,
            route_reason=route_reason,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            response_status=response_status,
            source_cost_usd=source_cost_usd,
            target_cost_usd=target_cost_usd,
            savings_usd=savings_usd,
            savings_percent=savings_percent,
            extra=extra,
        )

    # ── Background worker ──────────────────────────────────────────────────────

    async def _drain_queue(self) -> None:
        while True:
            entry = await self._queue.get()
            try:
                async with self._session_factory() as session:
                    session.add(entry)
                    await session.commit()
                    await self._upsert_daily_summary(session, entry)
            except Exception as exc:
                log.error("audit_write_failed", error=str(exc), entry_id=str(entry.id))
            finally:
                self._queue.task_done()

    async def _upsert_daily_summary(self, session: AsyncSession, entry: AuditLog) -> None:
        """Increment or create the DailyCostSummary for the entry's day."""
        from sqlalchemy import select, text

        day = entry.created_at.date()
        modeltoll_fee = entry.savings_usd * self._savings_share

        await session.execute(
            text(
                """
                INSERT INTO daily_cost_summaries
                    (tenant_id, date, total_requests, forwarded_requests, blocked_requests,
                     scrubbed_requests, total_input_tokens, total_output_tokens,
                     source_cost_usd, target_cost_usd, total_savings_usd, modeltoll_fee_usd)
                VALUES
                    (:tenant, :date, 1,
                     :fwd, :blk, :scr,
                     :inp, :out,
                     :src_cost, :tgt_cost, :savings, :fee)
                ON CONFLICT (tenant_id, date) DO UPDATE SET
                    total_requests       = daily_cost_summaries.total_requests + 1,
                    forwarded_requests   = daily_cost_summaries.forwarded_requests + :fwd,
                    blocked_requests     = daily_cost_summaries.blocked_requests + :blk,
                    scrubbed_requests    = daily_cost_summaries.scrubbed_requests + :scr,
                    total_input_tokens   = daily_cost_summaries.total_input_tokens + :inp,
                    total_output_tokens  = daily_cost_summaries.total_output_tokens + :out,
                    source_cost_usd      = daily_cost_summaries.source_cost_usd + :src_cost,
                    target_cost_usd      = daily_cost_summaries.target_cost_usd + :tgt_cost,
                    total_savings_usd    = daily_cost_summaries.total_savings_usd + :savings,
                    modeltoll_fee_usd    = daily_cost_summaries.modeltoll_fee_usd + :fee,
                    updated_at           = now()
                """
            ),
            {
                "tenant": entry.tenant_id,
                "date": day,
                "fwd": 1 if entry.action == RequestAction.FORWARDED else 0,
                "blk": 1 if entry.action == RequestAction.BLOCKED else 0,
                "scr": 1 if entry.scrubber_triggered else 0,
                "inp": entry.input_tokens,
                "out": entry.output_tokens,
                "src_cost": entry.source_cost_usd,
                "tgt_cost": entry.target_cost_usd,
                "savings": entry.savings_usd,
                "fee": modeltoll_fee,
            },
        )
        await session.commit()
