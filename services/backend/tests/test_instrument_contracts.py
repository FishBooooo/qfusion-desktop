"""Permanent instrument and Point-in-Time identifier contract tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from qfusion.domain import (
    Instrument,
    InstrumentAssetType,
    InstrumentQuery,
    Market,
    ProviderIdentifierLookup,
    ProviderInstrumentMapping,
    ProviderMappingLookup,
    TickerAlias,
    TickerLookup,
    require_instrument_available,
    require_provider_identifier_match,
    require_provider_mapping_match,
    require_ticker_match,
)

INSTRUMENT_ID = UUID("51000000-0000-4000-8000-000000000001")
OTHER_INSTRUMENT_ID = UUID("51000000-0000-4000-8000-000000000002")
ALIAS_ID = UUID("52000000-0000-4000-8000-000000000001")
MAPPING_ID = UUID("53000000-0000-4000-8000-000000000001")
VALID_FROM = datetime(2025, 1, 1, tzinfo=UTC)
VALID_TO = datetime(2026, 1, 1, tzinfo=UTC)
DECISION_TIME = datetime(2025, 7, 1, tzinfo=UTC)


def make_instrument(**overrides: object) -> Instrument:
    values: dict[str, object] = {
        "instrument_id": INSTRUMENT_ID,
        "market": Market.US,
        "asset_type": InstrumentAssetType.STOCK,
        "display_name": "Synthetic Technology Inc.",
        "source": "synthetic-registry",
        "source_record_id": "instrument-qfus-1",
        "source_version": "1.0.0",
        "revision_id": "revision-1",
        "registered_at": VALID_FROM - timedelta(days=1),
    }
    values.update(overrides)
    return Instrument.model_validate(values)


def make_alias(**overrides: object) -> TickerAlias:
    values: dict[str, object] = {
        "alias_id": ALIAS_ID,
        "instrument_id": INSTRUMENT_ID,
        "market": Market.US,
        "ticker": "qfus",
        "valid_from": VALID_FROM,
        "valid_to": VALID_TO,
        "available_at": VALID_FROM - timedelta(hours=1),
        "source": "synthetic-registry",
        "source_record_id": "ticker-qfus-1",
        "source_version": "1.0.0",
        "revision_id": "revision-1",
    }
    values.update(overrides)
    return TickerAlias.model_validate(values)


def make_mapping(**overrides: object) -> ProviderInstrumentMapping:
    values: dict[str, object] = {
        "mapping_id": MAPPING_ID,
        "instrument_id": INSTRUMENT_ID,
        "market": Market.US,
        "provider_name": "QFusion-Synthetic-Mock",
        "provider_instrument_id": "Us/QFus:Primary",
        "provider_version": "1.0.0",
        "valid_from": VALID_FROM,
        "valid_to": VALID_TO,
        "available_at": VALID_FROM - timedelta(minutes=30),
        "source_record_id": "provider-qfus-1",
        "revision_id": "revision-1",
    }
    values.update(overrides)
    return ProviderInstrumentMapping.model_validate(values)


def test_instrument_normalizes_registration_to_utc_and_is_immutable() -> None:
    offset = timezone(timedelta(hours=-5))
    instrument = make_instrument(
        display_name="  Synthetic Technology Inc.  ",
        registered_at=datetime(2024, 12, 31, 18, 0, tzinfo=offset),
    )

    assert instrument.display_name == "Synthetic Technology Inc."
    assert instrument.registered_at == datetime(2024, 12, 31, 23, 0, tzinfo=UTC)
    assert instrument.is_available_at(DECISION_TIME)

    with pytest.raises(ValidationError):
        make_instrument(unexpected="forbidden")
    with pytest.raises(ValidationError, match="timezone-aware"):
        make_instrument(registered_at=datetime(2025, 1, 1))
    with pytest.raises(ValidationError):
        instrument.display_name = "mutated"


def test_ticker_alias_normalizes_and_uses_half_open_interval() -> None:
    alias = make_alias(ticker=" qfus ")

    assert alias.ticker == "QFUS"
    assert alias.is_effective_at(VALID_FROM)
    assert alias.is_effective_at(VALID_TO - timedelta(microseconds=1))
    assert not alias.is_effective_at(VALID_TO)
    assert alias.is_available_at(DECISION_TIME)


@pytest.mark.parametrize("ticker", ["Q FUS", "QFUS$", "台積電"])
def test_ticker_alias_rejects_unsupported_values(ticker: str) -> None:
    with pytest.raises(ValidationError, match="ticker"):
        make_alias(ticker=ticker)


def test_effective_identifier_rejects_invalid_or_naive_times() -> None:
    with pytest.raises(ValidationError, match="valid_from"):
        make_alias(valid_to=VALID_FROM)
    with pytest.raises(ValidationError, match="timezone-aware"):
        make_alias(valid_from=datetime(2025, 1, 1))
    with pytest.raises(ValueError, match="timezone-aware"):
        make_alias().is_effective_at(datetime(2025, 7, 1))


def test_provider_mapping_normalizes_name_but_preserves_opaque_identifier_case() -> None:
    mapping = make_mapping(
        provider_name="  QFUSION-SYNTHETIC-MOCK  ",
        provider_instrument_id="  Us/QFus:Primary  ",
    )

    assert mapping.provider_name == "qfusion-synthetic-mock"
    assert mapping.provider_instrument_id == "Us/QFus:Primary"

    with pytest.raises(ValidationError, match="control"):
        make_mapping(provider_instrument_id="bad\x00id")


def test_effective_lookup_rejects_future_or_naive_query_time() -> None:
    with pytest.raises(ValidationError, match="effective_at"):
        TickerLookup(
            market=Market.US,
            ticker="QFUS",
            effective_at=DECISION_TIME + timedelta(seconds=1),
            decision_time=DECISION_TIME,
        )
    with pytest.raises(ValidationError, match="timezone-aware"):
        InstrumentQuery(
            instrument_id=INSTRUMENT_ID,
            decision_time=datetime(2025, 7, 1),
        )


def test_instrument_and_ticker_guards_reject_out_of_scope_results() -> None:
    instrument = make_instrument()
    instrument_query = InstrumentQuery(
        instrument_id=INSTRUMENT_ID,
        decision_time=DECISION_TIME,
    )
    ticker_query = TickerLookup(
        market=Market.US,
        ticker="qfus",
        effective_at=DECISION_TIME,
        decision_time=DECISION_TIME,
    )

    assert require_instrument_available(instrument_query, instrument) is instrument
    assert require_ticker_match(ticker_query, make_alias()) == make_alias()

    with pytest.raises(ValueError, match="different instrument_id"):
        require_instrument_available(
            instrument_query,
            make_instrument(instrument_id=OTHER_INSTRUMENT_ID),
        )
    with pytest.raises(ValueError, match="unavailable"):
        require_instrument_available(
            instrument_query,
            make_instrument(registered_at=DECISION_TIME + timedelta(seconds=1)),
        )
    with pytest.raises(ValueError, match="lookup key"):
        require_ticker_match(ticker_query, make_alias(ticker="OTHER"))
    with pytest.raises(ValueError, match="effective_at"):
        require_ticker_match(
            ticker_query,
            make_alias(valid_from=DECISION_TIME + timedelta(seconds=1), valid_to=None),
        )
    with pytest.raises(ValueError, match="decision_time"):
        require_ticker_match(
            ticker_query,
            make_alias(available_at=DECISION_TIME + timedelta(seconds=1)),
        )


def test_provider_guards_keep_identifier_and_instrument_lookups_distinct() -> None:
    mapping = make_mapping()
    identifier_query = ProviderIdentifierLookup(
        provider_name="QFusion-Synthetic-Mock",
        provider_instrument_id="Us/QFus:Primary",
        market=Market.US,
        effective_at=DECISION_TIME,
        decision_time=DECISION_TIME,
    )
    mapping_query = ProviderMappingLookup(
        instrument_id=INSTRUMENT_ID,
        provider_name="QFusion-Synthetic-Mock",
        market=Market.US,
        effective_at=DECISION_TIME,
        decision_time=DECISION_TIME,
    )

    assert require_provider_identifier_match(identifier_query, mapping) is mapping
    assert require_provider_mapping_match(mapping_query, mapping) is mapping

    with pytest.raises(ValueError, match="lookup key"):
        require_provider_identifier_match(
            identifier_query,
            make_mapping(provider_instrument_id="Us/qfus:primary"),
        )
    with pytest.raises(ValueError, match="instrument key"):
        require_provider_mapping_match(
            mapping_query,
            make_mapping(instrument_id=OTHER_INSTRUMENT_ID),
        )
