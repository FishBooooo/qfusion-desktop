"""Reject uv lock updates that mutate existing dependency versions."""

from __future__ import annotations

import argparse
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path


def _canonical_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def load_package_versions(path: Path) -> dict[str, tuple[str, ...]]:
    """Return every locked version grouped by normalized package name."""

    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    raw_packages = payload.get("package")
    if not isinstance(raw_packages, list):
        raise TypeError(f"lock file has no package list: {path}")

    versions: dict[str, set[str]] = {}
    for package in raw_packages:
        if not isinstance(package, dict):
            raise TypeError(f"invalid package entry in lock file: {path}")
        name = package.get("name")
        version = package.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            raise TypeError(f"package entry lacks name/version in lock file: {path}")
        versions.setdefault(_canonical_name(name), set()).add(version)

    return {
        name: tuple(sorted(package_versions))
        for name, package_versions in sorted(versions.items())
    }


def validate_lock_update(
    before: dict[str, tuple[str, ...]],
    after: dict[str, tuple[str, ...]],
    allowed_new: set[str],
) -> list[str]:
    """Return deterministic violations of the no-existing-version-change policy."""

    errors: list[str] = []
    removed = sorted(set(before) - set(after))
    for name in removed:
        errors.append(f"existing package removed: {name} {before[name]}")

    for name in sorted(set(before) & set(after)):
        if before[name] != after[name]:
            errors.append(
                f"existing package version changed: {name} {before[name]} -> {after[name]}"
            )

    unexpected = sorted(set(after) - set(before) - allowed_new)
    for name in unexpected:
        errors.append(f"unexpected new package: {name} {after[name]}")

    return errors


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse lock file paths and the explicit new-package allowlist."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", required=True, type=Path)
    parser.add_argument("--allow-new", action="append", default=[])
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    """Validate one candidate lock update."""

    options = parse_args(arguments)
    allowed_new = {_canonical_name(name) for name in options.allow_new}
    errors = validate_lock_update(
        load_package_versions(options.before),
        load_package_versions(options.after),
        allowed_new,
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("uv lock update preserved every existing package version")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
