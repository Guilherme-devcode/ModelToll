"""
FastAPI route definitions for the ModelToll proxy gateway.

Intercept patterns:
  • POST /v1/chat/completions        — OpenAI-compatible
  • POST /v1/messages                — Anthropic-compatible
  • POST /v1beta/models/*/generateContent — Google Gemini-compatible
  • POST /proxy/{path:path}          — Generic catch-all
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request, Response

from src.proxy.gateway import ProxyGateway

router = APIRouter(tags=["proxy"])


def _get_tenant(x_tenant_id: str = Header(default="default")) -> str:
    """Extract tenant ID from request header (set by the enterprise integration layer)."""
    return x_tenant_id


# ── OpenAI-compatible endpoints ────────────────────────────────────────────────

@router.post("/v1/chat/completions")
async def openai_chat(
    request: Request,
    tenant_id: str = Depends(_get_tenant),
) -> Response:
    gw: ProxyGateway = request.app.state.gateway
    return await gw.handle(request, tenant_id=tenant_id)


@router.post("/v1/completions")
async def openai_completions(
    request: Request,
    tenant_id: str = Depends(_get_tenant),
) -> Response:
    gw: ProxyGateway = request.app.state.gateway
    return await gw.handle(request, tenant_id=tenant_id)


@router.post("/v1/embeddings")
async def openai_embeddings(
    request: Request,
    tenant_id: str = Depends(_get_tenant),
) -> Response:
    gw: ProxyGateway = request.app.state.gateway
    return await gw.handle(request, tenant_id=tenant_id)


# ── Anthropic-compatible endpoints ─────────────────────────────────────────────

@router.post("/v1/messages")
async def anthropic_messages(
    request: Request,
    tenant_id: str = Depends(_get_tenant),
) -> Response:
    gw: ProxyGateway = request.app.state.gateway
    return await gw.handle(request, tenant_id=tenant_id)


# ── Google Gemini-compatible endpoints ─────────────────────────────────────────

@router.post("/v1beta/models/{model_id:path}")
async def gemini_generate(
    request: Request,
    model_id: str,
    tenant_id: str = Depends(_get_tenant),
) -> Response:
    gw: ProxyGateway = request.app.state.gateway
    return await gw.handle(request, tenant_id=tenant_id)


# ── Generic catch-all proxy ────────────────────────────────────────────────────

@router.post("/proxy/{path:path}")
@router.get("/proxy/{path:path}")
async def proxy_catchall(
    request: Request,
    path: str,
    tenant_id: str = Depends(_get_tenant),
) -> Response:
    gw: ProxyGateway = request.app.state.gateway
    return await gw.handle(request, tenant_id=tenant_id)
