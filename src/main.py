"""
ModelToll — Application Entry Point
─────────────────────────────────────
Wires together:
  • FastAPI app with proxy + dashboard routers
  • Shared singleton instances (scrubber, router, audit logger)
  • Lifespan startup / shutdown
  • Structured logging
  • Prometheus metrics (optional)
"""

from __future__ import annotations

import logging

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.audit.logger import AuditLogger
from src.config.settings import settings
from src.dashboard.api import health_router, router as dashboard_router
from src.proxy.gateway import ProxyGateway
from src.proxy.routes import router as proxy_router
from src.router.model_router import ModelRouter
from src.scrubber.engine import ScrubberEngine


# ── Logging ────────────────────────────────────────────────────────────────────

def _configure_logging() -> None:
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.log_level.value),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if settings.environment == "development"
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.value)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
    )


# ── App factory ────────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    _configure_logging()

    log = structlog.get_logger(__name__)

    # Build shared services (lazy — heavy models loaded on first use)
    scrubber = ScrubberEngine.from_settings(settings)
    router = ModelRouter.from_config(
        settings.model_routing_config_path,
        default_model=settings.default_approved_model,
    )
    audit = AuditLogger(
        database_url=settings.database_url,
        savings_share_percent=settings.savings_share_percent,
    )
    engine = create_async_engine(settings.database_url, pool_size=5, max_overflow=10)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # FastAPI application
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "ModelToll — intelligent AI gateway. "
            "Intercept, scrub, route, and audit enterprise AI usage."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS (for the admin dashboard SPA)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Optional Prometheus metrics
    if settings.metrics_enabled:
        try:
            from prometheus_client import make_asgi_app  # type: ignore[import]
            from starlette.routing import Mount

            metrics_app = make_asgi_app()
            app.mount("/metrics", metrics_app)
            log.info("prometheus_metrics_enabled")
        except ImportError:
            log.warning("prometheus_client_not_installed")

    # Routers
    app.include_router(health_router)
    app.include_router(proxy_router)
    app.include_router(dashboard_router)

    # Lifespan
    @app.on_event("startup")
    async def on_startup() -> None:
        await audit.start()
        app.state.gateway = ProxyGateway(
            settings=settings,
            scrubber=scrubber,
            router=router,
            audit=audit,
        )
        app.state.session_factory = session_factory
        log.info(
            "modeltoll_started",
            version=settings.app_version,
            environment=settings.environment,
            host=settings.host,
            port=settings.port,
        )

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        await app.state.gateway.close()
        await audit.stop()
        await engine.dispose()
        log.info("modeltoll_stopped")

    return app


app = create_app()


def main() -> None:
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
        log_level=settings.log_level.value.lower(),
        reload=settings.environment == "development",
    )


if __name__ == "__main__":
    main()
