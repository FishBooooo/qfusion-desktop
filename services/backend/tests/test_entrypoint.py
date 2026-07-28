"""Executable entry point wiring tests."""

from __future__ import annotations

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
        main()

    run_server.assert_called_once_with(
        app,
        host="127.0.0.1",
        port=8123,
        log_level="warning",
    )
