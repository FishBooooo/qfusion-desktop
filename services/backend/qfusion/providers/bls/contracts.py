"""BLS-specific request and transport contracts without API client types."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, Self

from pydantic import Field, JsonValue, StringConstraints, field_validator, model_validator

from qfusion.providers.contracts import (
    ProviderAccessProfile,
    ProviderCapability,
    ProviderContract,
    ProviderOperation,
    validate_provider_access,
)

BlsSeriesId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^[A-Z0-9_#-]{1,64}$",
    ),
]
BlsUserAgentText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=8, max_length=256),
]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("BLS timestamps must be timezone-aware")
    return value.astimezone(UTC)


class BlsSeriesRequest(ProviderContract):
    """One bounded, unregistered BLS v1 monthly-series request."""

    series_ids: tuple[BlsSeriesId, ...]
    start_year: int = Field(ge=1900, le=9999)
    end_year: int = Field(ge=1900, le=9999)

    @field_validator("series_ids")
    @classmethod
    def normalize_series_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("series_ids must not be empty")
        if len(values) > 25:
            raise ValueError("unregistered BLS v1 requests allow at most 25 series")
        if len(values) != len(set(values)):
            raise ValueError("series_ids must be unique")
        return tuple(sorted(values))

    @model_validator(mode="after")
    def validate_year_window(self) -> Self:
        if self.start_year > self.end_year:
            raise ValueError("start_year must not be after end_year")
        if self.end_year - self.start_year + 1 > 10:
            raise ValueError("unregistered BLS v1 requests allow at most 10 years")
        return self

    def api_payload(self) -> dict[str, object]:
        """Return the exact credential-free JSON body accepted by BLS v1."""

        return {
            "seriesid": list(self.series_ids),
            "startyear": str(self.start_year),
            "endyear": str(self.end_year),
        }


class BlsTransportConfig(ProviderContract):
    """Bounded, no-proxy configuration for the fixed BLS public origin."""

    user_agent: BlsUserAgentText
    timeout_seconds: float = Field(default=10.0, ge=1.0, le=60.0)
    max_attempts: int = Field(default=3, ge=1, le=4)
    max_retry_delay_seconds: float = Field(default=2.0, ge=0.0, le=10.0)
    max_response_bytes: int = Field(
        default=5 * 1024 * 1024,
        ge=1024,
        le=10 * 1024 * 1024,
    )
    max_requests_per_10_seconds: int = Field(default=5, ge=1, le=50)
    max_requests_per_day: int = Field(default=25, ge=1, le=25)

    @field_validator("user_agent")
    @classmethod
    def validate_declared_user_agent(cls, value: str) -> str:
        if "\r" in value or "\n" in value:
            raise ValueError("BLS User-Agent must not contain line breaks")
        if "@" not in value or len(value.split()) < 2:
            raise ValueError("BLS User-Agent must include a product name and contact email")
        return value


class BlsJsonResponse(ProviderContract):
    """One exact BLS response body plus its validated decoded representation."""

    payload: dict[str, JsonValue]
    raw_body: bytes = Field(min_length=2, max_length=10 * 1024 * 1024, repr=False)
    received_at: datetime
    content_type: str | None = Field(default=None, min_length=1, max_length=256)

    @field_validator("received_at")
    @classmethod
    def normalize_received_at(cls, value: datetime) -> datetime:
        return _as_utc(value)

    @model_validator(mode="after")
    def require_raw_body_payload_equivalence(self) -> Self:
        try:
            decoded: object = json.loads(self.raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError("BLS raw body must contain valid JSON") from error
        if not isinstance(decoded, dict) or not all(
            isinstance(key, str) for key in decoded
        ):
            raise ValueError("BLS raw body must contain a JSON object")
        if decoded != self.payload:
            raise ValueError("BLS raw body does not match the decoded payload")
        return self

    @property
    def raw_body_sha256(self) -> str:
        """Return the audit digest of the exact received response bytes."""

        return hashlib.sha256(self.raw_body, usedforsecurity=False).hexdigest()

    @property
    def raw_body_size(self) -> int:
        """Return the exact response byte count."""

        return len(self.raw_body)


def validate_bls_series_request(
    capability: ProviderCapability,
    access: ProviderAccessProfile,
    request: BlsSeriesRequest,
) -> BlsSeriesRequest:
    """Reject BLS requests outside both implementation and public-access declarations."""

    validate_provider_access(capability, access)
    if ProviderOperation.MACRO_SERIES not in capability.operations:
        raise ValueError("provider does not implement macro series")
    if ProviderOperation.MACRO_SERIES not in access.enabled_operations:
        raise PermissionError("current provider access does not enable macro series")
    return request
