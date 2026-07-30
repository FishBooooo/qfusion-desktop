"""Pure parser from SEC submissions column arrays to traceable filing facts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, date, datetime, time
from typing import Annotated, cast
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
from qfusion.providers.sec.contracts import SecFilingRequest
from qfusion.providers.sec.errors import SecPayloadError

_FACT_NAMESPACE = UUID("dc204611-737d-4ed3-9d86-70f0dbe4fbbc")
_REQUIRED_RECENT_COLUMNS = frozenset(
    {
        "accessionNumber",
        "filingDate",
        "reportDate",
        "acceptanceDateTime",
        "form",
        "primaryDocument",
    }
)
AccessionNumber = Annotated[
    str,
    StringConstraints(pattern=r"^\d{10}-\d{2}-\d{6}$"),
]
ShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=512),
]


class _RecentFiling(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        frozen=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    accession_number: AccessionNumber = Field(alias="accessionNumber")
    filing_date: date = Field(alias="filingDate")
    report_date: date | None = Field(alias="reportDate")
    acceptance_date_time: datetime = Field(alias="acceptanceDateTime")
    form: Annotated[str, StringConstraints(min_length=1, max_length=32)]
    primary_document: ShortText = Field(alias="primaryDocument")
    primary_document_description: ShortText | None = Field(
        default=None,
        alias="primaryDocDescription",
    )
    act: ShortText | None = None
    file_number: ShortText | None = Field(default=None, alias="fileNumber")
    film_number: ShortText | None = Field(default=None, alias="filmNumber")
    items: ShortText | None = None
    size: int | None = Field(default=None, ge=0)
    is_xbrl: bool | None = Field(default=None, alias="isXBRL")
    is_inline_xbrl: bool | None = Field(default=None, alias="isInlineXBRL")

    @field_validator("report_date", mode="before")
    @classmethod
    def normalize_empty_report_date(cls, value: object) -> object:
        return None if value is None or value == "" else value

    @field_validator("acceptance_date_time")
    @classmethod
    def normalize_acceptance_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("acceptanceDateTime must be timezone-aware")
        return value.astimezone(UTC)


def _as_utc(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise SecPayloadError(f"{label} must be timezone-aware")
    return value.astimezone(UTC)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) for key in value
    ):
        raise SecPayloadError(f"{label} must be a JSON object")
    return cast(Mapping[str, object], value)


def _normalize_cik(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise SecPayloadError("SEC payload cik must be an integer or digit string")
    digits = str(value).strip()
    if not digits.isdigit() or len(digits) > 10:
        raise SecPayloadError("SEC payload cik must contain at most ten digits")
    return digits.zfill(10)


def _columnar_rows(recent: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    missing = sorted(_REQUIRED_RECENT_COLUMNS - set(recent))
    if missing:
        raise SecPayloadError(f"SEC filings.recent is missing columns: {', '.join(missing)}")

    accession_column = recent["accessionNumber"]
    if not isinstance(accession_column, list):
        raise SecPayloadError("SEC filings.recent accessionNumber must be an array")
    row_count = len(accession_column)

    columns: dict[str, list[object]] = {}
    for name, value in recent.items():
        if not isinstance(value, list):
            raise SecPayloadError(f"SEC filings.recent column {name} must be an array")
        if len(value) != row_count:
            raise SecPayloadError(
                f"SEC filings.recent column {name} has length {len(value)}; "
                f"expected {row_count}"
            )
        columns[name] = cast(list[object], value)

    return tuple(
        {name: values[index] for name, values in columns.items()}
        for index in range(row_count)
    )


def _optional_text(value: str | None) -> JsonValue:
    return value if value not in {"", None} else None


def _fact_payload(
    filing: _RecentFiling,
    *,
    cik: str,
    entity_name: str,
) -> dict[str, JsonValue]:
    return {
        "cik": cik,
        "entity_name": entity_name,
        "accession_number": filing.accession_number,
        "filing_date": filing.filing_date.isoformat(),
        "report_date": (
            None if filing.report_date is None else filing.report_date.isoformat()
        ),
        "acceptance_datetime": filing.acceptance_date_time.isoformat(),
        "form": filing.form,
        "primary_document": filing.primary_document,
        "primary_document_description": _optional_text(
            filing.primary_document_description
        ),
        "act": _optional_text(filing.act),
        "file_number": _optional_text(filing.file_number),
        "film_number": _optional_text(filing.film_number),
        "items": _optional_text(filing.items),
        "size": filing.size,
        "is_xbrl": filing.is_xbrl,
        "is_inline_xbrl": filing.is_inline_xbrl,
    }


def parse_sec_submissions(
    payload: Mapping[str, object],
    request: SecFilingRequest,
    *,
    received_at: datetime,
    ingested_at: datetime,
) -> tuple[DataSourceRecord, ...]:
    """Parse recent filing metadata and enforce first-observation availability."""

    observed_at = _as_utc(received_at, "received_at")
    persisted_at = _as_utc(ingested_at, "ingested_at")
    if persisted_at < observed_at:
        raise SecPayloadError("ingested_at must not be earlier than received_at")

    payload_cik = _normalize_cik(payload.get("cik"))
    if payload_cik != request.cik:
        raise SecPayloadError("SEC payload cik does not match the registry-resolved CIK")

    entity_name_value = payload.get("name")
    if not isinstance(entity_name_value, str) or not entity_name_value.strip():
        raise SecPayloadError("SEC payload name must be a non-empty string")
    entity_name = entity_name_value.strip()

    filings = _mapping(payload.get("filings"), "SEC filings")
    recent = _mapping(filings.get("recent"), "SEC filings.recent")
    raw_rows = _columnar_rows(recent)
    requested_forms = set(request.forms)

    records: list[DataSourceRecord] = []
    for raw_row in raw_rows:
        try:
            filing = _RecentFiling.model_validate(raw_row)
        except ValidationError as error:
            raise SecPayloadError("SEC recent filing row failed validation") from error

        if requested_forms and filing.form not in requested_forms:
            continue
        if filing.acceptance_date_time > observed_at:
            raise SecPayloadError(
                "SEC acceptanceDateTime must not be after the observed receipt time"
            )
        report_or_filing_date = filing.report_date or filing.filing_date
        event_time = datetime.combine(report_or_filing_date, time.min, tzinfo=UTC)
        canonical_row = json.dumps(
            raw_row,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        row_hash = hashlib.sha256(canonical_row, usedforsecurity=False).hexdigest()
        fact_id = uuid5(
            _FACT_NAMESPACE,
            f"sec-edgar:{payload_cik}:{filing.accession_number}",
        )

        try:
            record = DataSourceRecord(
                fact_id=fact_id,
                instrument_id=request.instrument_id,
                fact_type="filing_metadata",
                source="sec-edgar",
                source_record_id=filing.accession_number,
                source_quality_level="official-public-filings",
                venue_scope="US-SEC-EDGAR",
                license_scope="public-government-content",
                provider_version="1.0.0",
                dataset_version="sec-submissions-v1",
                event_time=event_time,
                published_at=filing.acceptance_date_time,
                available_at=observed_at,
                received_at=observed_at,
                ingested_at=persisted_at,
                revision_id=filing.accession_number,
                quality_flag=QualityFlag.OK,
                raw_payload_hash=row_hash,
                payload=_fact_payload(
                    filing,
                    cik=payload_cik,
                    entity_name=entity_name,
                ),
            )
        except ValidationError as error:
            raise SecPayloadError("SEC filing metadata violated the Domain contract") from error
        records.append(record)

    records.sort(
        key=lambda item: (item.published_at, item.source_record_id),
        reverse=True,
    )
    return tuple(records[: request.limit])
