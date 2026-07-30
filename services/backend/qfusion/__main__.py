"""Executable entry point for the local QFusion backend."""

from __future__ import annotations

import argparse
import sys
import zoneinfo
from collections.abc import Sequence

import uvicorn

from qfusion.config.settings import get_settings
from qfusion.domain import MARKET_TIMEZONES
from qfusion.main import app
from qfusion.storage.migrations import verify_migration_assets


def _parse_arguments(arguments: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="qfusion-backend")
    verification_group = parser.add_mutually_exclusive_group()
    verification_group.add_argument(
        "--verify-migration-assets",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    verification_group.add_argument(
        "--verify-timezone-data",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(arguments)


def _verify_timezone_data() -> tuple[str, ...]:
    """Load every market zone after removing all system TZPATH entries."""

    original_tzpath = zoneinfo.TZPATH
    required_keys = tuple(dict.fromkeys(MARKET_TIMEZONES.values()))
    zoneinfo.ZoneInfo.clear_cache()
    zoneinfo.reset_tzpath(())
    try:
        resolved_keys = tuple(zoneinfo.ZoneInfo(key).key for key in required_keys)
        if resolved_keys != required_keys:
            raise RuntimeError("QFusion market timezone keys did not resolve exactly.")
        return resolved_keys
    finally:
        zoneinfo.ZoneInfo.clear_cache()
        zoneinfo.reset_tzpath(original_tzpath)


def main(arguments: Sequence[str] | None = None) -> None:
    """Verify packaged assets or run the local backend server."""

    parsed_arguments = _parse_arguments(arguments)
    if parsed_arguments.verify_migration_assets:
        heads = verify_migration_assets()
        sys.stdout.write(
            f"QFUSION_MIGRATION_ASSETS_OK heads={','.join(heads)}\n"
        )
        return
    if parsed_arguments.verify_timezone_data:
        timezone_keys = _verify_timezone_data()
        sys.stdout.write(
            f"QFUSION_TIMEZONE_DATA_OK zones={','.join(timezone_keys)}\n"
        )
        return

    settings = get_settings()
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    main()
