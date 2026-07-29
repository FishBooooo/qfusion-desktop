"""SQLite implementations of metadata repository interfaces."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from qfusion.domain import (
    AnalysisSnapshot,
    Market,
    RequestedHorizon,
    TargetType,
)
from qfusion.storage.models import AnalysisSnapshotRow, SnapshotFactReferenceRow


class DuplicateSnapshotError(ValueError):
    """Raised when immutable snapshot identity would be replaced."""


class SnapshotIntegrityError(ValueError):
    """Raised when persisted snapshot metadata no longer validates."""


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
