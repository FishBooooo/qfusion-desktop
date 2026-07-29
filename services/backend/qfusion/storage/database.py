"""SQLite engine and session construction for Local Lite metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import URL, Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

SessionFactory = sessionmaker[Session]


def _enable_sqlite_foreign_keys(
    dbapi_connection: Any,
    connection_record: Any,
) -> None:
    """Enable referential checks before a SQLite connection is used."""

    del connection_record
    previous_autocommit = getattr(dbapi_connection, "autocommit", None)
    if previous_autocommit is not None:
        dbapi_connection.autocommit = True

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()
        if previous_autocommit is not None:
            dbapi_connection.autocommit = previous_autocommit


def create_sqlite_engine(database_path: Path) -> Engine:
    """Create a file-backed SQLite engine without creating parent directories."""

    if not database_path.is_absolute():
        raise ValueError("database_path must be absolute")
    if not database_path.parent.is_dir():
        raise FileNotFoundError(f"database parent does not exist: {database_path.parent}")
    if database_path.exists() and not database_path.is_file():
        raise ValueError("database_path must identify a file")

    url = URL.create("sqlite+pysqlite", database=str(database_path))
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def create_session_factory(engine: Engine) -> SessionFactory:
    """Create short-lived sessions suitable for thread-offloaded repository calls."""

    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
