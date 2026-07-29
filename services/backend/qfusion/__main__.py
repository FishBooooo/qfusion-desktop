"""Executable entry point for the local QFusion backend."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

import uvicorn

from qfusion.config.settings import get_settings
from qfusion.main import app
from qfusion.storage.migrations import verify_migration_assets


def _parse_arguments(arguments: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="qfusion-backend")
    parser.add_argument(
        "--verify-migration-assets",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> None:
    """Verify packaged assets or run the local backend server."""

    parsed_arguments = _parse_arguments(arguments)
    if parsed_arguments.verify_migration_assets:
        heads = verify_migration_assets()
        sys.stdout.write(
            f"QFUSION_MIGRATION_ASSETS_OK heads={','.join(heads)}\n"
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
