"""Tests for the audited standalone backend build command."""

from __future__ import annotations

from scripts import build_backend

SERVER_DIALECT_PACKAGES = (
    "sqlalchemy.dialects.mssql",
    "sqlalchemy.dialects.mysql",
    "sqlalchemy.dialects.oracle",
    "sqlalchemy.dialects.postgresql",
)


def _assert_database_scope(command: list[str]) -> None:
    """Require SQLite plus Alembic imports, excluding only the known OOM module."""

    assert (
        f"--include-module={build_backend.SQLALCHEMY_SQLITE_DRIVER_MODULE}"
        in command
    )
    assert {
        argument
        for argument in command
        if argument.startswith("--nofollow-import-to=")
    } == {
        f"--nofollow-import-to={module_name}"
        for module_name in build_backend.SQLALCHEMY_EXCLUDED_MODULES
    }
    assert build_backend.SQLALCHEMY_EXCLUDED_MODULES == (
        "sqlalchemy.dialects.oracle.dictionary",
    )
    for package_name in SERVER_DIALECT_PACKAGES:
        assert f"--nofollow-import-to={package_name}" not in command


def test_windows_standalone_build_retains_alembic_dialect_imports() -> None:
    """Windows uses the safe PE scanner without breaking Alembic imports."""

    command, dependency_scanner = build_backend._build_nuitka_command(
        "qfusion-backend.exe",
        system_name="Windows",
    )

    assert dependency_scanner == "nuitka-inline-pefile"
    assert "--experimental=force-dependencies-pefile" in command
    _assert_database_scope(command)
    assert command[-1] == str(build_backend.PACKAGE_DIRECTORY)


def test_non_windows_build_uses_the_same_selective_exclusion() -> None:
    """The dependency scanner varies by platform, not the database scope."""

    command, dependency_scanner = build_backend._build_nuitka_command(
        "qfusion-backend",
        system_name="Linux",
    )

    assert dependency_scanner == "platform-default"
    assert "--experimental=force-dependencies-pefile" not in command
    _assert_database_scope(command)
    assert command[-1] == str(build_backend.PACKAGE_DIRECTORY)
