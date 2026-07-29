"""Tests for the audited standalone backend build command."""

from __future__ import annotations

from scripts import build_backend


def test_windows_standalone_build_includes_only_sqlite_dialect() -> None:
    """Windows builds retain SQLite while excluding unused server dialects."""

    command, dependency_scanner = build_backend._build_nuitka_command(
        "qfusion-backend.exe",
        system_name="Windows",
    )

    assert dependency_scanner == "nuitka-inline-pefile"
    assert "--experimental=force-dependencies-pefile" in command
    assert (
        f"--include-module={build_backend.SQLALCHEMY_SQLITE_DRIVER_MODULE}"
        in command
    )
    assert {
        argument
        for argument in command
        if argument.startswith("--nofollow-import-to=")
    } == {
        f"--nofollow-import-to={package_name}"
        for package_name in build_backend.SQLALCHEMY_UNUSED_DIALECT_PACKAGES
    }
    assert command[-1] == str(build_backend.PACKAGE_DIRECTORY)


def test_non_windows_build_keeps_the_same_sqlite_scope() -> None:
    """The dependency scanner varies by platform, not the database scope."""

    command, dependency_scanner = build_backend._build_nuitka_command(
        "qfusion-backend",
        system_name="Linux",
    )

    assert dependency_scanner == "platform-default"
    assert "--experimental=force-dependencies-pefile" not in command
    assert (
        f"--include-module={build_backend.SQLALCHEMY_SQLITE_DRIVER_MODULE}"
        in command
    )
    for package_name in build_backend.SQLALCHEMY_UNUSED_DIALECT_PACKAGES:
        assert f"--nofollow-import-to={package_name}" in command
