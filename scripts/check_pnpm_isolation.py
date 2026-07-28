"""Block pnpm before it purges a modules tree created from a non-project store."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULES_METADATA_PATH = REPOSITORY_ROOT / "node_modules" / ".modules.yaml"
EXPECTED_STORE_ROOT = REPOSITORY_ROOT / ".cache" / "pnpm" / "store"
# pnpm 10.13.1 records the effective content-addressable Store below this directory.
EXPECTED_STORE_LAYOUT_DIRECTORY = "v10"
STORE_DIRECTORY_PREFIX = "storeDir:"


class IsolationBoundaryError(ValueError):
    """Report metadata that cannot be trusted without touching external paths."""


def lexical_absolute_path(path: Path) -> Path:
    """Build a normalized absolute path without resolving symbolic links."""
    absolute_path = path if path.is_absolute() else Path.cwd() / path
    return Path(os.path.normpath(os.fspath(absolute_path)))


def normalized_path(path: Path) -> str:
    """Normalize a path lexically without reading its target."""
    return os.path.normcase(os.fspath(lexical_absolute_path(path)))


def has_symlink_component(path: Path, repository_root: Path) -> bool:
    """Check repository-local path components with lstat semantics."""
    normalized_root = lexical_absolute_path(repository_root)
    normalized_candidate = lexical_absolute_path(path)
    try:
        relative_path = normalized_candidate.relative_to(normalized_root)
    except ValueError as error:
        raise IsolationBoundaryError("pnpm path is outside the QFusion repository") from error

    current_path = normalized_root
    if current_path.is_symlink():
        return True

    for component in relative_path.parts:
        current_path /= component
        if current_path.is_symlink():
            return True
    return False


def configured_store_path(
    modules_metadata_path: Path,
    repository_root: Path,
) -> Path | None:
    """Read pnpm's recorded store path from workspace-local metadata."""
    if has_symlink_component(modules_metadata_path, repository_root):
        raise IsolationBoundaryError("node_modules metadata path contains a symbolic link")

    if not modules_metadata_path.is_file():
        return None

    store_values = [
        line.removeprefix(STORE_DIRECTORY_PREFIX).strip()
        for line in modules_metadata_path.read_text(encoding="utf-8").splitlines()
        if line.startswith(STORE_DIRECTORY_PREFIX)
    ]
    if len(store_values) != 1 or not store_values[0]:
        raise IsolationBoundaryError("node_modules metadata has no unique pnpm Store")

    store_path = Path(store_values[0])
    if os.pardir in store_path.parts:
        raise IsolationBoundaryError("node_modules metadata contains a parent path reference")
    if not store_path.is_absolute():
        store_path = repository_root / store_path
    return store_path


def blocked(message: str) -> int:
    """Emit the mandatory isolation marker and a non-sensitive explanation."""
    print("BLOCKED_BY_HOST_ISOLATION", file=sys.stderr)
    print(message, file=sys.stderr)
    return 1


def main(
    *,
    modules_metadata_path: Path = MODULES_METADATA_PATH,
    repository_root: Path = REPOSITORY_ROOT,
    expected_store_root: Path = EXPECTED_STORE_ROOT,
    expected_store_layout_directory: str = EXPECTED_STORE_LAYOUT_DIRECTORY,
) -> int:
    """Accept only an existing modules tree tied to the exact project Store layout."""
    try:
        existing_store_path = configured_store_path(
            modules_metadata_path,
            repository_root,
        )
    except IsolationBoundaryError:
        return blocked(
            "Existing node_modules metadata cannot be verified without crossing "
            "the project isolation boundary."
        )

    if existing_store_path is None:
        return 0

    expected_store_path = expected_store_root / expected_store_layout_directory
    if normalized_path(existing_store_path) != normalized_path(expected_store_path):
        return blocked(
            "Existing node_modules uses a different pnpm store. "
            "It will not be purged or reinstalled without explicit approval."
        )

    try:
        store_has_symlink = has_symlink_component(expected_store_path, repository_root)
    except IsolationBoundaryError:
        store_has_symlink = True
    if store_has_symlink:
        return blocked(
            "The configured project-local pnpm store path contains a symbolic link "
            "or leaves the QFusion repository."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
