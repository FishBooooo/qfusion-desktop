"""Build the Python backend as a standalone executable with Nuitka."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIRECTORY = REPOSITORY_ROOT / "services" / "backend" / "qfusion"
OUTPUT_DIRECTORY = REPOSITORY_ROOT / "dist" / "backend"


def main() -> None:
    """Invoke Nuitka without deleting previous user or research data."""
    executable_name = "qfusion-backend.exe" if platform.system() == "Windows" else "qfusion-backend"
    command = [
        sys.executable,
        "-m",
        "nuitka",
        "--mode=standalone",
        f"--output-dir={OUTPUT_DIRECTORY}",
        f"--output-filename={executable_name}",
        "--python-flag=-m",
        str(PACKAGE_DIRECTORY),
    ]
    # Every argument is a repository-owned constant; no user input reaches the process call.
    subprocess.run(command, cwd=REPOSITORY_ROOT, check=True)  # noqa: S603


if __name__ == "__main__":
    main()
