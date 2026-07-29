"""Build the Python backend as a standalone executable with Nuitka."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIRECTORY = REPOSITORY_ROOT / "services" / "backend" / "qfusion"
OUTPUT_DIRECTORY = REPOSITORY_ROOT / "dist" / "backend"
BUILD_MANIFEST = OUTPUT_DIRECTORY / "build-manifest.json"
NUITKA_CACHE_DIRECTORY = REPOSITORY_ROOT / ".cache" / "nuitka"


def _sha256(filename: Path) -> str:
    """Return a streaming SHA-256 digest for a generated artifact."""
    digest = hashlib.sha256()
    with filename.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _find_standalone_executable(executable_name: str) -> Path:
    """Find the single executable emitted into a Nuitka standalone directory."""
    matches = sorted(
        candidate.resolve()
        for standalone_directory in OUTPUT_DIRECTORY.glob("*.dist")
        if standalone_directory.is_dir()
        for candidate in (standalone_directory / executable_name,)
        if candidate.is_file()
    )
    if len(matches) != 1:
        rendered_matches = ", ".join(str(match) for match in matches) or "none"
        raise RuntimeError(
            "Expected exactly one Nuitka standalone executable, "
            f"found {len(matches)}: {rendered_matches}"
        )

    executable = matches[0]
    if not executable.is_relative_to(OUTPUT_DIRECTORY.resolve()):
        raise RuntimeError("Nuitka emitted an executable outside the repository build directory.")
    return executable


def main() -> None:
    """Build a self-contained backend without using host or user caches."""
    executable_name = "qfusion-backend.exe" if platform.system() == "Windows" else "qfusion-backend"
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    NUITKA_CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    BUILD_MANIFEST.unlink(missing_ok=True)

    command = [
        sys.executable,
        "-m",
        "nuitka",
        "--mode=standalone",
        f"--output-dir={OUTPUT_DIRECTORY}",
        f"--output-filename={executable_name}",
        "--python-flag=-m",
    ]
    dependency_scanner = "platform-default"
    if platform.system() == "Windows":
        # Nuitka 2.8 provides an inline pefile scanner. Selecting it avoids the
        # unverified Dependency Walker download and its HTTP fallback entirely.
        command.append("--experimental=force-dependencies-pefile")
        dependency_scanner = "nuitka-inline-pefile"
    command.append(str(PACKAGE_DIRECTORY))

    build_environment = os.environ.copy()
    build_environment["NUITKA_CACHE_DIR"] = str(NUITKA_CACHE_DIRECTORY)
    build_environment["NUITKA_CACHE_DIR_DOWNLOADS"] = str(
        NUITKA_CACHE_DIRECTORY / "downloads"
    )

    # Every argument and environment override is a repository-owned constant.
    subprocess.run(  # noqa: S603
        command,
        cwd=REPOSITORY_ROOT,
        env=build_environment,
        check=True,
    )

    executable = _find_standalone_executable(executable_name)
    manifest = {
        "schema_version": 1,
        "artifact_type": "nuitka-standalone",
        "dependency_scanner": dependency_scanner,
        "executable": executable.relative_to(REPOSITORY_ROOT).as_posix(),
        "sha256": _sha256(executable),
    }
    BUILD_MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"QFUSION_BACKEND_BUILD_OK executable={manifest['executable']}")
    print(f"QFUSION_BACKEND_SHA256={manifest['sha256']}")


if __name__ == "__main__":
    main()
