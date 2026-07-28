"""Health route used by the desktop shell."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from qfusion import __version__
from qfusion.api.schemas.health import HealthResponse
from qfusion.config.settings import Settings, get_settings

router = APIRouter(prefix="/api/v1", tags=["system"])
SettingsDependency = Annotated[Settings, Depends(get_settings)]


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check whether the local M0 backend is responsive",
)
def get_health(settings: SettingsDependency) -> HealthResponse:
    """Return non-sensitive process metadata for the desktop connection check."""
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=__version__,
        api_version="v1",
        execution_mode="research",
        data_mode="synthetic-m0",
        llm_mode=settings.llm_mode,
    )
