"""Standalone backend packaging regression tests."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from scripts import build_backend, smoke_backend_standalone


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


def test_standalone_timezone_probe_forces_packaged_fallback(tmp_path: Path) -> None:
    executable = tmp_path / "qfusion-backend.exe"
    arguments = [str(executable), "--verify-timezone-data"]
    expected_stdout = (
        b"QFUSION_TIMEZONE_DATA_OK "
        b"zones=America/New_York,Asia/Hong_Kong\r\n"
    )
    completed = subprocess.CompletedProcess(
        args=arguments,
        returncode=0,
        stdout=expected_stdout,
        stderr=b"",
    )
    environment = {"SYSTEMROOT": r"C:\Windows"}

    with patch(
        "scripts.smoke_backend_standalone.subprocess.run",
        return_value=completed,
    ) as run_command:
        timezone_keys = smoke_backend_standalone._verify_timezone_runtime(
            executable,
            environment,
        )

    assert timezone_keys == ("America/New_York", "Asia/Hong_Kong")
    run_command.assert_called_once_with(
        arguments,
        cwd=executable.parent,
        env={
            "SYSTEMROOT": r"C:\Windows",
            "PYTHONTZPATH": "",
        },
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=30.0,
        check=False,
    )
