"""SEC-specific request and transport contracts without vendor SDK types."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import Field, JsonValue, StringConstraints, field_validator, model_validator

from qfusion.domain import Market
from qfusion.providers.contracts import (
    NonEmptyText,
    ProviderAccessProfile,
    ProviderCapability,
    ProviderContract,
    ProviderOperation,
    validate_provider_access,
)

SecCik = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^\d{10}$"),
]
UserAgentText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=8, max_length=256),
]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("SEC timestamps must be timezone-aware")
    return value.astimezone(UTC)


class SecFilingRequest(ProviderContract):
    """Point-in-Time request for one registry-resolved SEC filer."""

    instrument_id: UUID
    provider_instrument_id: SecCik
    market: Market
    forms: tuple[NonEmptyText, ...] = ()
    limit: int = Field(default=1000, ge=1, le=1000)

    @field_validator("forms")
    @classmethod
    def normalize_forms(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(value.strip().upper() for value in values)
        if len(normalized) != len(set(normalized)):
            raise ValueError("forms must be unique")
        return tuple(sorted(normalized))

    @model_validator(mode="after")
    def require_us_market(self) -> Self:
        if self.market is not Market.US:
            raise ValueError("SEC EDGAR filing requests require the US market")
        return self

    @property
    def cik(self) -> str:
        """Return the exact ten-digit CIK used in the fixed SEC path."""

        return self.provider_instrument_id


class SecTransportConfig(ProviderContract):
    """Bounded, no-proxy configuration for the public SEC origin."""

    user_agent: UserAgentText
    timeout_seconds: float = Field(default=10.0, ge=1.0, le=60.0)
    max_attempts: int = Field(default=3, ge=1, le=4)
    max_retry_delay_seconds: float = Field(default=2.0, ge=0.0, le=10.0)
    max_requests_per_second: int = Field(default=5, ge=1, le=5)
    max_response_bytes: int = Field(
        default=10 * 1024 * 1024,
        ge=1024,
        le=50 * 1024 * 1024,
    )

    @field_validator("user_agent")
    @classmethod
    def validate_declared_user_agent(cls, value: str) -> str:
        if "\r" in value or "\n" in value:
            raise ValueError("SEC User-Agent must not contain line breaks")
        if "@" not in value or len(value.split()) < 2:
            raise ValueError("SEC User-Agent must include a product name and contact email")
        return value


class SecJsonResponse(ProviderContract):
    """One exact SEC response body plus its validated decoded representation."""

    payload: dict[str, JsonValue]
    raw_body: bytes = Field(min_length=2, max_length=50 * 1024 * 1024, repr=False)
    received_at: datetime
    content_type: str | None = Field(default=None, min_length=1, max_length=256)
    etag: str | None = Field(default=None, min_length=1, max_length=512)
    last_modified: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("received_at")
    @classmethod
    def normalize_received_at(cls, value: datetime) -> datetime:
        return _as_utc(value)

    @model_validator(mode="after")
    def require_raw_body_payload_equivalence(self) -> Self:
        try:
            decoded: object = json.loads(self.raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError("SEC raw body must contain valid JSON") from error
        if not isinstance(decoded, dict) or not all(
            isinstance(key, str) for key in decoded
        ):
            raise ValueError("SEC raw body must contain a JSON object")
        if decoded != self.payload:
            raise ValueError("SEC raw body does not match the decoded payload")
        return self

    @property
    def raw_body_sha256(self) -> str:
        """Return the audit digest of the exact received response bytes."""

        return hashlib.sha256(
            self.raw_body,
            usedforsecurity=False,
        ).hexdigest()

    @property
    def raw_body_size(self) -> int:
        """Return the exact response byte count."""

        return len(self.raw_body)


def validate_sec_filing_request(
    capability: ProviderCapability,
    access: ProviderAccessProfile,
    request: SecFilingRequest,
) -> SecFilingRequest:
    """Reject requests outside both the adapter and public-access declarations."""

    validate_provider_access(capability, access)
    if ProviderOperation.FILINGS not in capability.operations:
        raise ValueError("provider does not implement filings")
    if ProviderOperation.FILINGS not in access.enabled_operations:
        raise PermissionError("current provider access does not enable filings")
    if request.market not in capability.supported_markets:
        raise ValueError("provider does not support the requested market")
    return request
