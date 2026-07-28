"""System health response contract."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Non-sensitive health metadata returned to the desktop shell."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["ok"]
    service: str
    version: str
    api_version: Literal["v1"]
    execution_mode: Literal["research"]
    data_mode: Literal["synthetic-m0"]
    llm_mode: Literal["off", "local", "hybrid", "cloud"]
