"""Repository Protocol boundary tests."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from qfusion.domain import (
    AnalysisSnapshot,
    DataSourceRecord,
    FactQuery,
    FactReadRepository,
    SnapshotRepository,
)


class StubFactRepository:
    """Minimal structural implementation used only to verify the Protocol."""

    async def list_as_of(self, query: FactQuery) -> Sequence[DataSourceRecord]:
        del query
        return ()


class StubSnapshotRepository:
    """In-memory Protocol implementation used only for contract tests."""

    def __init__(self) -> None:
        self.snapshots: dict[UUID, AnalysisSnapshot] = {}

    async def add(self, snapshot: AnalysisSnapshot) -> None:
        if snapshot.snapshot_id in self.snapshots:
            raise ValueError("snapshot_id already exists")
        self.snapshots[snapshot.snapshot_id] = snapshot

    async def get(self, snapshot_id: UUID) -> AnalysisSnapshot | None:
        return self.snapshots.get(snapshot_id)


def test_repository_protocols_are_vendor_neutral_and_runtime_checkable() -> None:
    fact_repository = StubFactRepository()
    snapshot_repository = StubSnapshotRepository()

    assert isinstance(fact_repository, FactReadRepository)
    assert isinstance(snapshot_repository, SnapshotRepository)
    assert asyncio.run(
        fact_repository.list_as_of(FactQuery(decision_time=datetime(2026, 7, 28, tzinfo=UTC)))
    ) == ()
    assert asyncio.run(
        snapshot_repository.get(UUID("30000000-0000-4000-8000-000000000001"))
    ) is None
