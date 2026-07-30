"""SQLite Instrument Registry migration, Repository, and Synthetic Mock tests."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import inspect, select, text, update
from sqlalchemy.engine import Engine

from qfusion.domain import (
    DataSourceRecord,
    Instrument,
    InstrumentAssetType,
    InstrumentQuery,
    InstrumentRegistryRepository,
    Market,
    ProviderIdentifierLookup,
    ProviderInstrumentMapping,
    ProviderMappingLookup,
    QualityFlag,
    TickerAlias,
    TickerLookup,
)
from qfusion.providers import (
    DataInterval,
    ProviderBarRequest,
    SyntheticMockMarketDataProvider,
)
from qfusion.storage import (
    DuplicateInstrumentError,
    InstrumentIdentifierConflictError,
    InstrumentRegistryIntegrityError,
    SqlAlchemyInstrumentRegistryRepository,
    create_session_factory,
    create_sqlite_engine,
    upgrade_database,
)
from qfusion.storage.models import InstrumentRow, TickerAliasRow

INSTRUMENT_ID = UUID("61000000-0000-4000-8000-000000000001")
SECOND_INSTRUMENT_ID = UUID("61000000-0000-4000-8000-000000000002")
ALIAS_ID = UUID("62000000-0000-4000-8000-000000000001")
MAPPING_ID = UUID("63000000-0000-4000-8000-000000000001")
REGISTERED_AT = datetime(2025, 1, 1, tzinfo=UTC)
VALID_FROM = datetime(2025, 1, 2, tzinfo=UTC)
VALID_TO = datetime(2026, 1, 1, tzinfo=UTC)
DECISION_TIME = datetime(2025, 7, 1, 14, 30, tzinfo=UTC)


def make_instrument(**overrides: object) -> Instrument:
    values: dict[str, object] = {
        "instrument_id": INSTRUMENT_ID,
        "market": Market.US,
        "asset_type": InstrumentAssetType.STOCK,
        "display_name": "Synthetic QFusion Technology",
        "registered_at": REGISTERED_AT,
    }
    values.update(overrides)
    return Instrument.model_validate(values)


def make_alias(**overrides: object) -> TickerAlias:
    values: dict[str, object] = {
        "alias_id": ALIAS_ID,
        "instrument_id": INSTRUMENT_ID,
        "market": Market.US,
        "ticker": "QFUS",
        "valid_from": VALID_FROM,
        "valid_to": VALID_TO,
        "available_at": VALID_FROM,
        "source": "synthetic-registry",
        "source_record_id": "ticker-qfus-1",
        "revision_id": "revision-1",
    }
    values.update(overrides)
    return TickerAlias.model_validate(values)


def make_mapping(**overrides: object) -> ProviderInstrumentMapping:
    values: dict[str, object] = {
        "mapping_id": MAPPING_ID,
        "instrument_id": INSTRUMENT_ID,
        "market": Market.US,
        "provider_name": "qfusion-synthetic-mock",
        "provider_instrument_id": "US-QFUS-PRIMARY",
        "provider_version": "1.0.0",
        "valid_from": VALID_FROM,
        "valid_to": VALID_TO,
        "available_at": VALID_FROM,
        "source_record_id": "provider-qfus-1",
        "revision_id": "revision-1",
    }
    values.update(overrides)
    return ProviderInstrumentMapping.model_validate(values)


@pytest.fixture
def migrated_engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_sqlite_engine((tmp_path / "registry.sqlite3").resolve())
    upgrade_database(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def registry(
    migrated_engine: Engine,
) -> SqlAlchemyInstrumentRegistryRepository:
    return SqlAlchemyInstrumentRegistryRepository(create_session_factory(migrated_engine))


def add_default_registry(repository: SqlAlchemyInstrumentRegistryRepository) -> None:
    asyncio.run(repository.add_instrument(make_instrument()))
    asyncio.run(repository.add_ticker_alias(make_alias()))
    asyncio.run(repository.add_provider_mapping(make_mapping()))


def test_registry_round_trips_permanent_and_external_identities(
    registry: SqlAlchemyInstrumentRegistryRepository,
) -> None:
    assert isinstance(registry, InstrumentRegistryRepository)
    add_default_registry(registry)

    too_early = InstrumentQuery(
        instrument_id=INSTRUMENT_ID,
        decision_time=REGISTERED_AT - timedelta(microseconds=1),
    )
    current = InstrumentQuery(
        instrument_id=INSTRUMENT_ID,
        decision_time=DECISION_TIME,
    )
    ticker_query = TickerLookup(
        market=Market.US,
        ticker="qfus",
        effective_at=DECISION_TIME,
        decision_time=DECISION_TIME,
    )
    mapping_query = ProviderMappingLookup(
        instrument_id=INSTRUMENT_ID,
        provider_name="QFUSION-SYNTHETIC-MOCK",
        market=Market.US,
        effective_at=DECISION_TIME,
        decision_time=DECISION_TIME,
    )
    identifier_query = ProviderIdentifierLookup(
        provider_name="qfusion-synthetic-mock",
        provider_instrument_id="US-QFUS-PRIMARY",
        market=Market.US,
        effective_at=DECISION_TIME,
        decision_time=DECISION_TIME,
    )

    assert asyncio.run(registry.get_instrument(too_early)) is None
    assert asyncio.run(registry.get_instrument(current)) == make_instrument()
    assert asyncio.run(registry.resolve_ticker(ticker_query)) == make_alias()
    assert asyncio.run(registry.get_provider_mapping(mapping_query)) == make_mapping()
    assert asyncio.run(registry.resolve_provider_identifier(identifier_query)) == make_mapping()

    wrong_case = identifier_query.model_copy(
        update={"provider_instrument_id": "us-qfus-primary"}
    )
    assert asyncio.run(registry.resolve_provider_identifier(wrong_case)) is None


def test_registry_applies_effective_and_knowledge_time_independently(
    registry: SqlAlchemyInstrumentRegistryRepository,
) -> None:
    asyncio.run(registry.add_instrument(make_instrument()))
    alias = make_alias(available_at=DECISION_TIME)
    asyncio.run(registry.add_ticker_alias(alias))

    before_knowledge = TickerLookup(
        market=Market.US,
        ticker="QFUS",
        effective_at=DECISION_TIME - timedelta(days=1),
        decision_time=DECISION_TIME - timedelta(microseconds=1),
    )
    at_knowledge = before_knowledge.model_copy(
        update={"decision_time": DECISION_TIME}
    )
    at_exclusive_end = TickerLookup(
        market=Market.US,
        ticker="QFUS",
        effective_at=VALID_TO,
        decision_time=VALID_TO,
    )

    assert asyncio.run(registry.resolve_ticker(before_knowledge)) is None
    assert asyncio.run(registry.resolve_ticker(at_knowledge)) == alias
    assert asyncio.run(registry.resolve_ticker(at_exclusive_end)) is None


def test_ticker_change_and_reuse_do_not_change_permanent_identity(
    registry: SqlAlchemyInstrumentRegistryRepository,
) -> None:
    change_time = datetime(2025, 6, 1, tzinfo=UTC)
    reuse_time = datetime(2025, 9, 1, tzinfo=UTC)
    first_instrument = make_instrument()
    second_instrument = make_instrument(
        instrument_id=SECOND_INSTRUMENT_ID,
        display_name="Synthetic Reuser",
    )
    old_alias = make_alias(valid_to=change_time)
    new_alias = make_alias(
        alias_id=UUID("62000000-0000-4000-8000-000000000002"),
        ticker="QNEW",
        valid_from=change_time,
        valid_to=None,
        source_record_id="ticker-qnew-1",
    )
    reused_alias = make_alias(
        alias_id=UUID("62000000-0000-4000-8000-000000000003"),
        instrument_id=SECOND_INSTRUMENT_ID,
        valid_from=reuse_time,
        valid_to=None,
        available_at=reuse_time,
        source_record_id="ticker-qfus-2",
    )

    asyncio.run(registry.add_instrument(first_instrument))
    asyncio.run(registry.add_instrument(second_instrument))
    asyncio.run(registry.add_ticker_alias(old_alias))
    asyncio.run(registry.add_ticker_alias(new_alias))
    asyncio.run(registry.add_ticker_alias(reused_alias))

    old_lookup = TickerLookup(
        market=Market.US,
        ticker="QFUS",
        effective_at=change_time - timedelta(microseconds=1),
        decision_time=DECISION_TIME,
    )
    gap_lookup = old_lookup.model_copy(
        update={"effective_at": change_time, "decision_time": DECISION_TIME}
    )
    reused_lookup = old_lookup.model_copy(
        update={"effective_at": reuse_time, "decision_time": reuse_time}
    )
    new_lookup = old_lookup.model_copy(
        update={"ticker": "QNEW", "effective_at": change_time}
    )

    assert asyncio.run(registry.resolve_ticker(old_lookup)) == old_alias
    assert asyncio.run(registry.resolve_ticker(gap_lookup)) is None
    assert asyncio.run(registry.resolve_ticker(reused_lookup)) == reused_alias
    assert asyncio.run(registry.resolve_ticker(new_lookup)) == new_alias


def test_registry_rejects_duplicate_and_overlapping_ticker_aliases(
    registry: SqlAlchemyInstrumentRegistryRepository,
) -> None:
    asyncio.run(registry.add_instrument(make_instrument()))
    asyncio.run(registry.add_ticker_alias(make_alias()))

    with pytest.raises(DuplicateInstrumentError, match=str(INSTRUMENT_ID)):
        asyncio.run(registry.add_instrument(make_instrument()))
    with pytest.raises(InstrumentIdentifierConflictError, match="ticker alias"):
        asyncio.run(
            registry.add_ticker_alias(
                make_alias(
                    alias_id=UUID("62000000-0000-4000-8000-000000000004"),
                    valid_from=VALID_FROM + timedelta(days=1),
                )
            )
        )

    adjacent = make_alias(
        alias_id=UUID("62000000-0000-4000-8000-000000000005"),
        valid_from=VALID_TO,
        valid_to=None,
        available_at=VALID_TO,
        source_record_id="ticker-qfus-adjacent",
    )
    asyncio.run(registry.add_ticker_alias(adjacent))


def test_registry_rejects_both_provider_overlap_directions(
    registry: SqlAlchemyInstrumentRegistryRepository,
) -> None:
    asyncio.run(registry.add_instrument(make_instrument()))
    asyncio.run(
        registry.add_instrument(
            make_instrument(
                instrument_id=SECOND_INSTRUMENT_ID,
                display_name="Synthetic Second Instrument",
            )
        )
    )
    asyncio.run(registry.add_provider_mapping(make_mapping()))

    with pytest.raises(InstrumentIdentifierConflictError, match="provider mapping"):
        asyncio.run(
            registry.add_provider_mapping(
                make_mapping(
                    mapping_id=UUID("63000000-0000-4000-8000-000000000002"),
                    instrument_id=SECOND_INSTRUMENT_ID,
                )
            )
        )

    with pytest.raises(InstrumentIdentifierConflictError, match="provider mapping"):
        asyncio.run(
            registry.add_provider_mapping(
                make_mapping(
                    mapping_id=UUID("63000000-0000-4000-8000-000000000003"),
                    provider_instrument_id="US-QFUS-SECONDARY",
                )
            )
        )


def test_registry_rejects_unknown_mismatched_or_predating_instrument(
    registry: SqlAlchemyInstrumentRegistryRepository,
) -> None:
    with pytest.raises(InstrumentIdentifierConflictError):
        asyncio.run(registry.add_ticker_alias(make_alias()))

    asyncio.run(registry.add_instrument(make_instrument()))
    with pytest.raises(InstrumentIdentifierConflictError):
        asyncio.run(
            registry.add_ticker_alias(
                make_alias(
                    alias_id=UUID("62000000-0000-4000-8000-000000000006"),
                    market=Market.HK,
                )
            )
        )
    with pytest.raises(InstrumentIdentifierConflictError):
        asyncio.run(
            registry.add_provider_mapping(
                make_mapping(
                    mapping_id=UUID("63000000-0000-4000-8000-000000000004"),
                    available_at=REGISTERED_AT - timedelta(microseconds=1),
                )
            )
        )


def test_migration_installs_overlap_and_registration_triggers(
    migrated_engine: Engine,
) -> None:
    expected = {
        "trg_ticker_alias_no_overlap_insert",
        "trg_ticker_alias_no_overlap_update",
        "trg_provider_identifier_no_overlap_insert",
        "trg_provider_identifier_no_overlap_update",
        "trg_provider_instrument_no_overlap_insert",
        "trg_provider_instrument_no_overlap_update",
        "trg_ticker_alias_registration_insert",
        "trg_ticker_alias_registration_update",
        "trg_provider_mapping_registration_insert",
        "trg_provider_mapping_registration_update",
    }
    with migrated_engine.connect() as connection:
        names = set(
            connection.scalars(
                text("SELECT name FROM sqlite_master WHERE type = 'trigger'")
            ).all()
        )
    assert expected <= names


def test_registry_detects_persisted_domain_corruption(
    migrated_engine: Engine,
    registry: SqlAlchemyInstrumentRegistryRepository,
) -> None:
    add_default_registry(registry)

    with migrated_engine.begin() as connection:
        connection.execute(
            update(InstrumentRow)
            .where(InstrumentRow.instrument_id == INSTRUMENT_ID)
            .values(schema_version="broken")
        )
        connection.execute(
            update(TickerAliasRow)
            .where(TickerAliasRow.alias_id == ALIAS_ID)
            .values(source="")
        )

    with pytest.raises(InstrumentRegistryIntegrityError, match="invalid persisted instrument"):
        asyncio.run(
            registry.get_instrument(
                InstrumentQuery(
                    instrument_id=INSTRUMENT_ID,
                    decision_time=DECISION_TIME,
                )
            )
        )
    with pytest.raises(InstrumentRegistryIntegrityError, match="invalid persisted ticker"):
        asyncio.run(
            registry.resolve_ticker(
                TickerLookup(
                    market=Market.US,
                    ticker="QFUS",
                    effective_at=DECISION_TIME,
                    decision_time=DECISION_TIME,
                )
            )
        )


def test_migration_columns_match_registry_orm_metadata(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    table_names = (
        "instruments",
        "instrument_ticker_aliases",
        "provider_instrument_mappings",
    )
    for table_name in table_names:
        assert table_name in inspector.get_table_names()
        assert inspector.get_columns(table_name)


def test_registry_mapping_drives_network_free_synthetic_provider(
    registry: SqlAlchemyInstrumentRegistryRepository,
) -> None:
    add_default_registry(registry)
    mapping = asyncio.run(
        registry.get_provider_mapping(
            ProviderMappingLookup(
                instrument_id=INSTRUMENT_ID,
                provider_name="qfusion-synthetic-mock",
                market=Market.US,
                effective_at=DECISION_TIME,
                decision_time=DECISION_TIME,
            )
        )
    )
    assert mapping is not None

    event_time = DECISION_TIME - timedelta(minutes=5)
    record = DataSourceRecord(
        fact_id=UUID("64000000-0000-4000-8000-000000000001"),
        instrument_id=INSTRUMENT_ID,
        fact_type="minute_bar",
        source="qfusion-synthetic-mock",
        source_record_id="mock-registry-bar",
        source_quality_level="synthetic",
        venue_scope="synthetic-us-hk",
        license_scope="test-only",
        provider_version="1.0.0",
        dataset_version="registry-integration-v1",
        event_time=event_time,
        published_at=event_time,
        available_at=event_time,
        received_at=event_time,
        ingested_at=event_time,
        revision_id="revision-1",
        quality_flag=QualityFlag.SYNTHETIC_MOCK,
        raw_payload_hash="a" * 64,
        payload={"close": "100.00"},
    )
    provider = SyntheticMockMarketDataProvider(
        records=(record,),
        instrument_map={
            INSTRUMENT_ID: (mapping.provider_instrument_id, mapping.market)
        },
    )
    request = ProviderBarRequest(
        instrument_id=INSTRUMENT_ID,
        provider_instrument_id=mapping.provider_instrument_id,
        market=mapping.market,
        interval=DataInterval.MINUTE_1,
        start=event_time - timedelta(minutes=1),
        end=event_time + timedelta(minutes=1),
        decision_time=DECISION_TIME,
    )

    assert asyncio.run(provider.get_bars(request)) == (record,)


def test_registry_tables_are_not_used_as_ticker_primary_keys(
    migrated_engine: Engine,
) -> None:
    inspector = inspect(migrated_engine)
    instrument_pk = inspector.get_pk_constraint("instruments")["constrained_columns"]
    ticker_pk = inspector.get_pk_constraint("instrument_ticker_aliases")["constrained_columns"]

    assert instrument_pk == ["instrument_id"]
    assert ticker_pk == ["alias_id"]
    assert "ticker" not in instrument_pk
    assert "ticker" not in ticker_pk

    with migrated_engine.connect() as connection:
        assert connection.scalar(select(text("1"))) == 1
