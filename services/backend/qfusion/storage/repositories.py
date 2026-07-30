"""SQLite implementations of metadata repository interfaces."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from qfusion.domain import (
    AnalysisSnapshot,
    Instrument,
    InstrumentAssetType,
    InstrumentQuery,
    Market,
    ProviderIdentifierLookup,
    ProviderInstrumentMapping,
    ProviderMappingLookup,
    RequestedHorizon,
    TargetType,
    TickerAlias,
    TickerLookup,
    require_instrument_available,
    require_provider_identifier_match,
    require_provider_mapping_match,
    require_ticker_match,
)
from qfusion.storage.models import (
    AnalysisSnapshotRow,
    InstrumentRow,
    ProviderInstrumentMappingRow,
    SnapshotFactReferenceRow,
    TickerAliasRow,
)


class DuplicateSnapshotError(ValueError):
    """Raised when immutable snapshot identity would be replaced."""


class SnapshotIntegrityError(ValueError):
    """Raised when persisted snapshot metadata no longer validates."""


class DuplicateInstrumentError(ValueError):
    """Raised when a permanent instrument UUID would be replaced."""


class InstrumentIdentifierConflictError(ValueError):
    """Raised when an identifier is duplicate, overlapping, or incorrectly scoped."""


class InstrumentRegistryIntegrityError(ValueError):
    """Raised when persisted instrument metadata fails Domain or temporal guards."""


class SqlAlchemyInstrumentRegistryRepository:
    """Persist permanent instruments and resolve Point-in-Time external identifiers."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    async def add_instrument(self, instrument: Instrument) -> None:
        """Insert one permanent identity without replacement."""

        await asyncio.to_thread(self._add_instrument_sync, instrument)

    async def add_ticker_alias(self, alias: TickerAlias) -> None:
        """Insert one effective ticker alias without overlapping an existing alias."""

        await asyncio.to_thread(self._add_ticker_alias_sync, alias)

    async def add_provider_mapping(self, mapping: ProviderInstrumentMapping) -> None:
        """Insert one effective, opaque provider identifier mapping."""

        await asyncio.to_thread(self._add_provider_mapping_sync, mapping)

    async def get_instrument(self, query: InstrumentQuery) -> Instrument | None:
        """Return an instrument only when registered by decision_time."""

        return await asyncio.to_thread(self._get_instrument_sync, query)

    async def resolve_ticker(self, query: TickerLookup) -> TickerAlias | None:
        """Resolve ticker using both market-validity and knowledge time."""

        return await asyncio.to_thread(self._resolve_ticker_sync, query)

    async def resolve_provider_identifier(
        self,
        query: ProviderIdentifierLookup,
    ) -> ProviderInstrumentMapping | None:
        """Resolve an opaque provider identifier to one permanent instrument."""

        return await asyncio.to_thread(self._resolve_provider_identifier_sync, query)

    async def get_provider_mapping(
        self,
        query: ProviderMappingLookup,
    ) -> ProviderInstrumentMapping | None:
        """Return the provider identifier valid for one permanent instrument."""

        return await asyncio.to_thread(self._get_provider_mapping_sync, query)

    def _add_instrument_sync(self, instrument: Instrument) -> None:
        row = InstrumentRow(
            instrument_id=instrument.instrument_id,
            schema_version=instrument.schema_version,
            market=instrument.market.value,
            asset_type=instrument.asset_type.value,
            display_name=instrument.display_name,
            registered_at=instrument.registered_at,
        )
        try:
            with self._session_factory.begin() as session:
                session.add(row)
        except IntegrityError as error:
            raise DuplicateInstrumentError(
                f"instrument_id already exists or is invalid: {instrument.instrument_id}"
            ) from error

    def _add_ticker_alias_sync(self, alias: TickerAlias) -> None:
        row = TickerAliasRow(
            alias_id=alias.alias_id,
            schema_version=alias.schema_version,
            instrument_id=alias.instrument_id,
            market=alias.market.value,
            ticker=alias.ticker,
            valid_from=alias.valid_from,
            valid_to=alias.valid_to,
            available_at=alias.available_at,
            source=alias.source,
            source_record_id=alias.source_record_id,
            revision_id=alias.revision_id,
        )
        try:
            with self._session_factory.begin() as session:
                session.add(row)
        except IntegrityError as error:
            raise InstrumentIdentifierConflictError(
                f"ticker alias conflicts with registry state: {alias.alias_id}"
            ) from error

    def _add_provider_mapping_sync(self, mapping: ProviderInstrumentMapping) -> None:
        row = ProviderInstrumentMappingRow(
            mapping_id=mapping.mapping_id,
            schema_version=mapping.schema_version,
            instrument_id=mapping.instrument_id,
            market=mapping.market.value,
            provider_name=mapping.provider_name,
            provider_instrument_id=mapping.provider_instrument_id,
            provider_version=mapping.provider_version,
            valid_from=mapping.valid_from,
            valid_to=mapping.valid_to,
            available_at=mapping.available_at,
            source_record_id=mapping.source_record_id,
            revision_id=mapping.revision_id,
        )
        try:
            with self._session_factory.begin() as session:
                session.add(row)
        except IntegrityError as error:
            raise InstrumentIdentifierConflictError(
                f"provider mapping conflicts with registry state: {mapping.mapping_id}"
            ) from error

    def _get_instrument_sync(self, query: InstrumentQuery) -> Instrument | None:
        with self._session_factory() as session:
            statement = select(InstrumentRow).where(
                InstrumentRow.instrument_id == query.instrument_id,
                InstrumentRow.registered_at <= query.decision_time,
            )
            row = session.scalar(statement)
            if row is None:
                return None
            instrument = self._restore_instrument(row)
            try:
                return require_instrument_available(query, instrument)
            except ValueError as error:
                raise InstrumentRegistryIntegrityError(
                    f"instrument failed Point-in-Time guard: {query.instrument_id}"
                ) from error

    def _resolve_ticker_sync(self, query: TickerLookup) -> TickerAlias | None:
        with self._session_factory() as session:
            statement = (
                select(TickerAliasRow)
                .where(
                    TickerAliasRow.market == query.market.value,
                    TickerAliasRow.ticker == query.ticker,
                    TickerAliasRow.valid_from <= query.effective_at,
                    or_(
                        TickerAliasRow.valid_to.is_(None),
                        TickerAliasRow.valid_to > query.effective_at,
                    ),
                    TickerAliasRow.available_at <= query.decision_time,
                )
                .order_by(
                    TickerAliasRow.valid_from.desc(),
                    TickerAliasRow.available_at.desc(),
                    TickerAliasRow.alias_id,
                )
                .limit(2)
            )
            rows = tuple(session.scalars(statement).all())
            if not rows:
                return None
            if len(rows) != 1:
                raise InstrumentRegistryIntegrityError(
                    "ticker lookup returned overlapping persisted mappings"
                )
            alias = self._restore_ticker_alias(rows[0])
            self._require_registered_identity(
                session,
                alias.instrument_id,
                alias.market,
                alias.available_at,
            )
            try:
                return require_ticker_match(query, alias)
            except ValueError as error:
                raise InstrumentRegistryIntegrityError(
                    f"ticker alias failed Point-in-Time guard: {alias.alias_id}"
                ) from error

    def _resolve_provider_identifier_sync(
        self,
        query: ProviderIdentifierLookup,
    ) -> ProviderInstrumentMapping | None:
        with self._session_factory() as session:
            statement = (
                select(ProviderInstrumentMappingRow)
                .where(
                    ProviderInstrumentMappingRow.provider_name == query.provider_name,
                    ProviderInstrumentMappingRow.market == query.market.value,
                    ProviderInstrumentMappingRow.provider_instrument_id
                    == query.provider_instrument_id,
                    ProviderInstrumentMappingRow.valid_from <= query.effective_at,
                    or_(
                        ProviderInstrumentMappingRow.valid_to.is_(None),
                        ProviderInstrumentMappingRow.valid_to > query.effective_at,
                    ),
                    ProviderInstrumentMappingRow.available_at <= query.decision_time,
                )
                .order_by(
                    ProviderInstrumentMappingRow.valid_from.desc(),
                    ProviderInstrumentMappingRow.available_at.desc(),
                    ProviderInstrumentMappingRow.mapping_id,
                )
                .limit(2)
            )
            rows = tuple(session.scalars(statement).all())
            if not rows:
                return None
            if len(rows) != 1:
                raise InstrumentRegistryIntegrityError(
                    "provider identifier lookup returned overlapping persisted mappings"
                )
            mapping = self._restore_provider_mapping(rows[0])
            self._require_registered_identity(
                session,
                mapping.instrument_id,
                mapping.market,
                mapping.available_at,
            )
            try:
                return require_provider_identifier_match(query, mapping)
            except ValueError as error:
                raise InstrumentRegistryIntegrityError(
                    f"provider mapping failed Point-in-Time guard: {mapping.mapping_id}"
                ) from error

    def _get_provider_mapping_sync(
        self,
        query: ProviderMappingLookup,
    ) -> ProviderInstrumentMapping | None:
        with self._session_factory() as session:
            statement = (
                select(ProviderInstrumentMappingRow)
                .where(
                    ProviderInstrumentMappingRow.instrument_id == query.instrument_id,
                    ProviderInstrumentMappingRow.provider_name == query.provider_name,
                    ProviderInstrumentMappingRow.market == query.market.value,
                    ProviderInstrumentMappingRow.valid_from <= query.effective_at,
                    or_(
                        ProviderInstrumentMappingRow.valid_to.is_(None),
                        ProviderInstrumentMappingRow.valid_to > query.effective_at,
                    ),
                    ProviderInstrumentMappingRow.available_at <= query.decision_time,
                )
                .order_by(
                    ProviderInstrumentMappingRow.valid_from.desc(),
                    ProviderInstrumentMappingRow.available_at.desc(),
                    ProviderInstrumentMappingRow.mapping_id,
                )
                .limit(2)
            )
            rows = tuple(session.scalars(statement).all())
            if not rows:
                return None
            if len(rows) != 1:
                raise InstrumentRegistryIntegrityError(
                    "instrument lookup returned overlapping provider mappings"
                )
            mapping = self._restore_provider_mapping(rows[0])
            self._require_registered_identity(
                session,
                mapping.instrument_id,
                mapping.market,
                mapping.available_at,
            )
            try:
                return require_provider_mapping_match(query, mapping)
            except ValueError as error:
                raise InstrumentRegistryIntegrityError(
                    f"provider mapping failed instrument guard: {mapping.mapping_id}"
                ) from error

    @classmethod
    def _require_registered_identity(
        cls,
        session: Session,
        instrument_id: UUID,
        market: Market,
        mapping_available_at: datetime,
    ) -> Instrument:
        row = session.get(InstrumentRow, instrument_id)
        if row is None:
            raise InstrumentRegistryIntegrityError(
                f"identifier references a missing instrument: {instrument_id}"
            )
        instrument = cls._restore_instrument(row)
        if instrument.market is not market:
            raise InstrumentRegistryIntegrityError(
                f"identifier market differs from instrument: {instrument_id}"
            )
        if instrument.registered_at > mapping_available_at:
            raise InstrumentRegistryIntegrityError(
                f"identifier predates instrument registration: {instrument_id}"
            )
        return instrument

    @staticmethod
    def _restore_instrument(row: InstrumentRow) -> Instrument:
        try:
            return Instrument(
                schema_version=row.schema_version,
                instrument_id=row.instrument_id,
                market=Market(row.market),
                asset_type=InstrumentAssetType(row.asset_type),
                display_name=row.display_name,
                registered_at=row.registered_at,
            )
        except (TypeError, ValueError) as error:
            raise InstrumentRegistryIntegrityError(
                f"invalid persisted instrument: {row.instrument_id}"
            ) from error

    @staticmethod
    def _restore_ticker_alias(row: TickerAliasRow) -> TickerAlias:
        try:
            return TickerAlias(
                schema_version=row.schema_version,
                alias_id=row.alias_id,
                instrument_id=row.instrument_id,
                market=Market(row.market),
                ticker=row.ticker,
                valid_from=row.valid_from,
                valid_to=row.valid_to,
                available_at=row.available_at,
                source=row.source,
                source_record_id=row.source_record_id,
                revision_id=row.revision_id,
            )
        except (TypeError, ValueError) as error:
            raise InstrumentRegistryIntegrityError(
                f"invalid persisted ticker alias: {row.alias_id}"
            ) from error

    @staticmethod
    def _restore_provider_mapping(
        row: ProviderInstrumentMappingRow,
    ) -> ProviderInstrumentMapping:
        try:
            return ProviderInstrumentMapping(
                schema_version=row.schema_version,
                mapping_id=row.mapping_id,
                instrument_id=row.instrument_id,
                market=Market(row.market),
                provider_name=row.provider_name,
                provider_instrument_id=row.provider_instrument_id,
                provider_version=row.provider_version,
                valid_from=row.valid_from,
                valid_to=row.valid_to,
                available_at=row.available_at,
                source_record_id=row.source_record_id,
                revision_id=row.revision_id,
            )
        except (TypeError, ValueError) as error:
            raise InstrumentRegistryIntegrityError(
                f"invalid persisted provider mapping: {row.mapping_id}"
            ) from error


class SqlAlchemySnapshotRepository:
    """Persist immutable AnalysisSnapshot metadata in SQLite."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    async def add(self, snapshot: AnalysisSnapshot) -> None:
        """Insert one snapshot without replacing an existing identifier."""

        await asyncio.to_thread(self._add_sync, snapshot)

    async def get(self, snapshot_id: UUID) -> AnalysisSnapshot | None:
        """Return one validated snapshot without exposing storage rows."""

        return await asyncio.to_thread(self._get_sync, snapshot_id)

    def _add_sync(self, snapshot: AnalysisSnapshot) -> None:
        row = AnalysisSnapshotRow(
            snapshot_id=snapshot.snapshot_id,
            schema_version=snapshot.schema_version,
            target_type=snapshot.target_type.value,
            target_id=snapshot.target_id,
            market=snapshot.market.value,
            requested_horizon=snapshot.requested_horizon.value,
            decision_time=snapshot.decision_time,
            market_timezone=snapshot.market_timezone,
            created_at=snapshot.created_at,
            price_as_of=snapshot.price_as_of,
            fundamental_as_of=snapshot.fundamental_as_of,
            news_as_of=snapshot.news_as_of,
            options_as_of=snapshot.options_as_of,
            macro_as_of=snapshot.macro_as_of,
            flow_as_of=snapshot.flow_as_of,
            provider_versions=dict(snapshot.provider_versions),
            dataset_versions=dict(snapshot.dataset_versions),
            missing_data=list(snapshot.missing_data),
            stale_data=list(snapshot.stale_data),
            quality_score=snapshot.quality_score,
            content_fingerprint=snapshot.content_fingerprint(),
        )
        references = [
            SnapshotFactReferenceRow(
                snapshot_id=snapshot.snapshot_id,
                fact_id=fact_id,
            )
            for fact_id in snapshot.fact_ids
        ]

        try:
            with self._session_factory.begin() as session:
                session.add(row)
                session.add_all(references)
        except IntegrityError as error:
            raise DuplicateSnapshotError(
                f"snapshot_id already exists: {snapshot.snapshot_id}"
            ) from error

    def _get_sync(self, snapshot_id: UUID) -> AnalysisSnapshot | None:
        with self._session_factory() as session:
            row = session.get(AnalysisSnapshotRow, snapshot_id)
            if row is None:
                return None

            statement = (
                select(SnapshotFactReferenceRow.fact_id)
                .where(SnapshotFactReferenceRow.snapshot_id == snapshot_id)
                .order_by(SnapshotFactReferenceRow.fact_id)
            )
            fact_ids = tuple(session.scalars(statement).all())

            snapshot = self._restore_snapshot(row, fact_ids)
            if snapshot.content_fingerprint() != row.content_fingerprint:
                raise SnapshotIntegrityError(
                    f"snapshot fingerprint mismatch: {snapshot.snapshot_id}"
                )
            return snapshot

    @staticmethod
    def _restore_snapshot(
        row: AnalysisSnapshotRow,
        fact_ids: Sequence[UUID],
    ) -> AnalysisSnapshot:
        try:
            return AnalysisSnapshot(
                schema_version=row.schema_version,
                snapshot_id=row.snapshot_id,
                target_type=TargetType(row.target_type),
                target_id=row.target_id,
                market=Market(row.market),
                requested_horizon=RequestedHorizon(row.requested_horizon),
                decision_time=row.decision_time,
                market_timezone=row.market_timezone,
                created_at=row.created_at,
                price_as_of=row.price_as_of,
                fundamental_as_of=row.fundamental_as_of,
                news_as_of=row.news_as_of,
                options_as_of=row.options_as_of,
                macro_as_of=row.macro_as_of,
                flow_as_of=row.flow_as_of,
                provider_versions=dict(row.provider_versions),
                dataset_versions=dict(row.dataset_versions),
                fact_ids=tuple(fact_ids),
                missing_data=tuple(row.missing_data),
                stale_data=tuple(row.stale_data),
                quality_score=row.quality_score,
            )
        except (TypeError, ValueError) as error:
            raise SnapshotIntegrityError(
                f"invalid persisted snapshot: {row.snapshot_id}"
            ) from error
