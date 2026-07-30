"""Executable entry point wiring tests."""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from qfusion.config.settings import Settings


def test_entrypoint_passes_validated_local_settings_to_uvicorn() -> None:
    from qfusion.__main__ import app, main

    settings = Settings(
        _env_file=None,
        environment="test",
        port=8123,
        log_level="warning",
    )

    with (
        patch("qfusion.__main__.get_settings", return_value=settings),
        patch("qfusion.__main__.uvicorn.run") as run_server,
    ):
        main([])

    run_server.assert_called_once_with(
        app,
        host="127.0.0.1",
        port=8123,
        log_level="warning",
    )


def test_entrypoint_can_verify_packaged_migrations_without_starting_server() -> None:
    from qfusion.__main__ import main

    output = StringIO()
    with (
        patch(
            "qfusion.__main__.verify_migration_assets",
            return_value=("0001_m1b_snapshots",),
        ) as verify_assets,
        patch("qfusion.__main__.sys.stdout", output),
        patch("qfusion.__main__.uvicorn.run") as run_server,
    ):
        main(["--verify-migration-assets"])

    verify_assets.assert_called_once_with()
    run_server.assert_not_called()
    assert (
        output.getvalue()
        == "QFUSION_MIGRATION_ASSETS_OK heads=0001_m1b_snapshots\n"
    )


def test_timezone_verifier_loads_project_data_and_restores_tzpath() -> None:
    import zoneinfo

    from qfusion.__main__ import _verify_timezone_data

    original_tzpath = zoneinfo.TZPATH

    assert _verify_timezone_data() == (
        "America/New_York",
        "Asia/Hong_Kong",
    )
    assert original_tzpath == zoneinfo.TZPATH


def test_entrypoint_can_verify_packaged_timezone_data_without_server() -> None:
    from qfusion.__main__ import main

    output = StringIO()
    with (
        patch(
            "qfusion.__main__._verify_timezone_data",
            return_value=("America/New_York", "Asia/Hong_Kong"),
        ) as verify_timezone_data,
        patch("qfusion.__main__.sys.stdout", output),
        patch("qfusion.__main__.uvicorn.run") as run_server,
    ):
        main(["--verify-timezone-data"])

    verify_timezone_data.assert_called_once_with()
    run_server.assert_not_called()
    assert (
        output.getvalue()
        == "QFUSION_TIMEZONE_DATA_OK zones=America/New_York,Asia/Hong_Kong\n"
    )
