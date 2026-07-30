"""SQLAlchemy mappings for SQLite-owned QFusion metadata."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from qfusion.storage.types import UTCDateTime


class Base(DeclarativeBase):
    """Declarative metadata root used by migrations and drift tests."""


class InstrumentRow(Base):
    """Permanent internal instrument identity."""

    __tablename__ = "instruments"
    __table_args__ = (
        CheckConstraint("market IN ('US', 'HK')", name="ck_instruments_market"),
        CheckConstraint(
            "asset_type IN ('stock', 'adr', 'etf', 'sector_etf')",
            name="ck_instruments_asset_type",
        ),
        CheckConstraint(
            "length(display_name) >= 1 AND length(display_name) <= 256",
            name="ck_instruments_display_name_length",
        ),
        UniqueConstraint(
            "instrument_id",
            "market",
            name="uq_instruments_identity_market",
        ),
    )

    instrument_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class TickerAliasRow(Base):
    """Point-in-Time ticker alias for one permanent instrument."""

    __tablename__ = "instrument_ticker_aliases"
    __table_args__ = (
        ForeignKeyConstraint(
            ("instrument_id", "market"),
            ("instruments.instrument_id", "instruments.market"),
            ondelete="RESTRICT",
            name="fk_ticker_alias_instrument_market",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_from < valid_to",
            name="ck_ticker_alias_valid_range",
        ),
        CheckConstraint(
            "length(ticker) >= 1 AND length(ticker) <= 32",
            name="ck_ticker_alias_ticker_length",
        ),
        CheckConstraint("ticker = upper(ticker)", name="ck_ticker_alias_uppercase"),
        Index(
            "ix_ticker_alias_lookup",
            "market",
            "ticker",
            "valid_from",
            "valid_to",
            "available_at",
        ),
        Index("ix_ticker_alias_instrument", "instrument_id", "market"),
    )

    alias_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    instrument_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(UTCDateTime())
    available_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(128), nullable=False)
    revision_id: Mapped[str] = mapped_column(String(128), nullable=False)


class ProviderInstrumentMappingRow(Base):
    """Point-in-Time opaque provider identifier mapping."""

    __tablename__ = "provider_instrument_mappings"
    __table_args__ = (
        ForeignKeyConstraint(
            ("instrument_id", "market"),
            ("instruments.instrument_id", "instruments.market"),
            ondelete="RESTRICT",
            name="fk_provider_mapping_instrument_market",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_from < valid_to",
            name="ck_provider_mapping_valid_range",
        ),
        CheckConstraint(
            "length(provider_name) >= 1 AND length(provider_name) <= 128",
            name="ck_provider_mapping_name_length",
        ),
        CheckConstraint(
            "length(provider_instrument_id) >= 1 "
            "AND length(provider_instrument_id) <= 256",
            name="ck_provider_mapping_identifier_length",
        ),
        Index(
            "ix_provider_identifier_lookup",
            "provider_name",
            "market",
            "provider_instrument_id",
            "valid_from",
            "valid_to",
            "available_at",
        ),
        Index(
            "ix_provider_mapping_lookup",
            "instrument_id",
            "provider_name",
            "market",
            "valid_from",
            "valid_to",
            "available_at",
        ),
    )

    mapping_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    instrument_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_instrument_id: Mapped[str] = mapped_column(String(256), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(128), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(UTCDateTime())
    available_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(128), nullable=False)
    revision_id: Mapped[str] = mapped_column(String(128), nullable=False)


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
