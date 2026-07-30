"""Network-free tests for audited SEC response capture bundles."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

from pydantic import JsonValue, ValidationError
from pytest import raises

from qfusion.providers.sec import (
    SecJsonResponse,
    SecPayloadError,
    build_sec_capture_manifest,
    write_sec_capture_bundle,
)

_REPOSITORY_ROOT = Path(__file__).parents[3]
_FIXTURE = _REPOSITORY_ROOT / "fixtures" / "sec" / "submissions-schema-fixture.json"
_RECEIVED_AT = datetime(2026, 5, 8, tzinfo=UTC)
_COMMIT = "a" * 40
_RUN_ID = "123456789"


def fixture_response(*, content_type: str = "application/json") -> SecJsonResponse:
    raw_body = _FIXTURE.read_bytes()
    decoded: object = json.loads(raw_body)
    if not isinstance(decoded, dict) or not all(
        isinstance(key, str) for key in decoded
    ):
        raise TypeError("SEC capture fixture must be a JSON object")
    return SecJsonResponse(
        payload=cast(dict[str, JsonValue], decoded),
        raw_body=raw_body,
        received_at=_RECEIVED_AT,
        content_type=content_type,
        etag='"synthetic-etag"',
        last_modified="Fri, 08 May 2026 00:00:00 GMT",
    )


def test_manifest_validates_shape_and_excludes_runtime_contact() -> None:
    manifest = build_sec_capture_manifest(
        fixture_response(),
        cik="0000000001",
        source_commit=_COMMIT,
        source_run_id=_RUN_ID,
    )

    assert manifest.source_url.endswith("/submissions/CIK0000000001.json")
    assert manifest.raw_filename == "CIK0000000001.json"
    assert manifest.validated_filing_count == 2
    assert len(manifest.raw_body_sha256) == 64
    serialized = manifest.model_dump_json()
    assert "User-Agent" not in serialized
    assert "ci@example.com" not in serialized


def test_bundle_preserves_exact_bytes_and_manifest_provenance() -> None:
    response = fixture_response()
    output_directory = (
        _REPOSITORY_ROOT
        / ".tmp"
        / "tests"
        / f"sec-capture-{uuid4().hex}"
    )
    try:
        manifest, raw_path, manifest_path = write_sec_capture_bundle(
            response,
            cik="0000000001",
            source_commit=_COMMIT,
            source_run_id=_RUN_ID,
            output_directory=output_directory,
        )

        assert raw_path.read_bytes() == response.raw_body
        decoded_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert decoded_manifest["raw_body_sha256"] == manifest.raw_body_sha256
        assert decoded_manifest["source_commit"] == _COMMIT
        with raises(FileExistsError, match="already exists"):
            write_sec_capture_bundle(
                response,
                cik="0000000001",
                source_commit=_COMMIT,
                source_run_id=_RUN_ID,
                output_directory=output_directory,
            )
    finally:
        if output_directory.exists() and not output_directory.is_symlink():
            shutil.rmtree(output_directory)


def test_response_rejects_raw_payload_mismatch() -> None:
    response = fixture_response()

    with raises(ValidationError, match="does not match"):
        SecJsonResponse(
            payload=response.payload,
            raw_body=b'{"cik":2}',
            received_at=_RECEIVED_AT,
        )


def test_manifest_rejects_unexpected_media_type() -> None:
    with raises(SecPayloadError, match="application/json"):
        build_sec_capture_manifest(
            fixture_response(content_type="text/html"),
            cik="0000000001",
            source_commit=_COMMIT,
            source_run_id=_RUN_ID,
        )
