"""Deterministic AnalysisSnapshot construction and persistence tests."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from qfusion.domain import (
    AnalysisSnapshot,
    DataSourceRecord,
    FactQuery,
    Market,
    QualityFlag,
    RequestedHorizon,
    TargetType,
)
from qfusion.snapshots import (
    SnapshotBuilder,
    SnapshotBuildError,
    SnapshotBuildPolicy,
    SnapshotBuildRequest,
    SnapshotDataCategory,
    SnapshotFactRule,
    SnapshotFreshnessRule,
)
from qfusion.storage import (
    DuckDBFactRepository,
    FactWriteQueue,
    SqlAlchemySnapshotRepository,
    create_session_factory,
    create_sqlite_engine,
    upgrade_database,
)

_INSTRUMENT_ID = UUID("40000000-0000-4000-8000-000000000201")
_DECISION_TIME = datetime(2026, 7, 30, 14, 0, tzinfo=UTC)
_FIRST_SNAPSHOT_ID = UUID("50000000-0000-4000-8000-000000000201")
_SECOND_SNAPSHOT_ID = UUID("50000000-0000-4000-8000-000000000202")


def _record(
    sequence: int,
    fact_type: str,
    available_at: datetime,
    *,
    source: str = "M1-D Synthetic Mock",
    provider_version: str = "m1d.mock.1",
    dataset_version: str | None = None,
    quality_flag: QualityFlag = QualityFlag.SYNTHETIC_MOCK,
) -> DataSourceRecord:
    raw_content = f"m1d-{sequence}-{fact_type}".encode()
    is_adjusted = fact_type == "market.bar.daily"
    return DataSourceRecord(
        fact_id=UUID(f"60000000-0000-4000-8000-{sequence:012d}"),
        instrument_id=_INSTRUMENT_ID,
        fact_type=fact_type,
        source=source,
        source_record_id=f"m1d-{sequence}",
        source_quality_level="synthetic-contract-only",
        venue_scope="US synthetic fixture",
        license_scope="repository test fixture",
        provider_version=provider_version,
        dataset_version=dataset_version or f"m1d-{fact_type}-v1",
        event_time=available_at - timedelta(minutes=3),
        published_at=available_at - timedelta(minutes=2),
        available_at=available_at,
        received_at=available_at + timedelta(minutes=1),
        ingested_at=available_at + timedelta(minutes=2),
        revision_id="original",
        quality_flag=quality_flag,
        raw_payload_hash=hashlib.sha256(
            raw_content,
            usedforsecurity=False,
        ).hexdigest(),
        is_adjusted=is_adjusted,
        adjustment_type="split-and-dividend" if is_adjusted else None,
        payload={"mock": True, "sequence": sequence},
    )


def _request(**overrides: object) -> SnapshotBuildRequest:
    data: dict[str, object] = {
        "target_type": TargetType.STOCK,
        "target_id": _INSTRUMENT_ID,
        "market": Market.US,
        "requested_horizon": RequestedHorizon.FIVE_DAY,
        "decision_time": _DECISION_TIME,
        "instrument_ids": (_INSTRUMENT_ID,),
    }
    data.update(overrides)
    return SnapshotBuildRequest.model_validate(data)


class _FactRepository:
    def __init__(self, records: Sequence[DataSourceRecord]) -> None:
        self.records = tuple(records)
        self.queries: list[FactQuery] = []

    async def list_as_of(self, query: FactQuery) -> Sequence[DataSourceRecord]:
        self.queries.append(query)
        return self.records


class _SnapshotRepository:
    def __init__(self) -> None:
        self.snapshots: list[AnalysisSnapshot] = []

    async def add(self, snapshot: AnalysisSnapshot) -> None:
        self.snapshots.append(snapshot)

    async def get(self, snapshot_id: UUID) -> AnalysisSnapshot | None:
        return next(
            (item for item in self.snapshots if item.snapshot_id == snapshot_id),
            None,
        )


def test_builder_integrates_duckdb_and_sqlite_reproducibly(tmp_path: Path) -> None:
    database_root = tmp_path / "database"
    parquet_root = tmp_path / "parquet"
    database_root.mkdir()
    parquet_root.mkdir()

    fact_repository = DuckDBFactRepository(
        database_root / "warehouse.duckdb",
        parquet_root,
    )
    metadata_engine = create_sqlite_engine(database_root / "app.sqlite3")
    upgrade_database(metadata_engine)
    snapshot_repository = SqlAlchemySnapshotRepository(
        create_session_factory(metadata_engine)
    )

    records = (
        _record(1, "market.bar.daily", _DECISION_TIME - timedelta(hours=2)),
        _record(2, "market.bar.minute", _DECISION_TIME - timedelta(minutes=5)),
        _record(3, "filing", _DECISION_TIME - timedelta(days=1)),
        _record(4, "news", _DECISION_TIME - timedelta(minutes=30)),
        _record(5, "news", _DECISION_TIME + timedelta(hours=1)),
    )
    snapshot_ids = iter((_FIRST_SNAPSHOT_ID, _SECOND_SNAPSHOT_ID))
    builder = SnapshotBuilder(
        fact_repository,
        snapshot_repository,
        clock=lambda: _DECISION_TIME + timedelta(minutes=10),
        snapshot_id_factory=lambda: next(snapshot_ids),
    )

    async def scenario() -> tuple[AnalysisSnapshot, AnalysisSnapshot]:
        await fact_repository.initialize()
        async with FactWriteQueue(fact_repository) as writer:
            await writer.submit(records)
        first = await builder.build(_request())
        second = await builder.build(_request())
        assert await snapshot_repository.get(first.snapshot_id) == first
        assert await snapshot_repository.get(second.snapshot_id) == second
        return first, second

    try:
        first, second = asyncio.run(scenario())
    finally:
        metadata_engine.dispose()

    assert first.snapshot_id != second.snapshot_id
    assert first.created_at == second.created_at
    assert first.content_fingerprint() == second.content_fingerprint()
    assert first.fact_ids == tuple(record.fact_id for record in records[:4])
    assert records[4].fact_id not in first.fact_ids
    assert first.price_as_of == records[1].event_time
    assert first.fundamental_as_of == records[2].event_time
    assert first.news_as_of == records[3].event_time
    assert first.missing_data == ()
    assert first.stale_data == ()
    assert first.quality_score == 0.5
    assert first.provider_versions == {"M1-D Synthetic Mock": "m1d.mock.1"}
    assert first.dataset_versions == {
        f"M1-D Synthetic Mock::{record.fact_type}": record.dataset_version
        for record in records[:4]
    }


def test_builder_marks_missing_and_stale_categories_conservatively() -> None:
    price = _record(
        10,
        "market.bar.daily",
        _DECISION_TIME - timedelta(hours=2),
        quality_flag=QualityFlag.OK,
    )
    fact_repository = _FactRepository((price,))
    snapshot_repository = _SnapshotRepository()
    policy = SnapshotBuildPolicy(
        fact_rules=(
            SnapshotFactRule(
                fact_type="market.bar.daily",
                category=SnapshotDataCategory.PRICE,
            ),
            SnapshotFactRule(
                fact_type="news",
                category=SnapshotDataCategory.NEWS,
            ),
        ),
        required_categories=(
            SnapshotDataCategory.PRICE,
            SnapshotDataCategory.NEWS,
        ),
        freshness_rules=(
            SnapshotFreshnessRule(
                category=SnapshotDataCategory.PRICE,
                max_age=timedelta(minutes=30),
            ),
        ),
    )
    builder = SnapshotBuilder(
        fact_repository,
        snapshot_repository,
        policy=policy,
        clock=lambda: _DECISION_TIME + timedelta(seconds=1),
        snapshot_id_factory=lambda: _FIRST_SNAPSHOT_ID,
    )

    snapshot = asyncio.run(builder.build(_request()))

    assert snapshot.missing_data == ("news",)
    assert snapshot.stale_data == ("price",)
    assert snapshot.price_as_of == price.event_time
    assert snapshot.news_as_of is None
    assert snapshot.quality_score == 0.25
    assert snapshot_repository.snapshots == [snapshot]


def test_builder_rejects_repository_leakage_and_duplicate_facts() -> None:
    future = _record(20, "news", _DECISION_TIME + timedelta(minutes=1))
    duplicate = _record(21, "market.bar.daily", _DECISION_TIME - timedelta(minutes=1))

    async def scenario() -> None:
        leaking_builder = SnapshotBuilder(
            _FactRepository((future,)),
            _SnapshotRepository(),
            clock=lambda: _DECISION_TIME + timedelta(seconds=1),
        )
        with pytest.raises(SnapshotBuildError, match="Point-in-Time"):
            await leaking_builder.build(_request())

        duplicate_builder = SnapshotBuilder(
            _FactRepository((duplicate, duplicate)),
            _SnapshotRepository(),
            clock=lambda: _DECISION_TIME + timedelta(seconds=1),
        )
        with pytest.raises(SnapshotBuildError, match="duplicate fact_id"):
            await duplicate_builder.build(_request())

    asyncio.run(scenario())


def test_builder_rejects_ambiguous_provider_and_dataset_versions() -> None:
    provider_a = _record(
        30,
        "market.bar.daily",
        _DECISION_TIME - timedelta(minutes=10),
        provider_version="1",
    )
    provider_b = _record(
        31,
        "market.bar.minute",
        _DECISION_TIME - timedelta(minutes=5),
        provider_version="2",
    )
    dataset_a = _record(
        32,
        "news",
        _DECISION_TIME - timedelta(minutes=4),
        dataset_version="dataset-a",
    )
    dataset_b = _record(
        33,
        "news",
        _DECISION_TIME - timedelta(minutes=3),
        dataset_version="dataset-b",
    )

    async def scenario() -> None:
        provider_builder = SnapshotBuilder(
            _FactRepository((provider_a, provider_b)),
            _SnapshotRepository(),
            clock=lambda: _DECISION_TIME + timedelta(seconds=1),
        )
        with pytest.raises(SnapshotBuildError, match="provider versions"):
            await provider_builder.build(_request())

        dataset_builder = SnapshotBuilder(
            _FactRepository((dataset_a, dataset_b)),
            _SnapshotRepository(),
            clock=lambda: _DECISION_TIME + timedelta(seconds=1),
        )
        with pytest.raises(SnapshotBuildError, match="dataset versions"):
            await dataset_builder.build(_request())

    asyncio.run(scenario())


def test_builder_requires_a_valid_clock_and_propagates_persistence_failures() -> None:
    record = _record(40, "news", _DECISION_TIME - timedelta(minutes=1))

    class RejectingRepository(_SnapshotRepository):
        async def add(self, snapshot: AnalysisSnapshot) -> None:
            del snapshot
            raise RuntimeError("synthetic persistence failure")

    async def scenario() -> None:
        naive_clock = SnapshotBuilder(
            _FactRepository((record,)),
            _SnapshotRepository(),
            clock=lambda: datetime(2026, 7, 30, 14, 1),
        )
        with pytest.raises(SnapshotBuildError, match="timezone-aware"):
            await naive_clock.build(_request())

        early_clock = SnapshotBuilder(
            _FactRepository((record,)),
            _SnapshotRepository(),
            clock=lambda: _DECISION_TIME - timedelta(seconds=1),
        )
        with pytest.raises(SnapshotBuildError, match="before decision_time"):
            await early_clock.build(_request())

        rejecting_builder = SnapshotBuilder(
            _FactRepository((record,)),
            RejectingRepository(),
            clock=lambda: _DECISION_TIME + timedelta(seconds=1),
        )
        with pytest.raises(RuntimeError, match="persistence failure"):
            await rejecting_builder.build(_request())

    asyncio.run(scenario())


def test_build_request_and_policy_reject_ambiguous_configuration() -> None:
    with pytest.raises(ValidationError, match="exactly their target_id"):
        _request(instrument_ids=(UUID("40000000-0000-4000-8000-000000000299"),))
    with pytest.raises(ValidationError, match="must not be empty"):
        _request(instrument_ids=())
    with pytest.raises(ValidationError, match="must be unique"):
        _request(instrument_ids=(_INSTRUMENT_ID, _INSTRUMENT_ID))
    with pytest.raises(ValidationError, match="timezone-aware"):
        _request(decision_time=datetime(2026, 7, 30, 14, 0))

    duplicate_rule = SnapshotFactRule(
        fact_type="news",
        category=SnapshotDataCategory.NEWS,
    )
    with pytest.raises(ValidationError, match="unique fact_type"):
        SnapshotBuildPolicy(fact_rules=(duplicate_rule, duplicate_rule))
    with pytest.raises(ValidationError, match="lack fact rules"):
        SnapshotBuildPolicy(
            fact_rules=(duplicate_rule,),
            required_categories=(SnapshotDataCategory.PRICE,),
        )
    with pytest.raises(ValidationError, match="positive"):
        SnapshotFreshnessRule(
            category=SnapshotDataCategory.NEWS,
            max_age=timedelta(0),
        )
