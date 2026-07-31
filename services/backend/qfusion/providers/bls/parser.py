"""Pure parser from BLS v1 monthly observations to traceable macro facts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated
from uuid import UUID, uuid5

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    ValidationError,
    field_validator,
)

from qfusion.domain import DataSourceRecord, QualityFlag
from qfusion.providers.bls.contracts import BlsSeriesId, BlsSeriesRequest
from qfusion.providers.bls.errors import BlsPayloadError

_FACT_NAMESPACE = UUID("e2266281-dd78-403f-bb72-0cd6a64654ee")
ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=512),
]
YearText = Annotated[str, StringConstraints(pattern=r"^\d{4}$")]
MonthlyPeriod = Annotated[
    str,
    StringConstraints(pattern=r"^M(?:0[1-9]|1[0-3])$"),
]


class _BlsModel(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        frozen=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class _BlsFootnote(_BlsModel):
    code: ShortText | None = None
    text: ShortText | None = None

    @field_validator("code", "text", mode="before")
    @classmethod
    def normalize_empty_text(cls, value: object) -> object:
        return None if value is None or value == "" else value


class _BlsObservation(_BlsModel):
    year: YearText
    period: MonthlyPeriod
    period_name: ShortText = Field(alias="periodName")
    value: ShortText
    footnotes: tuple[_BlsFootnote, ...]

    @field_validator("value")
    @classmethod
    def validate_numeric_value(cls, value: str) -> str:
        try:
            parsed = Decimal(value)
        except InvalidOperation as error:
            raise ValueError("BLS observation value must be numeric") from error
        if not parsed.is_finite():
            raise ValueError("BLS observation value must be finite")
        return value


class _BlsSeries(_BlsModel):
    series_id: BlsSeriesId = Field(alias="seriesID")
    data: tuple[_BlsObservation, ...]


class _BlsResults(_BlsModel):
    series: tuple[_BlsSeries, ...]


class _BlsEnvelope(_BlsModel):
    status: ShortText
    message: tuple[str, ...]
    results: _BlsResults = Field(alias="Results")


def _as_utc(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise BlsPayloadError(f"{label} must be timezone-aware")
    return value.astimezone(UTC)


def _row_payload(observation: _BlsObservation, series_id: str) -> dict[str, JsonValue]:
    return {
        "api_version": "v1",
        "series_id": series_id,
        "year": observation.year,
        "period": observation.period,
        "period_name": observation.period_name,
        "value": observation.value,
        "footnotes": [
            {"code": footnote.code, "text": footnote.text}
            for footnote in observation.footnotes
        ],
        "time_basis": "monthly-period-start-utc",
        "publication_time_basis": "qfusion-first-observed-conservative",
    }


def parse_bls_series(
    payload: Mapping[str, object],
    request: BlsSeriesRequest,
    *,
    received_at: datetime,
    ingested_at: datetime,
) -> tuple[DataSourceRecord, ...]:
    """Parse monthly observations without backdating API availability or revisions."""

    observed_at = _as_utc(received_at, "received_at")
    persisted_at = _as_utc(ingested_at, "ingested_at")
    if persisted_at < observed_at:
        raise BlsPayloadError("ingested_at must not be earlier than received_at")

    try:
        envelope = _BlsEnvelope.model_validate(payload)
    except ValidationError as error:
        raise BlsPayloadError("BLS response envelope failed validation") from error

    if envelope.status != "REQUEST_SUCCEEDED":
        raise BlsPayloadError(f"BLS request status was {envelope.status}")
    if envelope.message:
        raise BlsPayloadError("BLS response contained API messages")

    requested_ids = set(request.series_ids)
    returned_ids = [series.series_id for series in envelope.results.series]
    if len(returned_ids) != len(set(returned_ids)):
        raise BlsPayloadError("BLS response contained duplicate series IDs")
    if set(returned_ids) != requested_ids:
        raise BlsPayloadError("BLS response series IDs did not match the request")

    records: list[DataSourceRecord] = []
    for series in envelope.results.series:
        if not series.data:
            raise BlsPayloadError(f"BLS series {series.series_id} returned no observations")
        seen_periods: set[tuple[str, str]] = set()
        monthly_count = 0
        for observation in series.data:
            period_key = (observation.year, observation.period)
            if period_key in seen_periods:
                raise BlsPayloadError("BLS response contained a duplicate observation period")
            seen_periods.add(period_key)

            observation_year = int(observation.year)
            if not request.start_year <= observation_year <= request.end_year:
                raise BlsPayloadError(
                    "BLS observation year fell outside the requested window"
                )

            if observation.period == "M13":
                continue
            monthly_count += 1
            month = int(observation.period[1:])
            event_time = datetime(observation_year, month, 1, tzinfo=UTC)
            if event_time > observed_at:
                raise BlsPayloadError("BLS observation period starts after receipt time")

            canonical_row = json.dumps(
                observation.model_dump(mode="json", by_alias=True),
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            row_hash = hashlib.sha256(
                canonical_row,
                usedforsecurity=False,
            ).hexdigest()
            source_record_id = (
                f"{series.series_id}:{observation.year}:{observation.period}"
            )
            fact_id = uuid5(
                _FACT_NAMESPACE,
                f"bls-public-data-v1:{source_record_id}:{row_hash}",
            )

            try:
                records.append(
                    DataSourceRecord(
                        fact_id=fact_id,
                        instrument_id=None,
                        fact_type="macro_observation",
                        source="bls-public-data-v1",
                        source_record_id=source_record_id,
                        source_quality_level="official-published-macro-series",
                        venue_scope="US-BLS",
                        license_scope="bls-api-secondary-use-with-attribution",
                        provider_version="1.0.0",
                        dataset_version="bls-public-data-v1-first-observed",
                        event_time=event_time,
                        published_at=observed_at,
                        available_at=observed_at,
                        received_at=observed_at,
                        ingested_at=persisted_at,
                        revision_id=f"sha256:{row_hash}",
                        quality_flag=QualityFlag.OK,
                        raw_payload_hash=row_hash,
                        payload=_row_payload(observation, series.series_id),
                    )
                )
            except ValidationError as error:
                raise BlsPayloadError(
                    "BLS observation violated the Domain contract"
                ) from error
        if monthly_count == 0:
            raise BlsPayloadError(
                f"BLS series {series.series_id} returned no monthly observations"
            )

    records.sort(key=lambda item: (item.event_time, item.source_record_id))
    return tuple(records)
