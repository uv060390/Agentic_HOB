"""
src/gateway/app.py  (AM-21)

FastAPI application entry point for the BrandOS Gateway.
Handles lifespan (startup/shutdown), mounts routes, and exposes /health.

Run locally:
    uvicorn src.gateway.app:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from src.shared.config import get_settings
from src.shared.db import close_engine, get_db
from src.shared.schemas import ApiResponse, HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle hook."""
    settings = get_settings()

    # Startup — start heartbeat scheduler
    import logging
    logger = logging.getLogger(__name__)
    try:
        from src.core.heartbeat import start_scheduler, stop_scheduler
        await start_scheduler()
        logger.info("Heartbeat scheduler started")
    except Exception as exc:
        logger.warning("Heartbeat scheduler failed to start: %s", exc)

    yield

    # Shutdown — stop scheduler and dispose DB connection pool
    try:
        from src.core.heartbeat import stop_scheduler
        await stop_scheduler()
    except Exception:
        pass
    await close_engine()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="BrandOS Gateway",
        description="AI-agent operating system for D2C brands.",
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if not settings.is_production else [],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Health endpoint (no auth required) ────────────────────────────────────

    @app.get("/health", response_model=ApiResponse[HealthResponse], tags=["ops"])
    async def health() -> ApiResponse[HealthResponse]:
        """Liveness probe — checks gateway and database connectivity."""
        db_status = "unknown"
        try:
            async with get_db() as session:
                await session.execute(text("SELECT 1"))
            db_status = "ok"
        except Exception as exc:
            db_status = f"error: {exc}"

        return ApiResponse.success(
            HealthResponse(
                status="ok",
                env=settings.brandos_env,
                db=db_status,
            )
        )

    # ── Mount route modules ──────────────────────────────────────────────────
    from src.gateway.routes.whatsapp import router as whatsapp_router
    from src.gateway.routes.telegram import router as telegram_router

    app.include_router(whatsapp_router)
    app.include_router(telegram_router)

    # Mount onboarding routes if available
    try:
        from src.gateway.routes.onboarding import router as onboarding_router
        app.include_router(onboarding_router)
    except ImportError:
        pass

    return app


app = create_app()
