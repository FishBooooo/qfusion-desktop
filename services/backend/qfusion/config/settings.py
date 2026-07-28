"""Environment-backed settings loaded only at the application boundary."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated settings for the local M0 backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="QFUSION_",
        extra="ignore",
        frozen=True,
    )

    app_name: str = "QFusion Backend"
    environment: Literal["development", "test", "production"] = "development"
    host: Literal["127.0.0.1"] = "127.0.0.1"
    port: int = Field(default=8000, ge=1024, le=65535)
    log_level: Literal["critical", "error", "warning", "info", "debug"] = "info"
    llm_mode: Literal["off", "local", "hybrid", "cloud"] = "off"
    allowed_origins: tuple[str, ...] = (
        "http://127.0.0.1:1420",
        "http://localhost:1420",
        "tauri://localhost",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache validated process configuration."""
    return Settings()
