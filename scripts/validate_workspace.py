"""Validate the deterministic M0 workspace structure without changing files."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tomllib
from pathlib import Path
from typing import TypedDict
from urllib.parse import unquote

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPOSITORY_ROOT / "workspace-baseline.json"
IGNORED_DIRECTORY_NAMES = {
    ".cache",
    ".tmp",
    ".toolchains",
    ".venv",
    "build",
    "coverage",
    "dist",
    "htmlcov",
    "node_modules",
    "playwright-report",
    "target",
    "test-results",
}
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


class WorkspaceBaseline(TypedDict):
    """Machine-readable M0 path requirements."""

    forbidden_paths: list[str]
    milestone: str
    required_directories: list[str]
    required_files: list[str]
    schema_version: int


def load_baseline() -> WorkspaceBaseline:
    """Load the baseline and reject an incompatible top-level value."""
    payload: object = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("workspace baseline must be a JSON object")
    return WorkspaceBaseline(
        forbidden_paths=list(payload["forbidden_paths"]),
        milestone=str(payload["milestone"]),
        required_directories=list(payload["required_directories"]),
        required_files=list(payload["required_files"]),
        schema_version=int(payload["schema_version"]),
    )


def syntax_errors() -> list[str]:
    """Return JSON and TOML syntax errors for checked-in workspace metadata."""
    errors: list[str] = []
    for path in sorted(REPOSITORY_ROOT.rglob("*.json")):
        if any(part in IGNORED_DIRECTORY_NAMES for part in path.parts):
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            errors.append(f"invalid JSON: {path.relative_to(REPOSITORY_ROOT)}: {error}")

    for path in sorted(REPOSITORY_ROOT.rglob("*.toml")):
        if any(part in IGNORED_DIRECTORY_NAMES for part in path.parts):
            continue
        try:
            tomllib.loads(path.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
            errors.append(f"invalid TOML: {path.relative_to(REPOSITORY_ROOT)}: {error}")
    return errors


def markdown_link_errors() -> list[str]:
    """Return broken relative Markdown links while leaving external URLs untouched."""
    errors: list[str] = []
    for path in sorted(REPOSITORY_ROOT.rglob("*.md")):
        if any(part in IGNORED_DIRECTORY_NAMES for part in path.parts):
            continue
        content = path.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK_PATTERN.finditer(content):
            raw_target = match.group(1).strip().strip("<>")
            if raw_target.startswith(("http://", "https://", "mailto:")):
                continue
            target_without_fragment = raw_target.partition("#")[0]
            if not target_without_fragment:
                continue
            target = path.parent / unquote(target_without_fragment)
            if not target.exists():
                relative_source = path.relative_to(REPOSITORY_ROOT)
                errors.append(f"broken Markdown link: {relative_source} -> {raw_target}")
    return errors


def validate_structure(baseline: WorkspaceBaseline) -> list[str]:
    """Return all structural violations instead of stopping at the first one."""
    errors: list[str] = []
    for relative_path in baseline["required_files"]:
        path = REPOSITORY_ROOT / relative_path
        if not path.is_file():
            errors.append(f"missing required file: {relative_path}")

    for relative_path in baseline["required_directories"]:
        path = REPOSITORY_ROOT / relative_path
        if not path.is_dir():
            errors.append(f"missing required directory: {relative_path}")

    for relative_path in baseline["forbidden_paths"]:
        path = REPOSITORY_ROOT / relative_path
        if path.exists():
            errors.append(f"forbidden compatibility path exists: {relative_path}")

    errors.extend(syntax_errors())
    errors.extend(markdown_link_errors())
    return errors


def validate_tools() -> list[str]:
    """Report missing project tools without installing or changing the host."""
    tool_names = ["python3", "uv", "node", "pnpm", "cargo", "rustc", "just"]
    return [
        f"missing tool: {tool_name}"
        for tool_name in tool_names
        if shutil.which(tool_name) is None
    ]


def parse_args() -> argparse.Namespace:
    """Parse optional toolchain validation mode."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-tools",
        action="store_true",
        help="also require the full Python/Node/Rust/just toolchain",
    )
    return parser.parse_args()


def main() -> int:
    """Validate structure and return a process-friendly exit code."""
    arguments = parse_args()
    baseline = load_baseline()
    errors = validate_structure(baseline)
    if arguments.with_tools:
        errors.extend(validate_tools())

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(
        "Workspace baseline valid: "
        f"schema={baseline['schema_version']} milestone={baseline['milestone']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
