"""FastAPI application composition root."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from qfusion import __version__
from qfusion.api.routes.health import router as health_router
from qfusion.config.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the local API with explicitly supplied or boundary-loaded settings."""
    resolved_settings = settings or get_settings()
    application = FastAPI(
        title=resolved_settings.app_name,
        summary="Local API for QFusion Desktop",
        description=(
            "M0 health endpoint only. This API contains no live market data or order submission."
        ),
        version=__version__,
        docs_url="/docs" if resolved_settings.environment == "development" else None,
        redoc_url=None,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "X-QFusion-Session"],
    )
    application.include_router(health_router)
    return application


app = create_app()
