"""
ModelToll Admin Dashboard API
──────────────────────────────
REST endpoints consumed by the enterprise admin dashboard.

Sections:
  • /dashboard/summary     — overall KPIs (cost, savings, requests)
  • /dashboard/logs        — paginated audit log with filters
  • /dashboard/top-models  — which models are being requested/routed
  • /dashboard/savings     — time-series cost arbitrage data
  • /dashboard/tenants     — multi-tenant summary (for MSPs)
  • /health                — liveness / readiness probe
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.audit.models import AuditLog, DailyCostSummary, RequestAction
from src.config.settings import settings

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
health_router = APIRouter(tags=["health"])

_api_key_header = APIKeyHeader(name="X-Admin-Api-Key", auto_error=True)


# ── Auth ────────────────────────────────────────────────────────────────────────

def _verify_api_key(api_key: str = Security(_api_key_header)) -> str:
    if api_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Invalid admin API key")
    return api_key


def _get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.session_factory


# ── Response schemas ────────────────────────────────────────────────────────────

class SummaryResponse(BaseModel):
    period_days: int
    total_requests: int
    forwarded_requests: int
    blocked_requests: int
    scrubbed_requests: int
    total_input_tokens: int
    total_output_tokens: int
    source_cost_usd: float
    target_cost_usd: float
    total_savings_usd: float
    modeltoll_fee_usd: float
    savings_percent: float
    top_entity_types: list[str]


class AuditLogEntry(BaseModel):
    id: str
    created_at: datetime
    tenant_id: str
    user_id: str | None
    original_host: str
    original_model: str | None
    action: str
    routed_model: str | None
    routed_provider: str | None
    scrubber_triggered: bool
    scrubber_detection_count: int
    scrubber_entity_types: list[str] | None
    input_tokens: int
    output_tokens: int
    savings_usd: float
    savings_percent: float
    latency_ms: int
    response_status: int | None


class AuditLogPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AuditLogEntry]


class ModelUsageItem(BaseModel):
    model: str
    request_count: int
    total_input_tokens: int
    total_savings_usd: float


class DailySavingsItem(BaseModel):
    date: str
    total_requests: int
    total_savings_usd: float
    modeltoll_fee_usd: float
    source_cost_usd: float
    target_cost_usd: float


# ── Endpoints ──────────────────────────────────────────────────────────────────

@health_router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": settings.app_version}


@router.get("/summary", response_model=SummaryResponse)
async def get_summary(
    tenant_id: str = Query(default="default"),
    days: int = Query(default=30, ge=1, le=365),
    _: str = Depends(_verify_api_key),
    session_factory: async_sessionmaker[AsyncSession] = Depends(_get_session_factory),
) -> SummaryResponse:
    since = datetime.now(UTC) - timedelta(days=days)

    async with session_factory() as session:
        result = await session.execute(
            select(
                func.count(AuditLog.id).label("total"),
                func.sum(func.cast(AuditLog.action == RequestAction.FORWARDED, type_=func.count().type)).label("forwarded"),
                func.sum(func.cast(AuditLog.action == RequestAction.BLOCKED, type_=func.count().type)).label("blocked"),
                func.sum(func.cast(AuditLog.scrubber_triggered, type_=func.count().type)).label("scrubbed"),
                func.coalesce(func.sum(AuditLog.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(AuditLog.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(AuditLog.source_cost_usd), 0).label("source_cost"),
                func.coalesce(func.sum(AuditLog.target_cost_usd), 0).label("target_cost"),
                func.coalesce(func.sum(AuditLog.savings_usd), 0).label("savings"),
            ).where(
                AuditLog.tenant_id == tenant_id,
                AuditLog.created_at >= since,
            )
        )
        row = result.one()

    total = row.total or 0
    source_cost = float(row.source_cost or 0)
    savings = float(row.savings or 0)
    fee = savings * (settings.savings_share_percent / 100.0)
    savings_pct = (savings / source_cost * 100) if source_cost > 0 else 0.0

    return SummaryResponse(
        period_days=days,
        total_requests=total,
        forwarded_requests=int(row.forwarded or 0),
        blocked_requests=int(row.blocked or 0),
        scrubbed_requests=int(row.scrubbed or 0),
        total_input_tokens=int(row.input_tokens or 0),
        total_output_tokens=int(row.output_tokens or 0),
        source_cost_usd=source_cost,
        target_cost_usd=float(row.target_cost or 0),
        total_savings_usd=savings,
        modeltoll_fee_usd=round(fee, 4),
        savings_percent=round(savings_pct, 2),
        top_entity_types=[],
    )


@router.get("/logs", response_model=AuditLogPage)
async def get_audit_logs(
    tenant_id: str = Query(default="default"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    action: str | None = Query(default=None),
    scrubbed_only: bool = Query(default=False),
    _: str = Depends(_verify_api_key),
    session_factory: async_sessionmaker[AsyncSession] = Depends(_get_session_factory),
) -> AuditLogPage:
    offset = (page - 1) * page_size

    base_query = select(AuditLog).where(AuditLog.tenant_id == tenant_id)
    count_query = select(func.count(AuditLog.id)).where(AuditLog.tenant_id == tenant_id)

    if action:
        try:
            action_enum = RequestAction(action.upper())
            base_query = base_query.where(AuditLog.action == action_enum)
            count_query = count_query.where(AuditLog.action == action_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid action: {action}")

    if scrubbed_only:
        base_query = base_query.where(AuditLog.scrubber_triggered.is_(True))
        count_query = count_query.where(AuditLog.scrubber_triggered.is_(True))

    base_query = base_query.order_by(desc(AuditLog.created_at)).offset(offset).limit(page_size)

    async with session_factory() as session:
        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

        items_result = await session.execute(base_query)
        items = items_result.scalars().all()

    return AuditLogPage(
        total=total,
        page=page,
        page_size=page_size,
        items=[
            AuditLogEntry(
                id=str(i.id),
                created_at=i.created_at,
                tenant_id=i.tenant_id,
                user_id=i.user_id,
                original_host=i.original_host,
                original_model=i.original_model,
                action=i.action.value,
                routed_model=i.routed_model,
                routed_provider=i.routed_provider,
                scrubber_triggered=i.scrubber_triggered,
                scrubber_detection_count=i.scrubber_detection_count,
                scrubber_entity_types=i.scrubber_entity_types,
                input_tokens=i.input_tokens,
                output_tokens=i.output_tokens,
                savings_usd=i.savings_usd,
                savings_percent=i.savings_percent,
                latency_ms=i.latency_ms,
                response_status=i.response_status,
            )
            for i in items
        ],
    )


@router.get("/top-models", response_model=list[ModelUsageItem])
async def get_top_models(
    tenant_id: str = Query(default="default"),
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=50),
    _: str = Depends(_verify_api_key),
    session_factory: async_sessionmaker[AsyncSession] = Depends(_get_session_factory),
) -> list[ModelUsageItem]:
    since = datetime.now(UTC) - timedelta(days=days)

    async with session_factory() as session:
        result = await session.execute(
            select(
                AuditLog.original_model,
                func.count(AuditLog.id).label("cnt"),
                func.coalesce(func.sum(AuditLog.input_tokens), 0).label("tokens"),
                func.coalesce(func.sum(AuditLog.savings_usd), 0).label("savings"),
            )
            .where(
                AuditLog.tenant_id == tenant_id,
                AuditLog.created_at >= since,
                AuditLog.original_model.isnot(None),
            )
            .group_by(AuditLog.original_model)
            .order_by(desc("cnt"))
            .limit(limit)
        )
        rows = result.all()

    return [
        ModelUsageItem(
            model=r.original_model or "unknown",
            request_count=r.cnt,
            total_input_tokens=int(r.tokens),
            total_savings_usd=float(r.savings),
        )
        for r in rows
    ]


@router.get("/savings", response_model=list[DailySavingsItem])
async def get_savings_timeseries(
    tenant_id: str = Query(default="default"),
    days: int = Query(default=30, ge=1, le=365),
    _: str = Depends(_verify_api_key),
    session_factory: async_sessionmaker[AsyncSession] = Depends(_get_session_factory),
) -> list[DailySavingsItem]:
    since = datetime.now(UTC) - timedelta(days=days)

    async with session_factory() as session:
        result = await session.execute(
            select(DailyCostSummary)
            .where(
                DailyCostSummary.tenant_id == tenant_id,
                DailyCostSummary.date >= since,
            )
            .order_by(DailyCostSummary.date)
        )
        rows = result.scalars().all()

    return [
        DailySavingsItem(
            date=r.date.strftime("%Y-%m-%d"),
            total_requests=r.total_requests,
            total_savings_usd=r.total_savings_usd,
            modeltoll_fee_usd=r.modeltoll_fee_usd,
            source_cost_usd=r.source_cost_usd,
            target_cost_usd=r.target_cost_usd,
        )
        for r in rows
    ]
