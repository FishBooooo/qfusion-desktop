"""Auditable, secret-free metadata for a manually captured SEC response."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal, Self
from uuid import UUID, uuid5

from pydantic import Field, StringConstraints, field_validator, model_validator

from qfusion.domain import Market
from qfusion.providers.contracts import ProviderContract
from qfusion.providers.sec.contracts import SecCik, SecFilingRequest, SecJsonResponse
from qfusion.providers.sec.errors import SecPayloadError
from qfusion.providers.sec.parser import parse_sec_submissions

_CAPTURE_INSTRUMENT_NAMESPACE = UUID("3bf2a194-17b9-4fa3-a33a-2ec9939eedc4")
CommitSha = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[0-9a-f]{40}$"),
]
RunIdentifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[1-9][0-9]{0,31}$"),
]
Sha256Text = Annotated[
    str,
    StringConstraints(pattern=r"^[0-9a-f]{64}$"),
]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("SEC capture timestamps must be timezone-aware")
    return value.astimezone(UTC)


class SecCaptureManifest(ProviderContract):
    """Secret-free provenance for one exact official response Artifact."""

    schema_version: Literal["1.0.0"] = "1.0.0"
    provider_name: Literal["sec-edgar"] = "sec-edgar"
    provider_version: Literal["1.0.0"] = "1.0.0"
    cik: SecCik
    source_url: str = Field(min_length=1, max_length=256)
    raw_filename: str = Field(min_length=1, max_length=64)
    received_at: datetime
    source_commit: CommitSha
    source_run_id: RunIdentifier
    raw_body_sha256: Sha256Text
    raw_body_size: int = Field(ge=2, le=50 * 1024 * 1024)
    content_type: str | None = Field(default=None, min_length=1, max_length=256)
    etag: str | None = Field(default=None, min_length=1, max_length=512)
    last_modified: str | None = Field(default=None, min_length=1, max_length=128)
    validated_filing_count: int = Field(ge=0, le=1000)

    @field_validator("received_at")
    @classmethod
    def normalize_received_at(cls, value: datetime) -> datetime:
        return _as_utc(value)

    @model_validator(mode="after")
    def require_fixed_source_identity(self) -> Self:
        expected_url = (
            f"https://data.sec.gov/submissions/CIK{self.cik}.json"
        )
        if self.source_url != expected_url:
            raise ValueError("SEC capture manifest source URL is not the fixed origin")
        if self.raw_filename != f"CIK{self.cik}.json":
            raise ValueError("SEC capture raw filename does not match the CIK")
        return self


def build_sec_capture_manifest(
    response: SecJsonResponse,
    *,
    cik: SecCik,
    source_commit: CommitSha,
    source_run_id: RunIdentifier,
) -> SecCaptureManifest:
    """Validate the official shape and build provenance without contact data."""

    if response.content_type is not None:
        media_type = response.content_type.partition(";")[0].strip().lower()
        if media_type != "application/json":
            raise SecPayloadError("SEC capture response was not application/json")

    request = SecFilingRequest(
        instrument_id=uuid5(
            _CAPTURE_INSTRUMENT_NAMESPACE,
            f"sec-edgar:{cik}",
        ),
        provider_instrument_id=cik,
        market=Market.US,
    )
    records = parse_sec_submissions(
        response.payload,
        request,
        received_at=response.received_at,
        ingested_at=response.received_at,
    )
    return SecCaptureManifest(
        cik=cik,
        source_url=f"https://data.sec.gov/submissions/CIK{cik}.json",
        raw_filename=f"CIK{cik}.json",
        received_at=response.received_at,
        source_commit=source_commit,
        source_run_id=source_run_id,
        raw_body_sha256=response.raw_body_sha256,
        raw_body_size=response.raw_body_size,
        content_type=response.content_type,
        etag=response.etag,
        last_modified=response.last_modified,
        validated_filing_count=len(records),
    )


def write_sec_capture_bundle(
    response: SecJsonResponse,
    *,
    cik: SecCik,
    source_commit: CommitSha,
    source_run_id: RunIdentifier,
    output_directory: Path,
) -> tuple[SecCaptureManifest, Path, Path]:
    """Create a new bundle without overwriting any existing path."""

    manifest = build_sec_capture_manifest(
        response,
        cik=cik,
        source_commit=source_commit,
        source_run_id=source_run_id,
    )
    if output_directory.exists() or output_directory.is_symlink():
        raise FileExistsError("SEC capture output directory already exists")

    output_directory.mkdir(mode=0o700, parents=True)
    raw_path = output_directory / manifest.raw_filename
    manifest_path = output_directory / "manifest.json"
    raw_path.write_bytes(response.raw_body)
    manifest_path.write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest, raw_path, manifest_path
