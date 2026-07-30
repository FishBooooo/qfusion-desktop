"""Deterministic synthetic provider boundary tests."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

from pytest import mark, raises

from qfusion.domain import DataSourceRecord, Market, QualityFlag
from qfusion.providers import (
    DataDeliveryQuality,
    DataInterval,
    MarketDataProvider,
    ProviderAdapter,
    ProviderBarRequest,
    SyntheticMockMarketDataProvider,
)

INSTRUMENT_ID = UUID("20000000-0000-4000-8000-000000000001")
OTHER_INSTRUMENT_ID = UUID("20000000-0000-4000-8000-000000000002")
EVENT_TIME = datetime(2026, 7, 30, 19, 50, tzinfo=UTC)
DECISION_TIME = EVENT_TIME + timedelta(minutes=6)


def make_record(
    fact_id: UUID = UUID("10000000-0000-4000-8000-000000000001"),
    **overrides: object,
) -> DataSourceRecord:
    event_time = overrides.pop("event_time", EVENT_TIME)
    if not isinstance(event_time, datetime):
        raise TypeError("test event_time must be a datetime")
    data: dict[str, object] = {
        "fact_id": fact_id,
        "instrument_id": INSTRUMENT_ID,
        "fact_type": "daily_bar",
        "source": "qfusion-synthetic-mock",
        "source_record_id": f"synthetic-{fact_id}",
        "source_quality_level": "synthetic",
        "venue_scope": "synthetic-us-hk",
        "license_scope": "test-only",
        "provider_version": "1.0.0",
        "dataset_version": "mock-bars-v1",
        "event_time": event_time,
        "published_at": event_time + timedelta(minutes=1),
        "available_at": event_time + timedelta(minutes=2),
        "received_at": event_time + timedelta(minutes=3),
        "ingested_at": event_time + timedelta(minutes=4),
        "revision_id": "revision-1",
        "quality_flag": QualityFlag.SYNTHETIC_MOCK,
        "raw_payload_hash": hashlib.sha256(
            str(fact_id).encode(),
            usedforsecurity=False,
        ).hexdigest(),
        "payload": {"close": "100.00"},
    }
    data.update(overrides)
    return DataSourceRecord.model_validate(data)


def make_request(**overrides: object) -> ProviderBarRequest:
    data: dict[str, object] = {
        "instrument_id": INSTRUMENT_ID,
        "provider_instrument_id": "opaque-instrument-1",
        "market": Market.US,
        "interval": DataInterval.DAY_1,
        "start": EVENT_TIME - timedelta(days=1),
        "end": DECISION_TIME,
        "decision_time": DECISION_TIME,
    }
    data.update(overrides)
    return ProviderBarRequest.model_validate(data)


def make_provider(
    records: list[DataSourceRecord] | None = None,
) -> SyntheticMockMarketDataProvider:
    selected = [make_record()] if records is None else records
    return SyntheticMockMarketDataProvider(
        selected,
        {
            INSTRUMENT_ID: "opaque-instrument-1",
            OTHER_INSTRUMENT_ID: "opaque-instrument-2",
        },
    )


def test_mock_provider_satisfies_interfaces_and_declares_synthetic_access() -> None:
    provider = make_provider()

    assert isinstance(provider, ProviderAdapter)
    assert isinstance(provider, MarketDataProvider)
    assert provider.capability.provider_name == "qfusion-synthetic-mock"
    assert provider.capability.supports_realtime is False
    assert provider.capability.license_scope == "test-only"
    assert tuple(item.data_quality for item in provider.access_profile.market_data_quality) == (
        DataDeliveryQuality.SYNTHETIC_MOCK,
        DataDeliveryQuality.SYNTHETIC_MOCK,
    )


def test_mock_provider_returns_deterministic_point_in_time_daily_bars() -> None:
    accepted = make_record()
    minute = make_record(
        UUID("10000000-0000-4000-8000-000000000002"),
        fact_type="minute_bar",
    )
    other_instrument = make_record(
        UUID("10000000-0000-4000-8000-000000000003"),
        instrument_id=OTHER_INSTRUMENT_ID,
    )
    outside_range = make_record(
        UUID("10000000-0000-4000-8000-000000000004"),
        event_time=EVENT_TIME - timedelta(days=2),
        published_at=EVENT_TIME - timedelta(days=2) + timedelta(minutes=1),
        available_at=EVENT_TIME - timedelta(days=2) + timedelta(minutes=2),
        received_at=EVENT_TIME - timedelta(days=2) + timedelta(minutes=3),
        ingested_at=EVENT_TIME - timedelta(days=2) + timedelta(minutes=4),
    )
    future = make_record(
        UUID("10000000-0000-4000-8000-000000000005"),
        available_at=DECISION_TIME + timedelta(minutes=1),
        received_at=DECISION_TIME + timedelta(minutes=2),
        ingested_at=DECISION_TIME + timedelta(minutes=3),
    )
    provider = make_provider(
        [future, minute, other_instrument, outside_range, accepted],
    )
    request = make_request()

    first = asyncio.run(provider.get_bars(request))
    second = asyncio.run(provider.get_bars(request))

    assert first == second == (accepted,)
    assert all(record.available_at <= request.decision_time for record in first)
    assert all(record.instrument_id == INSTRUMENT_ID for record in first)


def test_mock_provider_selects_minute_fact_type_and_supports_empty_response() -> None:
    daily = make_record()
    minute = make_record(
        UUID("10000000-0000-4000-8000-000000000002"),
        fact_type="minute_bar",
    )
    provider = make_provider([daily, minute])

    result = asyncio.run(provider.get_bars(make_request(interval=DataInterval.MINUTE_1)))
    assert result == (minute,)

    empty = make_provider([])
    assert asyncio.run(empty.get_bars(make_request())) == ()


def test_mock_provider_copies_seed_records_and_mapping() -> None:
    accepted = make_record()
    records = [accepted]
    instrument_map = {INSTRUMENT_ID: "opaque-instrument-1"}
    provider = SyntheticMockMarketDataProvider(records, instrument_map)

    records.clear()
    instrument_map[INSTRUMENT_ID] = "mutated"

    assert asyncio.run(provider.get_bars(make_request())) == (accepted,)


def test_mock_provider_rejects_unknown_or_mismatched_provider_instrument_id() -> None:
    provider = SyntheticMockMarketDataProvider(
        [make_record()],
        {INSTRUMENT_ID: "opaque-instrument-1"},
    )

    with raises(ValueError, match="does not match"):
        asyncio.run(
            provider.get_bars(
                make_request(provider_instrument_id="different-provider-id"),
            )
        )

    with raises(LookupError, match="not mapped"):
        asyncio.run(
            provider.get_bars(
                make_request(
                    instrument_id=OTHER_INSTRUMENT_ID,
                    provider_instrument_id="opaque-instrument-2",
                )
            )
        )


def test_mock_provider_rejects_invalid_instrument_maps() -> None:
    with raises(ValueError, match="must not be empty"):
        SyntheticMockMarketDataProvider([], {})
    with raises(ValueError, match="non-empty and trimmed"):
        SyntheticMockMarketDataProvider([], {INSTRUMENT_ID: ""})
    with raises(ValueError, match="non-empty and trimmed"):
        SyntheticMockMarketDataProvider([], {INSTRUMENT_ID: " untrimmed "})
    with raises(ValueError, match="must be unique"):
        SyntheticMockMarketDataProvider(
            [],
            {
                INSTRUMENT_ID: "duplicate",
                OTHER_INSTRUMENT_ID: "duplicate",
            },
        )


def test_mock_provider_rejects_duplicate_fact_identifiers() -> None:
    record = make_record()
    with raises(ValueError, match="unique fact_id"):
        make_provider([record, record])


@mark.parametrize(
    ("field", "value", "message"),
    [
        ("instrument_id", None, "mapped instrument_id"),
        ("instrument_id", UUID("20000000-0000-4000-8000-000000000099"), "mapped"),
        ("fact_type", "news", "only bar facts"),
        ("source", "wrong-source", "source does not match"),
        ("provider_version", "9.9.9", "provider_version"),
        ("source_quality_level", "unknown", "quality level"),
        ("venue_scope", "wrong-venue", "venue scope"),
        ("license_scope", "redistributable", "license scope"),
        ("quality_flag", QualityFlag.OK, "SYNTHETIC_MOCK"),
    ],
)
def test_mock_provider_rejects_records_outside_synthetic_contract(
    field: str,
    value: object,
    message: str,
) -> None:
    record = make_record(**{field: value})
    with raises(ValueError, match=message):
        make_provider([record])
