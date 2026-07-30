"""Network-free SEC submissions parsing and Point-in-Time tests."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import JsonValue, cast
from uuid import UUID

from pytest import raises

from qfusion.domain import Market, QualityFlag
from qfusion.providers.sec import SecFilingRequest, SecPayloadError, parse_sec_submissions

_FIXTURE = (
    Path(__file__).parents[3] / "fixtures" / "sec" / "submissions-schema-fixture.json"
)
INSTRUMENT_ID = UUID("30000000-0000-4000-8000-000000000001")
RECEIVED_AT = datetime(2026, 5, 8, 0, 0, tzinfo=UTC)
DECISION_TIME = RECEIVED_AT + timedelta(seconds=1)


def load_fixture() -> dict[str, JsonValue]:
    decoded: object = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    if not isinstance(decoded, dict) or not all(isinstance(key, str) for key in decoded):
        raise TypeError("SEC test fixture must be a JSON object")
    return cast(dict[str, JsonValue], decoded)


def make_request(**overrides: object) -> SecFilingRequest:
    values: dict[str, object] = {
        "instrument_id": INSTRUMENT_ID,
        "provider_instrument_id": "0000000001",
        "market": Market.US,
        "decision_time": DECISION_TIME,
    }
    values.update(overrides)
    return SecFilingRequest.model_validate(values)


def parse(
    payload: dict[str, JsonValue] | None = None,
    **request_overrides: object,
):
    return parse_sec_submissions(
        load_fixture() if payload is None else payload,
        make_request(**request_overrides),
        received_at=RECEIVED_AT,
        ingested_at=RECEIVED_AT,
    )


def test_fixture_parses_traceable_filings_with_observed_availability() -> None:
    records = parse()

    assert [record.payload["form"] for record in records] == ["10-Q", "10-K"]
    assert all(record.instrument_id == INSTRUMENT_ID for record in records)
    assert all(record.fact_type == "filing_metadata" for record in records)
    assert all(record.source == "sec-edgar" for record in records)
    assert all(record.quality_flag is QualityFlag.OK for record in records)
    assert all(record.available_at == RECEIVED_AT for record in records)
    assert all(record.received_at == RECEIVED_AT for record in records)
    assert records[0].published_at == datetime(2026, 5, 7, 20, 15, 28, tzinfo=UTC)
    assert records[0].event_time == datetime(2026, 3, 31, tzinfo=UTC)
    assert records[0].source_record_id == "0000000001-26-000002"
    assert len(records[0].raw_payload_hash) == 64


def test_parser_filters_forms_limit_and_decision_time() -> None:
    filtered = parse(forms=("10-k",))
    assert len(filtered) == 1
    assert filtered[0].payload["form"] == "10-K"

    limited = parse(limit=1)
    assert len(limited) == 1
    assert limited[0].payload["form"] == "10-Q"

    unavailable = parse(decision_time=RECEIVED_AT - timedelta(microseconds=1))
    assert unavailable == ()


def test_parser_is_deterministic_for_same_first_observation_envelope() -> None:
    first = parse()
    second = parse()

    assert first == second
    assert first[0].fact_id == second[0].fact_id
    assert first[0].raw_payload_hash == second[0].raw_payload_hash


def test_parser_tolerates_new_outer_and_equal_length_recent_columns() -> None:
    payload = load_fixture()
    payload["newTopLevelField"] = {"nested": True}
    filings = cast(dict[str, JsonValue], payload["filings"])
    recent = cast(dict[str, JsonValue], filings["recent"])
    recent["newColumn"] = ["new-a", "new-b"]

    assert len(parse(payload)) == 2


def test_parser_rejects_cik_mismatch_missing_and_misaligned_columns() -> None:
    mismatch = load_fixture()
    mismatch["cik"] = 2
    with raises(SecPayloadError, match="does not match"):
        parse(mismatch)

    missing = load_fixture()
    missing_filings = cast(dict[str, JsonValue], missing["filings"])
    missing_recent = cast(dict[str, JsonValue], missing_filings["recent"])
    del missing_recent["form"]
    with raises(SecPayloadError, match="missing columns"):
        parse(missing)

    misaligned = load_fixture()
    bad_filings = cast(dict[str, JsonValue], misaligned["filings"])
    bad_recent = cast(dict[str, JsonValue], bad_filings["recent"])
    bad_recent["form"] = ["10-Q"]
    with raises(SecPayloadError, match="has length 1"):
        parse(misaligned)


def test_parser_rejects_scalar_column_invalid_row_and_future_acceptance() -> None:
    scalar = load_fixture()
    scalar_filings = cast(dict[str, JsonValue], scalar["filings"])
    scalar_recent = cast(dict[str, JsonValue], scalar_filings["recent"])
    scalar_recent["newColumn"] = "not-an-array"
    with raises(SecPayloadError, match="must be an array"):
        parse(scalar)

    invalid = load_fixture()
    invalid_filings = cast(dict[str, JsonValue], invalid["filings"])
    invalid_recent = cast(dict[str, JsonValue], invalid_filings["recent"])
    invalid_recent["filingDate"] = ["not-a-date", "2026-02-20"]
    with raises(SecPayloadError, match="row failed validation"):
        parse(invalid)

    future = load_fixture()
    future_filings = cast(dict[str, JsonValue], future["filings"])
    future_recent = cast(dict[str, JsonValue], future_filings["recent"])
    future_recent["acceptanceDateTime"] = [
        "2027-01-01T00:00:00Z",
        "2026-02-20T21:05:00Z",
    ]
    with raises(SecPayloadError, match="after the observed"):
        parse(future)


def test_parser_rejects_invalid_envelope_timestamps_and_does_not_mutate_input() -> None:
    payload = load_fixture()
    before = copy.deepcopy(payload)

    with raises(SecPayloadError, match="ingested_at"):
        parse_sec_submissions(
            payload,
            make_request(),
            received_at=RECEIVED_AT,
            ingested_at=RECEIVED_AT - timedelta(seconds=1),
        )
    with raises(SecPayloadError, match="timezone-aware"):
        parse_sec_submissions(
            payload,
            make_request(),
            received_at=datetime(2026, 5, 8),
            ingested_at=RECEIVED_AT,
        )

    assert payload == before


def test_parser_accepts_empty_recent_arrays() -> None:
    payload = load_fixture()
    filings = cast(dict[str, JsonValue], payload["filings"])
    recent = cast(dict[str, JsonValue], filings["recent"])
    for key in tuple(recent):
        recent[key] = []

    assert parse(payload) == ()
