"""Programmatic, connection-injected Alembic migration entrypoints."""

from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Engine

_SOURCE_MIGRATIONS_DIRECTORY = Path(__file__).resolve().parents[2] / "migrations"
_BUNDLED_MIGRATIONS_DIRECTORY_NAME = "qfusion_migrations"


def _contains_migration_assets(directory: Path) -> bool:
    """Return whether a regular directory contains the required Alembic assets."""

    versions_directory = directory / "versions"
    required_files = (directory / "env.py", directory / "script.py.mako")
    if (
        directory.is_symlink()
        or not directory.is_dir()
        or versions_directory.is_symlink()
        or not versions_directory.is_dir()
        or any(path.is_symlink() or not path.is_file() for path in required_files)
    ):
        return False

    version_files = tuple(versions_directory.glob("*.py"))
    return bool(version_files) and all(
        not path.is_symlink() and path.is_file() for path in version_files
    )


def resolve_migrations_directory() -> Path:
    """Resolve source-tree or standalone migration assets without host configuration."""

    candidates = (
        Path(sys.executable).resolve().parent / _BUNDLED_MIGRATIONS_DIRECTORY_NAME,
        _SOURCE_MIGRATIONS_DIRECTORY,
    )
    for candidate in candidates:
        if _contains_migration_assets(candidate):
            return candidate.resolve()

    rendered_candidates = ", ".join(str(candidate) for candidate in candidates)
    raise RuntimeError(
        "QFusion Alembic migration assets are missing or unsafe; checked "
        f"{rendered_candidates}"
    )


def create_alembic_config() -> Config:
    """Build path-stable Alembic configuration without a database URL."""

    configuration = Config()
    configuration.set_main_option("script_location", str(resolve_migrations_directory()))
    return configuration


def verify_migration_assets() -> tuple[str, ...]:
    """Load every revision and return the single migration head."""

    script_directory = ScriptDirectory.from_config(create_alembic_config())
    heads = tuple(script_directory.get_heads())
    if len(heads) != 1:
        raise RuntimeError(
            "QFusion requires exactly one Alembic migration head; "
            f"found {len(heads)}"
        )
    return heads


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
