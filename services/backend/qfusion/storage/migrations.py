"""Programmatic, connection-injected Alembic migration entrypoints."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy.engine import Engine

_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
_ALEMBIC_INI = _REPOSITORY_ROOT / "alembic.ini"
_MIGRATIONS_DIRECTORY = _REPOSITORY_ROOT / "services" / "backend" / "migrations"


def create_alembic_config() -> Config:
    """Build path-stable Alembic configuration without a database URL."""

    configuration = Config(str(_ALEMBIC_INI))
    configuration.set_main_option("script_location", str(_MIGRATIONS_DIRECTORY))
    return configuration


def upgrade_database(engine: Engine) -> None:
    """Apply every pending migration using the caller-owned engine."""

    configuration = create_alembic_config()
    with engine.begin() as connection:
        configuration.attributes["connection"] = connection
        command.upgrade(configuration, "head")


def current_database_revision(engine: Engine) -> str | None:
    """Return the current Alembic revision for a database."""

    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        return context.get_current_revision()
