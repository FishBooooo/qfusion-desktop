"""Executable entry point for the local QFusion backend."""

from __future__ import annotations

import uvicorn

from qfusion.config.settings import get_settings
from qfusion.main import app


def main() -> None:
    """Run the M0 development server on the configured localhost port."""
    settings = get_settings()
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    main()
