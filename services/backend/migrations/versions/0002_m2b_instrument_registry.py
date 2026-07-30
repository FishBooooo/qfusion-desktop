"""Create permanent instruments and Point-in-Time identifier mappings.

Revision ID: 0002_m2b_instruments
Revises: 0001_m1b_snapshots
Create Date: 2026-07-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_m2b_instruments"
down_revision: str | None = "0001_m1b_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TICKER_OVERLAP_INSERT = """
CREATE TRIGGER trg_ticker_alias_no_overlap_insert
BEFORE INSERT ON instrument_ticker_aliases
WHEN EXISTS (
    SELECT 1
    FROM instrument_ticker_aliases AS existing
    WHERE existing.market = NEW.market
      AND existing.ticker = NEW.ticker
      AND (existing.valid_to IS NULL OR NEW.valid_from < existing.valid_to)
      AND (NEW.valid_to IS NULL OR existing.valid_from < NEW.valid_to)
)
BEGIN
    SELECT RAISE(ABORT, 'ticker alias validity overlaps an existing mapping');
END
"""

_TICKER_OVERLAP_UPDATE = """
CREATE TRIGGER trg_ticker_alias_no_overlap_update
BEFORE UPDATE ON instrument_ticker_aliases
WHEN EXISTS (
    SELECT 1
    FROM instrument_ticker_aliases AS existing
    WHERE existing.alias_id != NEW.alias_id
      AND existing.market = NEW.market
      AND existing.ticker = NEW.ticker
      AND (existing.valid_to IS NULL OR NEW.valid_from < existing.valid_to)
      AND (NEW.valid_to IS NULL OR existing.valid_from < NEW.valid_to)
)
BEGIN
    SELECT RAISE(ABORT, 'ticker alias validity overlaps an existing mapping');
END
"""

_PROVIDER_IDENTIFIER_OVERLAP_INSERT = """
CREATE TRIGGER trg_provider_identifier_no_overlap_insert
BEFORE INSERT ON provider_instrument_mappings
WHEN EXISTS (
    SELECT 1
    FROM provider_instrument_mappings AS existing
    WHERE existing.provider_name = NEW.provider_name
      AND existing.market = NEW.market
      AND existing.provider_instrument_id = NEW.provider_instrument_id
      AND (existing.valid_to IS NULL OR NEW.valid_from < existing.valid_to)
      AND (NEW.valid_to IS NULL OR existing.valid_from < NEW.valid_to)
)
BEGIN
    SELECT RAISE(ABORT, 'provider identifier validity overlaps an existing mapping');
END
"""

_PROVIDER_IDENTIFIER_OVERLAP_UPDATE = """
CREATE TRIGGER trg_provider_identifier_no_overlap_update
BEFORE UPDATE ON provider_instrument_mappings
WHEN EXISTS (
    SELECT 1
    FROM provider_instrument_mappings AS existing
    WHERE existing.mapping_id != NEW.mapping_id
      AND existing.provider_name = NEW.provider_name
      AND existing.market = NEW.market
      AND existing.provider_instrument_id = NEW.provider_instrument_id
      AND (existing.valid_to IS NULL OR NEW.valid_from < existing.valid_to)
      AND (NEW.valid_to IS NULL OR existing.valid_from < NEW.valid_to)
)
BEGIN
    SELECT RAISE(ABORT, 'provider identifier validity overlaps an existing mapping');
END
"""

_PROVIDER_INSTRUMENT_OVERLAP_INSERT = """
CREATE TRIGGER trg_provider_instrument_no_overlap_insert
BEFORE INSERT ON provider_instrument_mappings
WHEN EXISTS (
    SELECT 1
    FROM provider_instrument_mappings AS existing
    WHERE existing.provider_name = NEW.provider_name
      AND existing.market = NEW.market
      AND existing.instrument_id = NEW.instrument_id
      AND (existing.valid_to IS NULL OR NEW.valid_from < existing.valid_to)
      AND (NEW.valid_to IS NULL OR existing.valid_from < NEW.valid_to)
)
BEGIN
    SELECT RAISE(ABORT, 'instrument has overlapping provider mappings');
END
"""

_PROVIDER_INSTRUMENT_OVERLAP_UPDATE = """
CREATE TRIGGER trg_provider_instrument_no_overlap_update
BEFORE UPDATE ON provider_instrument_mappings
WHEN EXISTS (
    SELECT 1
    FROM provider_instrument_mappings AS existing
    WHERE existing.mapping_id != NEW.mapping_id
      AND existing.provider_name = NEW.provider_name
      AND existing.market = NEW.market
      AND existing.instrument_id = NEW.instrument_id
      AND (existing.valid_to IS NULL OR NEW.valid_from < existing.valid_to)
      AND (NEW.valid_to IS NULL OR existing.valid_from < NEW.valid_to)
)
BEGIN
    SELECT RAISE(ABORT, 'instrument has overlapping provider mappings');
END
"""

_TICKER_REGISTRATION_INSERT = """
CREATE TRIGGER trg_ticker_alias_registration_insert
BEFORE INSERT ON instrument_ticker_aliases
WHEN EXISTS (
    SELECT 1
    FROM instruments
    WHERE instruments.instrument_id = NEW.instrument_id
      AND instruments.market = NEW.market
      AND instruments.registered_at > NEW.available_at
)
BEGIN
    SELECT RAISE(ABORT, 'ticker alias predates instrument registration');
END
"""

_TICKER_REGISTRATION_UPDATE = """
CREATE TRIGGER trg_ticker_alias_registration_update
BEFORE UPDATE ON instrument_ticker_aliases
WHEN EXISTS (
    SELECT 1
    FROM instruments
    WHERE instruments.instrument_id = NEW.instrument_id
      AND instruments.market = NEW.market
      AND instruments.registered_at > NEW.available_at
)
BEGIN
    SELECT RAISE(ABORT, 'ticker alias predates instrument registration');
END
"""

_PROVIDER_REGISTRATION_INSERT = """
CREATE TRIGGER trg_provider_mapping_registration_insert
BEFORE INSERT ON provider_instrument_mappings
WHEN EXISTS (
    SELECT 1
    FROM instruments
    WHERE instruments.instrument_id = NEW.instrument_id
      AND instruments.market = NEW.market
      AND instruments.registered_at > NEW.available_at
)
BEGIN
    SELECT RAISE(ABORT, 'provider mapping predates instrument registration');
END
"""

_PROVIDER_REGISTRATION_UPDATE = """
CREATE TRIGGER trg_provider_mapping_registration_update
BEFORE UPDATE ON provider_instrument_mappings
WHEN EXISTS (
    SELECT 1
    FROM instruments
    WHERE instruments.instrument_id = NEW.instrument_id
      AND instruments.market = NEW.market
      AND instruments.registered_at > NEW.available_at
)
BEGIN
    SELECT RAISE(ABORT, 'provider mapping predates instrument registration');
END
"""

_TRIGGER_SQL = (
    _TICKER_OVERLAP_INSERT,
    _TICKER_OVERLAP_UPDATE,
    _PROVIDER_IDENTIFIER_OVERLAP_INSERT,
    _PROVIDER_IDENTIFIER_OVERLAP_UPDATE,
    _PROVIDER_INSTRUMENT_OVERLAP_INSERT,
    _PROVIDER_INSTRUMENT_OVERLAP_UPDATE,
    _TICKER_REGISTRATION_INSERT,
    _TICKER_REGISTRATION_UPDATE,
    _PROVIDER_REGISTRATION_INSERT,
    _PROVIDER_REGISTRATION_UPDATE,
)

_DROP_TRIGGER_SQL = (
    "DROP TRIGGER IF EXISTS trg_ticker_alias_no_overlap_insert",
    "DROP TRIGGER IF EXISTS trg_ticker_alias_no_overlap_update",
    "DROP TRIGGER IF EXISTS trg_provider_identifier_no_overlap_insert",
    "DROP TRIGGER IF EXISTS trg_provider_identifier_no_overlap_update",
    "DROP TRIGGER IF EXISTS trg_provider_instrument_no_overlap_insert",
    "DROP TRIGGER IF EXISTS trg_provider_instrument_no_overlap_update",
    "DROP TRIGGER IF EXISTS trg_ticker_alias_registration_insert",
    "DROP TRIGGER IF EXISTS trg_ticker_alias_registration_update",
    "DROP TRIGGER IF EXISTS trg_provider_mapping_registration_insert",
    "DROP TRIGGER IF EXISTS trg_provider_mapping_registration_update",
)


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("market", sa.String(length=8), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column("registered_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("market IN ('US', 'HK')", name="ck_instruments_market"),
        sa.CheckConstraint(
            "asset_type IN ('stock', 'adr', 'etf', 'sector_etf')",
            name="ck_instruments_asset_type",
        ),
        sa.CheckConstraint(
            "length(display_name) >= 1 AND length(display_name) <= 256",
            name="ck_instruments_display_name_length",
        ),
        sa.PrimaryKeyConstraint("instrument_id"),
        sa.UniqueConstraint(
            "instrument_id",
            "market",
            name="uq_instruments_identity_market",
        ),
    )

    op.create_table(
        "instrument_ticker_aliases",
        sa.Column("alias_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("market", sa.String(length=8), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("valid_from", sa.DateTime(), nullable=False),
        sa.Column("valid_to", sa.DateTime(), nullable=True),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("source_record_id", sa.String(length=128), nullable=False),
        sa.Column("revision_id", sa.String(length=128), nullable=False),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from < valid_to",
            name="ck_ticker_alias_valid_range",
        ),
        sa.CheckConstraint(
            "length(ticker) >= 1 AND length(ticker) <= 32",
            name="ck_ticker_alias_ticker_length",
        ),
        sa.CheckConstraint("ticker = upper(ticker)", name="ck_ticker_alias_uppercase"),
        sa.ForeignKeyConstraint(
            ("instrument_id", "market"),
            ("instruments.instrument_id", "instruments.market"),
            ondelete="RESTRICT",
            name="fk_ticker_alias_instrument_market",
        ),
        sa.PrimaryKeyConstraint("alias_id"),
    )
    op.create_index(
        "ix_ticker_alias_lookup",
        "instrument_ticker_aliases",
        ["market", "ticker", "valid_from", "valid_to", "available_at"],
        unique=False,
    )
    op.create_index(
        "ix_ticker_alias_instrument",
        "instrument_ticker_aliases",
        ["instrument_id", "market"],
        unique=False,
    )

    op.create_table(
        "provider_instrument_mappings",
        sa.Column("mapping_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("market", sa.String(length=8), nullable=False),
        sa.Column("provider_name", sa.String(length=128), nullable=False),
        sa.Column("provider_instrument_id", sa.String(length=256), nullable=False),
        sa.Column("provider_version", sa.String(length=128), nullable=False),
        sa.Column("valid_from", sa.DateTime(), nullable=False),
        sa.Column("valid_to", sa.DateTime(), nullable=True),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("source_record_id", sa.String(length=128), nullable=False),
        sa.Column("revision_id", sa.String(length=128), nullable=False),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from < valid_to",
            name="ck_provider_mapping_valid_range",
        ),
        sa.CheckConstraint(
            "length(provider_name) >= 1 AND length(provider_name) <= 128",
            name="ck_provider_mapping_name_length",
        ),
        sa.CheckConstraint(
            "length(provider_instrument_id) >= 1 "
            "AND length(provider_instrument_id) <= 256",
            name="ck_provider_mapping_identifier_length",
        ),
        sa.ForeignKeyConstraint(
            ("instrument_id", "market"),
            ("instruments.instrument_id", "instruments.market"),
            ondelete="RESTRICT",
            name="fk_provider_mapping_instrument_market",
        ),
        sa.PrimaryKeyConstraint("mapping_id"),
    )
    op.create_index(
        "ix_provider_identifier_lookup",
        "provider_instrument_mappings",
        [
            "provider_name",
            "market",
            "provider_instrument_id",
            "valid_from",
            "valid_to",
            "available_at",
        ],
        unique=False,
    )
    op.create_index(
        "ix_provider_mapping_lookup",
        "provider_instrument_mappings",
        [
            "instrument_id",
            "provider_name",
            "market",
            "valid_from",
            "valid_to",
            "available_at",
        ],
        unique=False,
    )

    for statement in _TRIGGER_SQL:
        op.execute(statement)


def downgrade() -> None:
    for statement in reversed(_DROP_TRIGGER_SQL):
        op.execute(statement)

    op.drop_index(
        "ix_provider_mapping_lookup",
        table_name="provider_instrument_mappings",
    )
    op.drop_index(
        "ix_provider_identifier_lookup",
        table_name="provider_instrument_mappings",
    )
    op.drop_table("provider_instrument_mappings")
    op.drop_index(
        "ix_ticker_alias_instrument",
        table_name="instrument_ticker_aliases",
    )
    op.drop_index(
        "ix_ticker_alias_lookup",
        table_name="instrument_ticker_aliases",
    )
    op.drop_table("instrument_ticker_aliases")
    op.drop_table("instruments")
