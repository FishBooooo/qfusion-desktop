"""Manually capture one official SEC submissions response on an isolated Runner."""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from qfusion.providers.sec import (
    SecCaptureManifest,
    SecHttpTransport,
    SecNetworkPolicyError,
    SecPayloadError,
    SecTransportConfig,
    SecTransportError,
    write_sec_capture_bundle,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIRECTORY = REPOSITORY_ROOT / ".tmp" / "sec-official-capture"
_CIK_PATTERN = re.compile(r"^\d{10}$")
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_RUN_ID_PATTERN = re.compile(r"^[1-9][0-9]{0,31}$")


class SecCaptureConfigurationError(ValueError):
    """The manual capture gate was not configured safely."""


@dataclass(frozen=True)
class CaptureArguments:
    """Validated command-line inputs that never contain the contact value."""

    cik: str
    user_agent_file: Path
    source_commit: str
    source_run_id: str


def _repository_path(path: Path, *, label: str) -> Path:
    candidate = path if path.is_absolute() else REPOSITORY_ROOT / path
    candidate = Path(os.path.abspath(candidate))
    try:
        relative = candidate.relative_to(REPOSITORY_ROOT)
    except ValueError as error:
        raise SecCaptureConfigurationError(
            f"{label} must remain inside the repository"
        ) from error

    current = REPOSITORY_ROOT
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise SecCaptureConfigurationError(f"{label} must not traverse symlinks")
    return candidate


def _read_user_agent(path: Path) -> str:
    candidate = _repository_path(path, label="SEC User-Agent file")
    temporary_root = _repository_path(
        REPOSITORY_ROOT / ".tmp",
        label="temporary root",
    )
    try:
        candidate.relative_to(temporary_root)
    except ValueError as error:
        raise SecCaptureConfigurationError(
            "SEC User-Agent file must be under the repository .tmp directory"
        ) from error
    if not candidate.is_file() or candidate.is_symlink():
        raise SecCaptureConfigurationError(
            "SEC User-Agent file must be a regular repository-local file"
        )
    metadata = candidate.stat()
    if metadata.st_size > 512:
        raise SecCaptureConfigurationError("SEC User-Agent file is too large")
    if metadata.st_mode & 0o077:
        raise SecCaptureConfigurationError(
            "SEC User-Agent file must not grant group or other permissions"
        )
    try:
        value = candidate.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise SecCaptureConfigurationError(
            "SEC User-Agent file must contain UTF-8 text"
        ) from error
    if not value.strip():
        raise SecCaptureConfigurationError("SEC User-Agent file is empty")
    return value


def _prepare_output_directory() -> Path:
    output_directory = _repository_path(
        OUTPUT_DIRECTORY,
        label="SEC capture output",
    )
    if output_directory.exists() or output_directory.is_symlink():
        raise SecCaptureConfigurationError(
            "SEC capture output already exists; use a clean Runner"
        )
    return output_directory


def parse_args() -> CaptureArguments:
    """Parse the manual gate inputs without exposing the contact value in argv."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cik", required=True)
    parser.add_argument("--user-agent-file", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-run-id", required=True)
    namespace = parser.parse_args()
    return CaptureArguments(
        cik=str(namespace.cik),
        user_agent_file=Path(namespace.user_agent_file),
        source_commit=str(namespace.source_commit),
        source_run_id=str(namespace.source_run_id),
    )


def _validate_identifiers(arguments: CaptureArguments) -> None:
    if _CIK_PATTERN.fullmatch(arguments.cik) is None:
        raise SecCaptureConfigurationError("CIK must contain exactly ten digits")
    if _COMMIT_PATTERN.fullmatch(arguments.source_commit) is None:
        raise SecCaptureConfigurationError("source commit must be a lowercase SHA-1")
    if _RUN_ID_PATTERN.fullmatch(arguments.source_run_id) is None:
        raise SecCaptureConfigurationError("source run ID is invalid")


async def capture_once(arguments: CaptureArguments) -> SecCaptureManifest:
    """Run one bounded fixed-origin request and write one new Artifact bundle."""

    _validate_identifiers(arguments)
    user_agent = _read_user_agent(arguments.user_agent_file)
    output_directory = _prepare_output_directory()
    try:
        config = SecTransportConfig(user_agent=user_agent)
    except ValidationError as error:
        raise SecCaptureConfigurationError(
            "SEC User-Agent failed the declared contact contract"
        ) from error

    async with SecHttpTransport(config) as transport:
        response = await transport.get_submissions(arguments.cik)
    manifest, _, _ = write_sec_capture_bundle(
        response,
        cik=arguments.cik,
        source_commit=arguments.source_commit,
        source_run_id=arguments.source_run_id,
        output_directory=output_directory,
    )
    return manifest


def main() -> int:
    """Return a process-safe status without logging the runtime contact value."""

    arguments = parse_args()
    try:
        manifest = asyncio.run(capture_once(arguments))
    except SecCaptureConfigurationError as error:
        print(f"SEC_CAPTURE_CONFIGURATION_INVALID: {error}", file=sys.stderr)
        return 2
    except ValidationError:
        print("SEC_CAPTURE_FAILED: provenance validation failed", file=sys.stderr)
        return 1
    except (
        OSError,
        SecNetworkPolicyError,
        SecPayloadError,
        SecTransportError,
    ) as error:
        print(
            f"SEC_CAPTURE_FAILED: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return 1

    print(
        "SEC_CAPTURE_OK "
        f"cik={manifest.cik} "
        f"raw_sha256={manifest.raw_body_sha256} "
        f"raw_size={manifest.raw_body_size}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
