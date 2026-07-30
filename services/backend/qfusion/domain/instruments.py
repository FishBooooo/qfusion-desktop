"""Permanent instrument identities and Point-in-Time identifier contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID

from pydantic import StringConstraints, field_validator, model_validator

from qfusion.domain.contracts import DomainContract, Market, NonEmptyText, _as_utc

DisplayName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256),
]
TickerText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=32),
]
OpaqueIdentifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=256),
]
_ALLOWED_TICKER_CHARACTERS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-/"
)


def _normalize_ticker(value: str) -> str:
    normalized = value.strip().upper()
    if any(character.isspace() for character in normalized):
        raise ValueError("ticker must not contain whitespace")
    if any(character not in _ALLOWED_TICKER_CHARACTERS for character in normalized):
        raise ValueError("ticker contains unsupported characters")
    return normalized


def _normalize_provider_name(value: str) -> str:
    return value.strip().casefold()


def _normalize_opaque_identifier(value: str) -> str:
    normalized = value.strip()
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise ValueError("provider_instrument_id must not contain control characters")
    return normalized


class InstrumentAssetType(StrEnum):
    """Static first-phase security types owned by the instrument registry."""

    STOCK = "stock"
    ADR = "adr"
    ETF = "etf"
    SECTOR_ETF = "sector_etf"


class Instrument(DomainContract):
    """Permanent internal identity that never uses ticker as its primary key."""

    schema_version: Annotated[str, StringConstraints(pattern=r"^1\.0\.0$")] = "1.0.0"
    instrument_id: UUID
    market: Market
    asset_type: InstrumentAssetType
    display_name: DisplayName
    source: NonEmptyText
    source_record_id: NonEmptyText
    source_version: NonEmptyText
    revision_id: NonEmptyText
    registered_at: datetime

    @field_validator("registered_at")
    @classmethod
    def normalize_registered_at(cls, value: datetime) -> datetime:
        return _as_utc(value)

    def is_available_at(self, decision_time: datetime) -> bool:
        """Return whether the permanent identity was registered by a decision time."""

        return self.registered_at <= _as_utc(decision_time)


class EffectiveIdentifier(DomainContract):
    """Shared immutable effective and knowledge interval for external identifiers."""

    instrument_id: UUID
    market: Market
    valid_from: datetime
    valid_to: datetime | None = None
    available_at: datetime
    source_record_id: NonEmptyText
    revision_id: NonEmptyText

    @field_validator("valid_from", "valid_to", "available_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _as_utc(value)

    @model_validator(mode="after")
    def validate_effective_interval(self) -> Self:
        if self.valid_to is not None and self.valid_from >= self.valid_to:
            raise ValueError("valid_from must be earlier than valid_to")
        return self

    def is_effective_at(self, effective_at: datetime) -> bool:
        """Apply the half-open market-validity interval."""

        normalized = _as_utc(effective_at)
        return self.valid_from <= normalized and (
            self.valid_to is None or normalized < self.valid_to
        )

    def is_available_at(self, decision_time: datetime) -> bool:
        """Return whether the mapping was known by a decision time."""

        return self.available_at <= _as_utc(decision_time)


class TickerAlias(EffectiveIdentifier):
    """One market ticker alias over an explicit half-open validity interval."""

    schema_version: Annotated[str, StringConstraints(pattern=r"^1\.0\.0$")] = "1.0.0"
    alias_id: UUID
    ticker: TickerText
    source: NonEmptyText
    source_version: NonEmptyText

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return _normalize_ticker(value)


class ProviderInstrumentMapping(EffectiveIdentifier):
    """Case-preserving opaque provider identifier bound to one internal UUID."""

    schema_version: Annotated[str, StringConstraints(pattern=r"^1\.0\.0$")] = "1.0.0"
    mapping_id: UUID
    provider_name: NonEmptyText
    provider_instrument_id: OpaqueIdentifier
    provider_version: NonEmptyText

    @field_validator("provider_name")
    @classmethod
    def normalize_provider_name(cls, value: str) -> str:
        return _normalize_provider_name(value)

    @field_validator("provider_instrument_id")
    @classmethod
    def validate_opaque_identifier(cls, value: str) -> str:
        return _normalize_opaque_identifier(value)


class InstrumentQuery(DomainContract):
    """Point-in-Time lookup of one permanent identity."""

    instrument_id: UUID
    decision_time: datetime

    @field_validator("decision_time")
    @classmethod
    def normalize_decision_time(cls, value: datetime) -> datetime:
        return _as_utc(value)


class EffectiveLookup(DomainContract):
    """Common temporal boundary for identifier resolution."""

    market: Market
    effective_at: datetime
    decision_time: datetime

    @field_validator("effective_at", "decision_time")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _as_utc(value)

    @model_validator(mode="after")
    def validate_lookup_timeline(self) -> Self:
        if self.effective_at > self.decision_time:
            raise ValueError("effective_at must not be after decision_time")
        return self


class TickerLookup(EffectiveLookup):
    """Resolve one normalized ticker in one market and decision context."""

    ticker: TickerText

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return _normalize_ticker(value)


class ProviderIdentifierLookup(EffectiveLookup):
    """Resolve one exact opaque provider identifier to an internal instrument."""

    provider_name: NonEmptyText
    provider_instrument_id: OpaqueIdentifier

    @field_validator("provider_name")
    @classmethod
    def normalize_provider_name(cls, value: str) -> str:
        return _normalize_provider_name(value)

    @field_validator("provider_instrument_id")
    @classmethod
    def validate_opaque_identifier(cls, value: str) -> str:
        return _normalize_opaque_identifier(value)


class ProviderMappingLookup(EffectiveLookup):
    """Resolve the provider identifier valid for one internal instrument."""

    instrument_id: UUID
    provider_name: NonEmptyText

    @field_validator("provider_name")
    @classmethod
    def normalize_provider_name(cls, value: str) -> str:
        return _normalize_provider_name(value)


def require_instrument_available(
    query: InstrumentQuery,
    instrument: Instrument,
) -> Instrument:
    """Reject a Repository result unavailable at the explicit decision time."""

    if instrument.instrument_id != query.instrument_id:
        raise ValueError("repository returned a different instrument_id")
    if not instrument.is_available_at(query.decision_time):
        raise ValueError("repository returned an instrument unavailable at decision_time")
    return instrument


def require_ticker_match(query: TickerLookup, alias: TickerAlias) -> TickerAlias:
    """Reject a ticker result outside lookup identity or Point-in-Time boundaries."""

    if alias.market is not query.market or alias.ticker != query.ticker:
        raise ValueError("repository returned a ticker alias outside the lookup key")
    if not alias.is_effective_at(query.effective_at):
        raise ValueError("repository returned a ticker alias outside effective_at")
    if not alias.is_available_at(query.decision_time):
        raise ValueError("repository returned a ticker alias unavailable at decision_time")
    return alias


def require_provider_identifier_match(
    query: ProviderIdentifierLookup,
    mapping: ProviderInstrumentMapping,
) -> ProviderInstrumentMapping:
    """Reject a provider-ID result outside identity or Point-in-Time boundaries."""

    if (
        mapping.market is not query.market
        or mapping.provider_name != query.provider_name
        or mapping.provider_instrument_id != query.provider_instrument_id
    ):
        raise ValueError("repository returned a provider mapping outside the lookup key")
    if not mapping.is_effective_at(query.effective_at):
        raise ValueError("repository returned a provider mapping outside effective_at")
    if not mapping.is_available_at(query.decision_time):
        raise ValueError("repository returned a provider mapping unavailable at decision_time")
    return mapping


def require_provider_mapping_match(
    query: ProviderMappingLookup,
    mapping: ProviderInstrumentMapping,
) -> ProviderInstrumentMapping:
    """Reject an instrument-to-provider result outside all requested boundaries."""

    if (
        mapping.instrument_id != query.instrument_id
        or mapping.market is not query.market
        or mapping.provider_name != query.provider_name
    ):
        raise ValueError("repository returned a provider mapping outside the instrument key")
    if not mapping.is_effective_at(query.effective_at):
        raise ValueError("repository returned a provider mapping outside effective_at")
    if not mapping.is_available_at(query.decision_time):
        raise ValueError("repository returned a provider mapping unavailable at decision_time")
    return mapping
