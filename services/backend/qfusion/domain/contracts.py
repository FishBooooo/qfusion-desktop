"""Versioned, vendor-neutral Point-in-Time domain contracts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
    model_validator,
)

NonEmptyText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class Market(StrEnum):
    """Markets supported by the first QFusion phase."""

    US = "US"
    HK = "HK"


class TargetType(StrEnum):
    """Kinds of analysis targets."""

    STOCK = "stock"
    SECTOR = "sector"
    BASKET = "basket"


class RequestedHorizon(StrEnum):
    """Decision horizons supported by the first QFusion phase."""

    INTRADAY = "intraday"
    FIVE_DAY = "5d"
    TWENTY_DAY = "20d"
    THREE_MONTH = "3m"


class QualityFlag(StrEnum):
    """Explicit quality state for one source record."""

    OK = "OK"
    DELAYED = "DELAYED"
    STALE = "STALE"
    CONFLICT = "CONFLICT"
    MISSING = "MISSING"
    SYNTHETIC_MOCK = "SYNTHETIC_MOCK"


MARKET_TIMEZONES: dict[Market, str] = {
    Market.US: "America/New_York",
    Market.HK: "Asia/Hong_Kong",
}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("financial timestamps must be timezone-aware")
    return value.astimezone(UTC)


class DomainContract(BaseModel):
    """Immutable base for domain values crossing layer boundaries."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class DataSourceRecord(DomainContract):
    """Traceable wrapper around one vendor-neutral financial fact."""

    schema_version: Annotated[str, StringConstraints(pattern=r"^1\.0\.0$")] = "1.0.0"
    fact_id: UUID
    instrument_id: UUID | None = None
    fact_type: NonEmptyText
    source: NonEmptyText
    source_record_id: NonEmptyText
    source_quality_level: NonEmptyText
    venue_scope: NonEmptyText
    license_scope: NonEmptyText
    provider_version: NonEmptyText
    dataset_version: NonEmptyText

    event_time: datetime
    published_at: datetime
    available_at: datetime
    received_at: datetime
    ingested_at: datetime

    revision_id: NonEmptyText
    effective_from: datetime | None = None
    effective_to: datetime | None = None

    quality_flag: QualityFlag
    raw_payload_hash: Sha256Hex
    is_adjusted: bool = False
    adjustment_type: NonEmptyText | None = None
    payload: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator(
        "event_time",
        "published_at",
        "available_at",
        "received_at",
        "ingested_at",
        "effective_from",
        "effective_to",
    )
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        """Normalize every persisted timestamp to timezone-aware UTC."""

        return None if value is None else _as_utc(value)

    @model_validator(mode="after")
    def validate_temporal_and_adjustment_metadata(self) -> Self:
        """Reject records that could introduce temporal leakage or ambiguous adjustment state."""

        timeline = (
            ("event_time", self.event_time),
            ("published_at", self.published_at),
            ("available_at", self.available_at),
            ("received_at", self.received_at),
            ("ingested_at", self.ingested_at),
        )
        for (earlier_name, earlier), (later_name, later) in pairwise(timeline):
            if earlier > later:
                raise ValueError(f"{earlier_name} must not be after {later_name}")

        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_from >= self.effective_to
        ):
            raise ValueError("effective_from must be earlier than effective_to")

        if self.is_adjusted != (self.adjustment_type is not None):
            raise ValueError("adjustment_type must be present exactly when is_adjusted is true")

        return self

    def is_available_at(self, decision_time: datetime) -> bool:
        """Return whether this record was legally usable at a decision time."""

        return self.available_at <= _as_utc(decision_time)


class FactQuery(DomainContract):
    """Point-in-Time selection requested from a fact repository."""

    decision_time: datetime
    instrument_ids: tuple[UUID, ...] = ()
    fact_types: tuple[NonEmptyText, ...] = ()

    @field_validator("decision_time")
    @classmethod
    def normalize_decision_time(cls, value: datetime) -> datetime:
        return _as_utc(value)

    @field_validator("instrument_ids")
    @classmethod
    def normalize_instrument_ids(cls, values: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if len(values) != len(set(values)):
            raise ValueError("instrument_ids must be unique")
        return tuple(sorted(values, key=str))

    @field_validator("fact_types")
    @classmethod
    def normalize_fact_types(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("fact_types must be unique")
        return tuple(sorted(values))


def require_point_in_time(
    query: FactQuery,
    records: Iterable[DataSourceRecord],
) -> tuple[DataSourceRecord, ...]:
    """Validate that repository output obeys the query and cannot leak future facts."""

    selected = tuple(records)

    if any(not record.is_available_at(query.decision_time) for record in selected):
        raise ValueError("repository returned a record unavailable at decision_time")

    if query.instrument_ids and any(
        record.instrument_id not in query.instrument_ids for record in selected
    ):
        raise ValueError("repository returned a record outside instrument_ids")

    if query.fact_types and any(record.fact_type not in query.fact_types for record in selected):
        raise ValueError("repository returned a record outside fact_types")

    return selected


class AnalysisSnapshot(DomainContract):
    """Immutable, reproducible input shared by all three independent models."""

    schema_version: Annotated[str, StringConstraints(pattern=r"^1\.0\.0$")] = "1.0.0"
    snapshot_id: UUID
    target_type: TargetType
    target_id: UUID
    market: Market
    requested_horizon: RequestedHorizon
    decision_time: datetime
    market_timezone: NonEmptyText
    created_at: datetime

    price_as_of: datetime | None = None
    fundamental_as_of: datetime | None = None
    news_as_of: datetime | None = None
    options_as_of: datetime | None = None
    macro_as_of: datetime | None = None
    flow_as_of: datetime | None = None

    provider_versions: dict[NonEmptyText, NonEmptyText] = Field(default_factory=dict)
    dataset_versions: dict[NonEmptyText, NonEmptyText] = Field(default_factory=dict)
    fact_ids: tuple[UUID, ...] = ()
    missing_data: tuple[NonEmptyText, ...] = ()
    stale_data: tuple[NonEmptyText, ...] = ()
    quality_score: float = Field(ge=0.0, le=1.0)

    @field_validator(
        "decision_time",
        "created_at",
        "price_as_of",
        "fundamental_as_of",
        "news_as_of",
        "options_as_of",
        "macro_as_of",
        "flow_as_of",
    )
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _as_utc(value)

    @field_validator("provider_versions", "dataset_versions")
    @classmethod
    def normalize_version_maps(cls, values: dict[str, str]) -> dict[str, str]:
        return dict(sorted(values.items()))

    @field_validator("fact_ids")
    @classmethod
    def normalize_fact_ids(cls, values: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if len(values) != len(set(values)):
            raise ValueError("fact_ids must be unique")
        return tuple(sorted(values, key=str))

    @field_validator("missing_data", "stale_data")
    @classmethod
    def normalize_quality_lists(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("quality lists must not contain duplicates")
        return tuple(sorted(values))

    @model_validator(mode="after")
    def validate_point_in_time_boundary(self) -> Self:
        """Ensure every snapshot component was available by its decision time."""

        if self.created_at < self.decision_time:
            raise ValueError("created_at must not be earlier than decision_time")

        as_of_fields = (
            self.price_as_of,
            self.fundamental_as_of,
            self.news_as_of,
            self.options_as_of,
            self.macro_as_of,
            self.flow_as_of,
        )
        if any(value is not None and value > self.decision_time for value in as_of_fields):
            raise ValueError("as-of timestamps must not be after decision_time")

        expected_timezone = MARKET_TIMEZONES[self.market]
        if self.market_timezone != expected_timezone:
            raise ValueError(
                f"market_timezone for {self.market.value} must be {expected_timezone}"
            )

        overlap = set(self.missing_data) & set(self.stale_data)
        if overlap:
            raise ValueError("missing_data and stale_data must be disjoint")

        return self

    def content_fingerprint(self) -> Sha256Hex:
        """Hash reproducibility inputs while excluding allocation-time identity fields."""

        payload = self.model_dump(
            mode="json",
            exclude={"snapshot_id", "created_at"},
        )
        canonical = json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        return hashlib.sha256(canonical, usedforsecurity=False).hexdigest()
