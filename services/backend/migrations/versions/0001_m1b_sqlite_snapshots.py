"""Create immutable AnalysisSnapshot metadata tables.

Revision ID: 0001_m1b_snapshots
Revises: None
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_m1b_snapshots"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_snapshots",
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("target_type", sa.String(length=16), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("market", sa.String(length=8), nullable=False),
        sa.Column("requested_horizon", sa.String(length=16), nullable=False),
        sa.Column("decision_time", sa.DateTime(), nullable=False),
        sa.Column("market_timezone", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("price_as_of", sa.DateTime(), nullable=True),
        sa.Column("fundamental_as_of", sa.DateTime(), nullable=True),
        sa.Column("news_as_of", sa.DateTime(), nullable=True),
        sa.Column("options_as_of", sa.DateTime(), nullable=True),
        sa.Column("macro_as_of", sa.DateTime(), nullable=True),
        sa.Column("flow_as_of", sa.DateTime(), nullable=True),
        sa.Column("provider_versions", sa.JSON(), nullable=False),
        sa.Column("dataset_versions", sa.JSON(), nullable=False),
        sa.Column("missing_data", sa.JSON(), nullable=False),
        sa.Column("stale_data", sa.JSON(), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=False),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "quality_score >= 0.0 AND quality_score <= 1.0",
            name="ck_analysis_snapshots_quality_score",
        ),
        sa.CheckConstraint(
            "created_at >= decision_time",
            name="ck_analysis_snapshots_created_after_decision",
        ),
        sa.CheckConstraint(
            "price_as_of IS NULL OR price_as_of <= decision_time",
            name="ck_analysis_snapshots_price_as_of",
        ),
        sa.CheckConstraint(
            "fundamental_as_of IS NULL OR fundamental_as_of <= decision_time",
            name="ck_analysis_snapshots_fundamental_as_of",
        ),
        sa.CheckConstraint(
            "news_as_of IS NULL OR news_as_of <= decision_time",
            name="ck_analysis_snapshots_news_as_of",
        ),
        sa.CheckConstraint(
            "options_as_of IS NULL OR options_as_of <= decision_time",
            name="ck_analysis_snapshots_options_as_of",
        ),
        sa.CheckConstraint(
            "macro_as_of IS NULL OR macro_as_of <= decision_time",
            name="ck_analysis_snapshots_macro_as_of",
        ),
        sa.CheckConstraint(
            "flow_as_of IS NULL OR flow_as_of <= decision_time",
            name="ck_analysis_snapshots_flow_as_of",
        ),
        sa.CheckConstraint(
            "("
            "market = 'US' AND market_timezone = 'America/New_York'"
            ") OR ("
            "market = 'HK' AND market_timezone = 'Asia/Hong_Kong'"
            ")",
            name="ck_analysis_snapshots_market_timezone",
        ),
        sa.CheckConstraint(
            "length(content_fingerprint) = 64",
            name="ck_analysis_snapshots_fingerprint_length",
        ),
        sa.PrimaryKeyConstraint("snapshot_id"),
    )
    op.create_index(
        "ix_analysis_snapshots_target_decision",
        "analysis_snapshots",
        ["target_type", "target_id", "decision_time"],
        unique=False,
    )

    op.create_table(
        "analysis_snapshot_facts",
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("fact_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["analysis_snapshots.snapshot_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("snapshot_id", "fact_id"),
    )
    op.create_index(
        "ix_analysis_snapshot_facts_fact_id",
        "analysis_snapshot_facts",
        ["fact_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_analysis_snapshot_facts_fact_id",
        table_name="analysis_snapshot_facts",
    )
    op.drop_table("analysis_snapshot_facts")
    op.drop_index(
        "ix_analysis_snapshots_target_decision",
        table_name="analysis_snapshots",
    )
    op.drop_table("analysis_snapshots")
