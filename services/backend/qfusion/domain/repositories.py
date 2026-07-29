"""Repository interfaces consumed by the domain and application layers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable
from uuid import UUID

from qfusion.domain.contracts import AnalysisSnapshot, DataSourceRecord, FactQuery


@runtime_checkable
class FactReadRepository(Protocol):
    """Read financial facts through an explicit Point-in-Time query."""

    async def list_as_of(self, query: FactQuery) -> Sequence[DataSourceRecord]:
        """Return only records whose available_at does not exceed decision_time."""
        ...


@runtime_checkable
class SnapshotRepository(Protocol):
    """Persist and retrieve immutable analysis snapshots."""

    async def add(self, snapshot: AnalysisSnapshot) -> None:
        """Persist a new snapshot without replacing an existing identifier."""
        ...

    async def get(self, snapshot_id: UUID) -> AnalysisSnapshot | None:
        """Return one snapshot by its permanent identifier."""
        ...
