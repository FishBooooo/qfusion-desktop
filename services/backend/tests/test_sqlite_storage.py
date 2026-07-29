"""SQLite metadata migration and repository tests."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from sqlalchemy import delete, func, inspect, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from qfusion.domain import (
    AnalysisSnapshot,
    Market,
    RequestedHorizon,
    SnapshotRepository,
    TargetType,
)
from qfusion.storage import (
    DuplicateSnapshotError,
    SnapshotIntegrityError,
    SqlAlchemySnapshotRepository,
    create_alembic_config,
    create_session_factory,
    create_sqlite_engine,
    current_database_revision,
    upgrade_database,
)
from qfusion.storage.models import AnalysisSnapshotRow, Base, SnapshotFactReferenceRow
from qfusion.storage.types import UTCDateTime

SNAPSHOT_ID = UUID("30000000-0000-4000-8000-000000000101")
SECOND_SNAPSHOT_ID = UUID("30000000-0000-4000-8000-000000000102")
TARGET_ID = UUID("40000000-0000-4000-8000-000000000101")
FIRST_FACT_ID = UUID("10000000-0000-4000-8000-000000000102")
SECOND_FACT_ID = UUID("10000000-0000-4000-8000-000000000101")
DECISION_TIME = datetime(2026, 7, 29, 14, 30, tzinfo=UTC)


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
        "fundamental_as_of": DECISION_TIME - timedelta(minutes=2),
        "provider_versions": {"synthetic": "1.0.0"},
        "dataset_versions": {"bars": "mock-bars-v1"},
        "fact_ids": (FIRST_FACT_ID, SECOND_FACT_ID),
        "missing_data": ("options",),
        "stale_data": ("news",),
        "quality_score": 0.75,
    }
    data.update(overrides)
    return AnalysisSnapshot.model_validate(data)


@pytest.fixture
def migrated_engine(tmp_path: Path) -> Iterator[Engine]:
    database_path = (tmp_path / "app.sqlite3").resolve()
    engine = create_sqlite_engine(database_path)
    upgrade_database(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def test_sqlite_engine_rejects_ambiguous_paths_and_enables_foreign_keys(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="absolute"):
        create_sqlite_engine(Path("relative.sqlite3"))

    with pytest.raises(FileNotFoundError, match="parent"):
        create_sqlite_engine((tmp_path / "missing" / "app.sqlite3").resolve())

    with pytest.raises(ValueError, match="file"):
        create_sqlite_engine(tmp_path.resolve())

    engine = create_sqlite_engine((tmp_path / "foreign-keys.sqlite3").resolve())
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
    finally:
        engine.dispose()


def test_migration_is_idempotent_reversible_and_matches_orm(tmp_path: Path) -> None:
    engine = create_sqlite_engine((tmp_path / "migration.sqlite3").resolve())
    try:
        assert current_database_revision(engine) is None

        upgrade_database(engine)
        upgrade_database(engine)

        assert current_database_revision(engine) == "0001_m1b_snapshots"
        inspector = inspect(engine)
        expected_tables = {"analysis_snapshots", "analysis_snapshot_facts"}
        assert expected_tables <= set(inspector.get_table_names())

        for table_name in expected_tables:
            migrated_columns = {column["name"] for column in inspector.get_columns(table_name)}
            mapped_columns = set(Base.metadata.tables[table_name].columns.keys())
            assert migrated_columns == mapped_columns

        configuration = create_alembic_config()
        with engine.begin() as connection:
            configuration.attributes["connection"] = connection
            command.downgrade(configuration, "base")

        assert current_database_revision(engine) is None
        downgraded_tables = set(inspect(engine).get_table_names())
        assert expected_tables.isdisjoint(downgraded_tables)

        upgrade_database(engine)
        assert current_database_revision(engine) == "0001_m1b_snapshots"
    finally:
        engine.dispose()


def test_snapshot_repository_round_trips_immutable_metadata(
    migrated_engine: Engine,
) -> None:
    repository = SqlAlchemySnapshotRepository(create_session_factory(migrated_engine))
    offset = timezone(timedelta(hours=-4))
    snapshot = make_snapshot(
        decision_time=DECISION_TIME.astimezone(offset),
        created_at=(DECISION_TIME + timedelta(seconds=1)).astimezone(offset),
    )

    assert isinstance(repository, SnapshotRepository)
    assert asyncio.run(repository.get(SNAPSHOT_ID)) is None

    asyncio.run(repository.add(snapshot))
    restored = asyncio.run(repository.get(SNAPSHOT_ID))

    assert restored == snapshot
    assert restored is not None
    assert restored.decision_time.tzinfo is UTC
    assert restored.fact_ids == (SECOND_FACT_ID, FIRST_FACT_ID)
    assert restored.content_fingerprint() == snapshot.content_fingerprint()


def test_snapshot_repository_rejects_duplicate_identity(
    migrated_engine: Engine,
) -> None:
    repository = SqlAlchemySnapshotRepository(create_session_factory(migrated_engine))
    snapshot = make_snapshot()

    asyncio.run(repository.add(snapshot))

    with pytest.raises(DuplicateSnapshotError, match=str(SNAPSHOT_ID)):
        asyncio.run(repository.add(snapshot))


def test_snapshot_fact_references_cascade_only_with_snapshot(
    migrated_engine: Engine,
) -> None:
    session_factory = create_session_factory(migrated_engine)
    repository = SqlAlchemySnapshotRepository(session_factory)
    asyncio.run(repository.add(make_snapshot()))

    with session_factory() as session:
        reference_count = session.scalar(
            select(func.count()).select_from(SnapshotFactReferenceRow)
        )
        assert reference_count == 2

    with migrated_engine.begin() as connection:
        connection.execute(
            delete(AnalysisSnapshotRow).where(
                AnalysisSnapshotRow.snapshot_id == SNAPSHOT_ID
            )
        )

    with session_factory() as session:
        reference_count = session.scalar(
            select(func.count()).select_from(SnapshotFactReferenceRow)
        )
        assert reference_count == 0


def test_physical_schema_rejects_future_as_of_timestamp(
    migrated_engine: Engine,
) -> None:
    repository = SqlAlchemySnapshotRepository(create_session_factory(migrated_engine))
    asyncio.run(repository.add(make_snapshot()))

    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as connection:
            connection.execute(
                update(AnalysisSnapshotRow)
                .where(AnalysisSnapshotRow.snapshot_id == SNAPSHOT_ID)
                .values(price_as_of=DECISION_TIME + timedelta(seconds=1))
            )


def test_repository_detects_fingerprint_and_contract_corruption(
    migrated_engine: Engine,
) -> None:
    repository = SqlAlchemySnapshotRepository(create_session_factory(migrated_engine))
    asyncio.run(repository.add(make_snapshot()))
    asyncio.run(
        repository.add(
            make_snapshot(
                snapshot_id=SECOND_SNAPSHOT_ID,
                fact_ids=(),
            )
        )
    )

    with migrated_engine.begin() as connection:
        connection.execute(
            update(AnalysisSnapshotRow)
            .where(AnalysisSnapshotRow.snapshot_id == SNAPSHOT_ID)
            .values(content_fingerprint="0" * 64)
        )
        connection.execute(
            update(AnalysisSnapshotRow)
            .where(AnalysisSnapshotRow.snapshot_id == SECOND_SNAPSHOT_ID)
            .values(requested_horizon="unsupported")
        )

    with pytest.raises(SnapshotIntegrityError, match="fingerprint"):
        asyncio.run(repository.get(SNAPSHOT_ID))

    with pytest.raises(SnapshotIntegrityError, match="invalid persisted"):
        asyncio.run(repository.get(SECOND_SNAPSHOT_ID))


def test_utc_datetime_type_requires_awareness_and_restores_utc(
    migrated_engine: Engine,
) -> None:
    utc_type = UTCDateTime()
    dialect = migrated_engine.dialect
    offset_value = datetime(
        2026,
        7,
        29,
        10,
        30,
        tzinfo=timezone(timedelta(hours=-4)),
    )

    assert utc_type.process_bind_param(None, dialect) is None
    assert utc_type.process_bind_param(offset_value, dialect) == datetime(
        2026,
        7,
        29,
        14,
        30,
    )
    with pytest.raises(TypeError, match="timezone-aware"):
        utc_type.process_bind_param(datetime(2026, 7, 29, 14, 30), dialect)

    assert utc_type.process_result_value(None, dialect) is None
    assert utc_type.process_result_value(
        datetime(2026, 7, 29, 14, 30),
        dialect,
    ) == datetime(2026, 7, 29, 14, 30, tzinfo=UTC)
    assert utc_type.process_result_value(offset_value, dialect) == DECISION_TIME
