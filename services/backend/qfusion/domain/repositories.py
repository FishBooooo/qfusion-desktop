"""Repository interfaces consumed by the domain and application layers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable
from uuid import UUID

from qfusion.domain.contracts import AnalysisSnapshot, DataSourceRecord, FactQuery
from qfusion.domain.instruments import (
    Instrument,
    InstrumentQuery,
    ProviderIdentifierLookup,
    ProviderInstrumentMapping,
    ProviderMappingLookup,
    TickerAlias,
    TickerLookup,
)


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


@runtime_checkable
class InstrumentRegistryRepository(Protocol):
    """Persist permanent identities and resolve external identifiers as of a decision."""

    async def add_instrument(self, instrument: Instrument) -> None:
        """Insert one permanent identity without replacement."""
        ...

    async def add_ticker_alias(self, alias: TickerAlias) -> None:
        """Insert one non-overlapping, effective ticker alias."""
        ...

    async def add_provider_mapping(self, mapping: ProviderInstrumentMapping) -> None:
        """Insert one non-overlapping opaque provider mapping."""
        ...

    async def get_instrument(self, query: InstrumentQuery) -> Instrument | None:
        """Return an identity only if it was registered by decision_time."""
        ...

    async def resolve_ticker(self, query: TickerLookup) -> TickerAlias | None:
        """Resolve ticker by market, validity time, and knowledge time."""
        ...

    async def resolve_provider_identifier(
        self,
        query: ProviderIdentifierLookup,
    ) -> ProviderInstrumentMapping | None:
        """Resolve one provider identifier to its permanent instrument."""
        ...

    async def get_provider_mapping(
        self,
        query: ProviderMappingLookup,
    ) -> ProviderInstrumentMapping | None:
        """Return the provider ID valid for one permanent instrument."""
        ...
