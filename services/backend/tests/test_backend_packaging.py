"""Standalone backend packaging regression tests."""

from __future__ import annotations

from scripts import build_backend


def test_nuitka_command_bundles_project_timezone_data() -> None:
    command, dependency_scanner = build_backend._build_nuitka_command(
        "qfusion-backend.exe",
        system_name="Windows",
    )

    assert dependency_scanner == "nuitka-inline-pefile"
    assert "--include-package=tzdata" in command
    assert "--include-package-data=tzdata" in command
    assert command.index("--include-package=tzdata") < command.index(
        str(build_backend.PACKAGE_DIRECTORY)
    )
    assert tuple(path.as_posix() for path in build_backend.REQUIRED_TIMEZONE_ASSETS) == (
        "tzdata/zoneinfo/America/New_York",
        "tzdata/zoneinfo/Asia/Hong_Kong",
    )
