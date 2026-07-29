"""SQLAlchemy mappings for SQLite-owned QFusion metadata."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from qfusion.storage.types import UTCDateTime


class Base(DeclarativeBase):
    """Declarative metadata root used by migrations and drift tests."""


class AnalysisSnapshotRow(Base):
    """Physical metadata for one immutable AnalysisSnapshot."""

    __tablename__ = "analysis_snapshots"
    __table_args__ = (
        CheckConstraint(
            "quality_score >= 0.0 AND quality_score <= 1.0",
            name="ck_analysis_snapshots_quality_score",
        ),
        CheckConstraint(
            "created_at >= decision_time",
            name="ck_analysis_snapshots_created_after_decision",
        ),
        CheckConstraint(
            "price_as_of IS NULL OR price_as_of <= decision_time",
            name="ck_analysis_snapshots_price_as_of",
        ),
        CheckConstraint(
            "fundamental_as_of IS NULL OR fundamental_as_of <= decision_time",
            name="ck_analysis_snapshots_fundamental_as_of",
        ),
        CheckConstraint(
            "news_as_of IS NULL OR news_as_of <= decision_time",
            name="ck_analysis_snapshots_news_as_of",
        ),
        CheckConstraint(
            "options_as_of IS NULL OR options_as_of <= decision_time",
            name="ck_analysis_snapshots_options_as_of",
        ),
        CheckConstraint(
            "macro_as_of IS NULL OR macro_as_of <= decision_time",
            name="ck_analysis_snapshots_macro_as_of",
        ),
        CheckConstraint(
            "flow_as_of IS NULL OR flow_as_of <= decision_time",
            name="ck_analysis_snapshots_flow_as_of",
        ),
        CheckConstraint(
            "("
            "market = 'US' AND market_timezone = 'America/New_York'"
            ") OR ("
            "market = 'HK' AND market_timezone = 'Asia/Hong_Kong'"
            ")",
            name="ck_analysis_snapshots_market_timezone",
        ),
        CheckConstraint(
            "length(content_fingerprint) = 64",
            name="ck_analysis_snapshots_fingerprint_length",
        ),
        Index(
            "ix_analysis_snapshots_target_decision",
            "target_type",
            "target_id",
            "decision_time",
        ),
    )

    snapshot_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    target_type: Mapped[str] = mapped_column(String(16), nullable=False)
    target_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False)
    requested_horizon: Mapped[str] = mapped_column(String(16), nullable=False)
    decision_time: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    market_timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    price_as_of: Mapped[datetime | None] = mapped_column(UTCDateTime())
    fundamental_as_of: Mapped[datetime | None] = mapped_column(UTCDateTime())
    news_as_of: Mapped[datetime | None] = mapped_column(UTCDateTime())
    options_as_of: Mapped[datetime | None] = mapped_column(UTCDateTime())
    macro_as_of: Mapped[datetime | None] = mapped_column(UTCDateTime())
    flow_as_of: Mapped[datetime | None] = mapped_column(UTCDateTime())

    provider_versions: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    dataset_versions: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    missing_data: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    stale_data: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    quality_score: Mapped[float] = mapped_column(nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)


class SnapshotFactReferenceRow(Base):
    """Cross-store reference from SQLite snapshot metadata to warehouse facts."""

    __tablename__ = "analysis_snapshot_facts"
    __table_args__ = (
        Index("ix_analysis_snapshot_facts_fact_id", "fact_id"),
    )

    snapshot_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("analysis_snapshots.snapshot_id", ondelete="CASCADE"),
        primary_key=True,
    )
    fact_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
