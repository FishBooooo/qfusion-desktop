"""Point-in-Time domain contract tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

from pydantic import ValidationError
from pytest import raises

from qfusion.domain import (
    AnalysisSnapshot,
    DataSourceRecord,
    FactQuery,
    Market,
    QualityFlag,
    RequestedHorizon,
    TargetType,
    require_point_in_time,
)

FACT_ID = UUID("10000000-0000-4000-8000-000000000001")
INSTRUMENT_ID = UUID("20000000-0000-4000-8000-000000000001")
SNAPSHOT_ID = UUID("30000000-0000-4000-8000-000000000001")
TARGET_ID = UUID("40000000-0000-4000-8000-000000000001")
DECISION_TIME = datetime(2026, 7, 28, 14, 30, tzinfo=UTC)


def make_record(**overrides: object) -> DataSourceRecord:
    data: dict[str, object] = {
        "fact_id": FACT_ID,
        "instrument_id": INSTRUMENT_ID,
        "fact_type": "daily_bar",
        "source": "qfusion-synthetic-fixture",
        "source_record_id": "synthetic-us-001",
        "source_quality_level": "synthetic",
        "venue_scope": "US",
        "license_scope": "test-only",
        "provider_version": "1.0.0",
        "dataset_version": "mock-bars-v1",
        "event_time": DECISION_TIME - timedelta(minutes=5),
        "published_at": DECISION_TIME - timedelta(minutes=4),
        "available_at": DECISION_TIME - timedelta(minutes=3),
        "received_at": DECISION_TIME - timedelta(minutes=2),
        "ingested_at": DECISION_TIME - timedelta(minutes=1),
        "revision_id": "revision-1",
        "quality_flag": QualityFlag.SYNTHETIC_MOCK,
        "raw_payload_hash": "a" * 64,
        "payload": {"close": "100.25"},
    }
    data.update(overrides)
    return DataSourceRecord.model_validate(data)


def make_snapshot(**overrides: object) -> AnalysisSnapshot:
    data: dict[str, object] = {
        "snapshot_id": SNAPSHOT_ID,
        "target_type": TargetType.STOCK,
        "target_id": TARGET_ID,
        "market": Market.US,
        "requested_horizon": RequestedHorizon.FIVE_DAY,
        "decision_time": DECISION_TIME,
        "market_timezone": "America/New_York",
        "created_at": DECISION_TIME + timedelta(seconds=1),
        "price_as_of": DECISION_TIME - timedelta(minutes=1),
        "provider_versions": {"synthetic": "1.0.0"},
        "dataset_versions": {"bars": "mock-bars-v1"},
        "fact_ids": (FACT_ID,),
        "missing_data": (),
        "stale_data": (),
        "quality_score": 1.0,
    }
    data.update(overrides)
    return AnalysisSnapshot.model_validate(data)


def test_data_source_record_normalizes_offsets_to_utc() -> None:
    offset = timezone(timedelta(hours=-4))
    event_time = datetime(2026, 7, 28, 10, 25, tzinfo=offset)

    record = make_record(event_time=event_time)

    assert record.event_time == datetime(2026, 7, 28, 14, 25, tzinfo=UTC)
    assert record.event_time.tzinfo is UTC


def test_data_source_record_rejects_naive_timestamp() -> None:
    with raises(ValidationError, match="timezone-aware"):
        make_record(event_time=datetime(2026, 7, 28, 14, 25))


def test_data_source_record_rejects_non_monotonic_timeline() -> None:
    with raises(ValidationError, match="available_at must not be after received_at"):
        make_record(
            available_at=DECISION_TIME,
            received_at=DECISION_TIME - timedelta(seconds=1),
        )


def test_data_source_record_rejects_invalid_effective_range() -> None:
    with raises(ValidationError, match="effective_from must be earlier"):
        make_record(effective_from=DECISION_TIME, effective_to=DECISION_TIME)


def test_data_source_record_requires_consistent_adjustment_metadata() -> None:
    with raises(ValidationError, match="adjustment_type"):
        make_record(is_adjusted=True)

    with raises(ValidationError, match="adjustment_type"):
        make_record(adjustment_type="split")


def test_data_source_record_rejects_extra_fields_and_invalid_hash() -> None:
    with raises(ValidationError):
        make_record(unexpected="value")

    with raises(ValidationError):
        make_record(raw_payload_hash="not-a-sha256")


def test_record_availability_requires_aware_decision_time() -> None:
    record = make_record()

    assert record.is_available_at(DECISION_TIME)
    with raises(ValueError, match="timezone-aware"):
        record.is_available_at(datetime(2026, 7, 28, 14, 30))


def test_fact_query_is_canonical_and_unique() -> None:
    another_instrument = UUID("20000000-0000-4000-8000-000000000000")
    query = FactQuery(
        decision_time=DECISION_TIME,
        instrument_ids=(INSTRUMENT_ID, another_instrument),
        fact_types=("news", "daily_bar"),
    )

    assert query.instrument_ids == (another_instrument, INSTRUMENT_ID)
    assert query.fact_types == ("daily_bar", "news")

    with raises(ValidationError, match="instrument_ids must be unique"):
        FactQuery(decision_time=DECISION_TIME, instrument_ids=(INSTRUMENT_ID, INSTRUMENT_ID))

    with raises(ValidationError, match="fact_types must be unique"):
        FactQuery(decision_time=DECISION_TIME, fact_types=("news", "news"))


def test_point_in_time_guard_rejects_future_and_out_of_scope_records() -> None:
    query = FactQuery(
        decision_time=DECISION_TIME,
        instrument_ids=(INSTRUMENT_ID,),
        fact_types=("daily_bar",),
    )
    record = make_record()

    assert require_point_in_time(query, (record,)) == (record,)

    future = make_record(
        available_at=DECISION_TIME + timedelta(minutes=1),
        received_at=DECISION_TIME + timedelta(minutes=2),
        ingested_at=DECISION_TIME + timedelta(minutes=3),
    )
    with raises(ValueError, match="unavailable"):
        require_point_in_time(query, (future,))

    other_instrument = make_record(
        fact_id=UUID("10000000-0000-4000-8000-000000000002"),
        instrument_id=UUID("20000000-0000-4000-8000-000000000002"),
    )
    with raises(ValueError, match="outside instrument_ids"):
        require_point_in_time(query, (other_instrument,))

    other_type = make_record(fact_type="news")
    with raises(ValueError, match="outside fact_types"):
        require_point_in_time(query, (other_type,))


def test_snapshot_normalizes_collections_and_has_stable_fingerprint() -> None:
    second_fact = UUID("10000000-0000-4000-8000-000000000000")
    snapshot = make_snapshot(
        provider_versions={"z-provider": "2", "a-provider": "1"},
        dataset_versions={"z-dataset": "2", "a-dataset": "1"},
        fact_ids=(FACT_ID, second_fact),
        stale_data=("news", "fundamentals"),
    )
    equivalent = make_snapshot(
        snapshot_id=UUID("30000000-0000-4000-8000-000000000002"),
        created_at=DECISION_TIME + timedelta(minutes=1),
        provider_versions={"a-provider": "1", "z-provider": "2"},
        dataset_versions={"a-dataset": "1", "z-dataset": "2"},
        fact_ids=(second_fact, FACT_ID),
        stale_data=("fundamentals", "news"),
    )

    assert tuple(snapshot.provider_versions) == ("a-provider", "z-provider")
    assert tuple(snapshot.dataset_versions) == ("a-dataset", "z-dataset")
    assert snapshot.fact_ids == (second_fact, FACT_ID)
    assert snapshot.stale_data == ("fundamentals", "news")
    assert snapshot.content_fingerprint() == equivalent.content_fingerprint()
    assert len(snapshot.content_fingerprint()) == 64


def test_snapshot_rejects_temporal_timezone_and_quality_violations() -> None:
    with raises(ValidationError, match="created_at"):
        make_snapshot(created_at=DECISION_TIME - timedelta(seconds=1))

    with raises(ValidationError, match="as-of"):
        make_snapshot(news_as_of=DECISION_TIME + timedelta(seconds=1))

    with raises(ValidationError, match="market_timezone"):
        make_snapshot(market_timezone="UTC")

    with raises(ValidationError, match="disjoint"):
        make_snapshot(missing_data=("news",), stale_data=("news",))


def test_snapshot_rejects_duplicate_quality_and_fact_identifiers() -> None:
    with raises(ValidationError, match="fact_ids must be unique"):
        make_snapshot(fact_ids=(FACT_ID, FACT_ID))

    with raises(ValidationError, match="quality lists"):
        make_snapshot(missing_data=("news", "news"))


def test_snapshot_supports_hong_kong_market_timezone() -> None:
    snapshot = make_snapshot(
        market=Market.HK,
        market_timezone="Asia/Hong_Kong",
    )

    assert snapshot.market is Market.HK
