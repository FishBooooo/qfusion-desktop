"""Alembic environment restricted to an application-supplied connection."""

from __future__ import annotations

from typing import NoReturn

from alembic import context
from sqlalchemy.engine import Connection

from qfusion.storage.models import Base

configuration = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> NoReturn:
    """Reject URL-based offline migrations for the local desktop database."""

    raise RuntimeError("QFusion migrations require a caller-owned database connection")


def run_migrations_online() -> None:
    """Run migrations on the connection injected by qfusion.storage."""

    connection = configuration.attributes.get("connection")
    if not isinstance(connection, Connection):
        raise RuntimeError("QFusion migrations require configuration.attributes['connection']")

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
