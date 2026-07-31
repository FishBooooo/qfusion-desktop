"""Pure BLS parser tests using only a synthetic checked-in response fixture."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from pydantic import JsonValue
from pytest import raises

from qfusion.providers.bls import BlsPayloadError, BlsSeriesRequest, parse_bls_series

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = REPOSITORY_ROOT / "fixtures/bls/public-data-v1-schema-fixture.json"
OBSERVED_AT = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
INGESTED_AT = OBSERVED_AT + timedelta(seconds=1)
REQUEST = BlsSeriesRequest(
    series_ids=("QFUSION_TEST_01",),
    start_year=2025,
    end_year=2026,
)


def load_payload() -> dict[str, JsonValue]:
    loaded: object = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return cast(dict[str, JsonValue], loaded)


def first_series(payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
    results = cast(dict[str, JsonValue], payload["Results"])
    series = cast(list[JsonValue], results["series"])
    return cast(dict[str, JsonValue], series[0])


def observations(payload: dict[str, JsonValue]) -> list[JsonValue]:
    return cast(list[JsonValue], first_series(payload)["data"])


def test_parser_preserves_values_footnotes_and_first_observed_pit_boundary() -> None:
    records = parse_bls_series(
        load_payload(),
        REQUEST,
        received_at=OBSERVED_AT,
        ingested_at=INGESTED_AT,
    )

    assert len(records) == 2
    january, february = records
    assert january.source_record_id == "QFUSION_TEST_01:2026:M01"
    assert january.event_time == datetime(2026, 1, 1, tzinfo=UTC)
    assert february.event_time == datetime(2026, 2, 1, tzinfo=UTC)
    assert january.instrument_id is None
    assert january.fact_type == "macro_observation"
    assert january.source == "bls-public-data-v1"
    assert january.source_quality_level == "official-published-macro-series"
    assert january.venue_scope == "US-BLS"
    assert january.provider_version == "1.0.0"
    assert january.dataset_version == "bls-public-data-v1-first-observed"
    assert january.published_at == OBSERVED_AT
    assert january.available_at == OBSERVED_AT
    assert january.received_at == OBSERVED_AT
    assert january.ingested_at == INGESTED_AT
    assert not january.is_available_at(OBSERVED_AT - timedelta(microseconds=1))
    assert january.is_available_at(OBSERVED_AT)
    assert january.revision_id == f"sha256:{january.raw_payload_hash}"
    assert january.payload["value"] == "100.00"
    assert january.payload["footnotes"] == [
        {"code": "P", "text": "Preliminary synthetic observation."}
    ]
    assert february.payload["value"] == "101.25"
    assert february.payload["footnotes"] == [{"code": None, "text": None}]
    assert january.payload["time_basis"] == "monthly-period-start-utc"
    assert january.payload["publication_time_basis"] == (
        "qfusion-first-observed-conservative"
    )
    assert all(record.source_record_id != "QFUSION_TEST_01:2025:M13" for record in records)


def test_parser_revision_identity_changes_without_overwriting_period_identity() -> None:
    original_payload = load_payload()
    original = parse_bls_series(
        original_payload,
        REQUEST,
        received_at=OBSERVED_AT,
        ingested_at=OBSERVED_AT,
    )
    repeated = parse_bls_series(
        original_payload,
        REQUEST,
        received_at=OBSERVED_AT,
        ingested_at=OBSERVED_AT,
    )
    revised_payload = copy.deepcopy(original_payload)
    january = cast(dict[str, JsonValue], observations(revised_payload)[1])
    january["value"] = "100.50"
    revised = parse_bls_series(
        revised_payload,
        REQUEST,
        received_at=OBSERVED_AT + timedelta(days=1),
        ingested_at=OBSERVED_AT + timedelta(days=1),
    )

    assert original[0].fact_id == repeated[0].fact_id
    assert original[0].revision_id == repeated[0].revision_id
    assert revised[0].source_record_id == original[0].source_record_id
    assert revised[0].fact_id != original[0].fact_id
    assert revised[0].revision_id != original[0].revision_id
    assert revised[0].available_at == OBSERVED_AT + timedelta(days=1)


def test_parser_rejects_unsafe_receipt_and_ingestion_times() -> None:
    payload = load_payload()

    with raises(BlsPayloadError, match="received_at must be timezone-aware"):
        parse_bls_series(
            payload,
            REQUEST,
            received_at=datetime(2026, 7, 31, 12, 0),
            ingested_at=INGESTED_AT,
        )
    with raises(BlsPayloadError, match="ingested_at must be timezone-aware"):
        parse_bls_series(
            payload,
            REQUEST,
            received_at=OBSERVED_AT,
            ingested_at=datetime(2026, 7, 31, 12, 0),
        )
    with raises(BlsPayloadError, match="must not be earlier"):
        parse_bls_series(
            payload,
            REQUEST,
            received_at=OBSERVED_AT,
            ingested_at=OBSERVED_AT - timedelta(seconds=1),
        )


def test_parser_rejects_failed_or_ambiguous_response_envelopes() -> None:
    malformed = load_payload()
    malformed.pop("Results")
    with raises(BlsPayloadError, match="envelope failed validation"):
        parse_bls_series(
            malformed,
            REQUEST,
            received_at=OBSERVED_AT,
            ingested_at=OBSERVED_AT,
        )

    failed = load_payload()
    failed["status"] = "REQUEST_FAILED"
    with raises(BlsPayloadError, match="status was REQUEST_FAILED"):
        parse_bls_series(
            failed,
            REQUEST,
            received_at=OBSERVED_AT,
            ingested_at=OBSERVED_AT,
        )

    warned = load_payload()
    warned["message"] = ["Synthetic warning"]
    with raises(BlsPayloadError, match="contained API messages"):
        parse_bls_series(
            warned,
            REQUEST,
            received_at=OBSERVED_AT,
            ingested_at=OBSERVED_AT,
        )


def test_parser_rejects_series_identity_mismatches_and_duplicates() -> None:
    mismatch = load_payload()
    first_series(mismatch)["seriesID"] = "QFUSION_OTHER"
    with raises(BlsPayloadError, match="did not match"):
        parse_bls_series(
            mismatch,
            REQUEST,
            received_at=OBSERVED_AT,
            ingested_at=OBSERVED_AT,
        )

    duplicate = load_payload()
    results = cast(dict[str, JsonValue], duplicate["Results"])
    series = cast(list[JsonValue], results["series"])
    series.append(copy.deepcopy(series[0]))
    duplicate_request = BlsSeriesRequest(
        series_ids=("QFUSION_TEST_01", "QFUSION_TEST_02"),
        start_year=2025,
        end_year=2026,
    )
    with raises(BlsPayloadError, match="duplicate series IDs"):
        parse_bls_series(
            duplicate,
            duplicate_request,
            received_at=OBSERVED_AT,
            ingested_at=OBSERVED_AT,
        )


def test_parser_rejects_empty_duplicate_annual_only_and_future_observations() -> None:
    empty = load_payload()
    first_series(empty)["data"] = []
    with raises(BlsPayloadError, match="returned no observations"):
        parse_bls_series(
            empty,
            REQUEST,
            received_at=OBSERVED_AT,
            ingested_at=OBSERVED_AT,
        )

    duplicate = load_payload()
    rows = observations(duplicate)
    rows.append(copy.deepcopy(rows[0]))
    with raises(BlsPayloadError, match="duplicate observation period"):
        parse_bls_series(
            duplicate,
            REQUEST,
            received_at=OBSERVED_AT,
            ingested_at=OBSERVED_AT,
        )

    annual_only = load_payload()
    first_series(annual_only)["data"] = [copy.deepcopy(observations(annual_only)[2])]
    with raises(BlsPayloadError, match="no monthly observations"):
        parse_bls_series(
            annual_only,
            REQUEST,
            received_at=OBSERVED_AT,
            ingested_at=OBSERVED_AT,
        )

    future = load_payload()
    future_row = cast(dict[str, JsonValue], observations(future)[0])
    future_row["year"] = "2027"
    with raises(BlsPayloadError, match="starts after receipt time"):
        parse_bls_series(
            future,
            REQUEST,
            received_at=OBSERVED_AT,
            ingested_at=OBSERVED_AT,
        )


def test_parser_rejects_observations_outside_requested_year_window() -> None:
    payload = load_payload()
    row = cast(dict[str, JsonValue], observations(payload)[0])
    row["year"] = "2024"

    with raises(BlsPayloadError, match="outside the requested window"):
        parse_bls_series(
            payload,
            REQUEST,
            received_at=OBSERVED_AT,
            ingested_at=OBSERVED_AT,
        )


def test_parser_rejects_non_numeric_or_non_finite_values() -> None:
    for invalid in ("not-a-number", "NaN", "Infinity"):
        payload = load_payload()
        row = cast(dict[str, JsonValue], observations(payload)[0])
        row["value"] = invalid
        with raises(BlsPayloadError, match="envelope failed validation"):
            parse_bls_series(
                payload,
                REQUEST,
                received_at=OBSERVED_AT,
                ingested_at=OBSERVED_AT,
            )
