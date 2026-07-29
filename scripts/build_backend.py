"""Build the Python backend as a standalone executable with Nuitka."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from qfusion.storage.migrations import verify_migration_assets

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIRECTORY = REPOSITORY_ROOT / "services" / "backend" / "qfusion"
MIGRATIONS_DIRECTORY = REPOSITORY_ROOT / "services" / "backend" / "migrations"
OUTPUT_DIRECTORY = REPOSITORY_ROOT / "dist" / "backend"
BUILD_MANIFEST = OUTPUT_DIRECTORY / "build-manifest.json"
NUITKA_CACHE_DIRECTORY = REPOSITORY_ROOT / ".cache" / "nuitka"
BUNDLED_MIGRATIONS_DIRECTORY_NAME = "qfusion_migrations"
SQLALCHEMY_SQLITE_DRIVER_MODULE = "sqlalchemy.dialects.sqlite.pysqlite"
SQLALCHEMY_EXCLUDED_MODULES = (
    "sqlalchemy.dialects.oracle.dictionary",
)


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


def _migration_source_files() -> tuple[Path, ...]:
    """Return the regular, repository-owned files required by Alembic."""

    if MIGRATIONS_DIRECTORY.is_symlink():
        raise RuntimeError("Refusing to package a symlinked migration directory.")

    source_root = MIGRATIONS_DIRECTORY.resolve(strict=True)
    versions_directory = source_root / "versions"
    required_files = (source_root / "env.py", source_root / "script.py.mako")
    version_files = tuple(sorted(versions_directory.glob("*.py")))

    if (
        versions_directory.is_symlink()
        or not versions_directory.is_dir()
        or not version_files
    ):
        raise RuntimeError("Migration versions directory is missing, symlinked, or empty.")

    source_files = (*required_files, *version_files)
    for source_file in source_files:
        if (
            source_file.is_symlink()
            or not source_file.is_file()
            or not source_file.resolve().is_relative_to(source_root)
        ):
            raise RuntimeError(f"Unsafe migration source file: {source_file}")
    return source_files


def _copy_migration_assets(destination: Path) -> list[dict[str, str]]:
    """Copy exact Alembic assets next to the standalone executable and hash them."""

    output_root = OUTPUT_DIRECTORY.resolve()
    resolved_destination = destination.resolve()
    if (
        not resolved_destination.is_relative_to(output_root)
        or resolved_destination == output_root
        or destination.is_symlink()
    ):
        raise RuntimeError("Refusing to write migration assets outside the build directory.")

    if destination.exists():
        if not destination.is_dir():
            raise RuntimeError("Migration asset target exists but is not a directory.")
        shutil.rmtree(destination)
    destination.mkdir(parents=True)

    source_root = MIGRATIONS_DIRECTORY.resolve(strict=True)
    records: list[dict[str, str]] = []
    for source_file in _migration_source_files():
        relative_path = source_file.relative_to(source_root)
        target_file = destination / relative_path
        target_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_file, target_file)
        source_sha256 = _sha256(source_file)
        if _sha256(target_file) != source_sha256:
            raise RuntimeError(
                "Copied migration asset failed SHA-256 verification: "
                f"{relative_path}"
            )
        records.append(
            {
                "path": relative_path.as_posix(),
                "sha256": source_sha256,
            }
        )
    return records


def _build_nuitka_command(
    executable_name: str, *, system_name: str | None = None
) -> tuple[list[str], str]:
    """Build the audited Nuitka command for the Local Lite backend."""

    selected_system = system_name or platform.system()
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
    if selected_system == "Windows":
        # Nuitka 2.8 provides an inline pefile scanner. Selecting it avoids the
        # unverified Dependency Walker download and its HTTP fallback entirely.
        command.append("--experimental=force-dependencies-pefile")
        dependency_scanner = "nuitka-inline-pefile"

    # M1 Local Lite explicitly retains pysqlite. Alembic imports its built-in
    # DDL implementations at module initialization, so the SQLAlchemy server
    # dialect entry points must remain importable even though QFusion never opens
    # those databases. Exclude only Oracle's very large reflection dictionary,
    # which is not imported by Alembic and previously exhausted MSVC pass 2.
    command.append(f"--include-module={SQLALCHEMY_SQLITE_DRIVER_MODULE}")
    command.extend(
        f"--nofollow-import-to={module_name}"
        for module_name in SQLALCHEMY_EXCLUDED_MODULES
    )
    command.append(str(PACKAGE_DIRECTORY))
    return command, dependency_scanner


def main() -> None:
    """Build a self-contained backend without using host or user caches."""

    system_name = platform.system()
    executable_name = "qfusion-backend.exe" if system_name == "Windows" else "qfusion-backend"
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    NUITKA_CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    BUILD_MANIFEST.unlink(missing_ok=True)
    migration_heads = verify_migration_assets()
    command, dependency_scanner = _build_nuitka_command(
        executable_name,
        system_name=system_name,
    )

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
    migration_directory = executable.parent / BUNDLED_MIGRATIONS_DIRECTORY_NAME
    migration_files = _copy_migration_assets(migration_directory)
    manifest = {
        "schema_version": 2,
        "artifact_type": "nuitka-standalone",
        "dependency_scanner": dependency_scanner,
        "executable": executable.relative_to(REPOSITORY_ROOT).as_posix(),
        "sha256": _sha256(executable),
        "migration_assets": {
            "directory": migration_directory.relative_to(REPOSITORY_ROOT).as_posix(),
            "heads": list(migration_heads),
            "files": migration_files,
        },
    }
    BUILD_MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"QFUSION_BACKEND_BUILD_OK executable={manifest['executable']}")
    print(f"QFUSION_BACKEND_SHA256={manifest['sha256']}")
    print(f"QFUSION_MIGRATION_HEADS={','.join(migration_heads)}")


if __name__ == "__main__":
    main()
