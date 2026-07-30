"""BLS request, capability, access, and exact-response contract tests."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta, timezone

from pydantic import ValidationError
from pytest import raises

from qfusion.providers import (
    BlsJsonResponse,
    BlsMacroSeriesProvider,
    BlsPublicDataProvider,
    BlsSeriesRequest,
    BlsTransportConfig,
    ProviderAdapter,
    ProviderOperation,
    ProviderUsage,
    ProviderUsageStatus,
    validate_bls_series_request,
    validate_provider_usage,
)

OBSERVED_AT = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)


class EmptyTransport:
    async def get_series(self, request: BlsSeriesRequest) -> BlsJsonResponse:
        payload: dict[str, object] = {
            "status": "REQUEST_SUCCEEDED",
            "message": [],
            "Results": {
                "series": [
                    {"seriesID": series_id, "data": []}
                    for series_id in request.series_ids
                ]
            },
        }
        raw_body = json.dumps(payload, separators=(",", ":")).encode()
        return BlsJsonResponse(
            payload=payload,
            raw_body=raw_body,
            received_at=OBSERVED_AT,
            content_type="application/json",
        )


def make_request(**overrides: object) -> BlsSeriesRequest:
    values: dict[str, object] = {
        "series_ids": ("QFUSION_TEST_02", "QFUSION_TEST_01"),
        "start_year": 2017,
        "end_year": 2026,
    }
    values.update(overrides)
    return BlsSeriesRequest.model_validate(values)


def test_request_is_canonical_bounded_and_credential_free() -> None:
    request = make_request()

    assert request.series_ids == ("QFUSION_TEST_01", "QFUSION_TEST_02")
    assert request.api_payload() == {
        "seriesid": ["QFUSION_TEST_01", "QFUSION_TEST_02"],
        "startyear": "2017",
        "endyear": "2026",
    }
    assert "registrationkey" not in request.api_payload()


def test_request_rejects_invalid_series_and_year_windows() -> None:
    with raises(ValidationError, match="series_ids must not be empty"):
        make_request(series_ids=())
    with raises(ValidationError, match="at most 25 series"):
        make_request(series_ids=tuple(f"QFUSION_{index:02d}" for index in range(26)))
    with raises(ValidationError, match="series_ids must be unique"):
        make_request(series_ids=("QFUSION_TEST_01", "QFUSION_TEST_01"))
    with raises(ValidationError, match="string_pattern_mismatch"):
        make_request(series_ids=("not valid",))
    with raises(ValidationError, match="start_year must not be after end_year"):
        make_request(start_year=2026, end_year=2025)
    with raises(ValidationError, match="at most 10 years"):
        make_request(start_year=2016, end_year=2026)


def test_transport_config_requires_contact_and_caps_public_v1_budgets() -> None:
    config = BlsTransportConfig(user_agent="QFusion CI ci@example.com")

    assert config.max_requests_per_day == 25
    assert config.max_requests_per_10_seconds == 5
    assert config.max_attempts == 3

    with raises(ValidationError, match="product name and contact email"):
        BlsTransportConfig(user_agent="anonymous")
    with raises(ValidationError, match="line breaks"):
        BlsTransportConfig(user_agent="QFusion ci@example.com\nInjected: value")
    with raises(ValidationError):
        BlsTransportConfig(
            user_agent="QFusion CI ci@example.com",
            max_requests_per_day=26,
        )
    with raises(ValidationError):
        BlsTransportConfig(
            user_agent="QFusion CI ci@example.com",
            max_requests_per_10_seconds=51,
        )


def test_json_response_preserves_exact_body_hash_and_utc_receipt() -> None:
    payload = {"status": "REQUEST_SUCCEEDED", "message": [], "Results": {}}
    raw_body = json.dumps(payload, separators=(",", ":")).encode()
    offset = timezone(timedelta(hours=8))
    response = BlsJsonResponse(
        payload=payload,
        raw_body=raw_body,
        received_at=datetime(2026, 7, 31, 20, 0, tzinfo=offset),
        content_type="application/json",
    )

    assert response.received_at == OBSERVED_AT
    assert response.raw_body_size == len(raw_body)
    assert response.raw_body_sha256 == hashlib.sha256(
        raw_body,
        usedforsecurity=False,
    ).hexdigest()


def test_json_response_rejects_naive_malformed_or_mismatched_body() -> None:
    payload = {"status": "REQUEST_SUCCEEDED"}
    raw_body = b'{"status":"REQUEST_SUCCEEDED"}'

    with raises(ValidationError, match="timezone-aware"):
        BlsJsonResponse(
            payload=payload,
            raw_body=raw_body,
            received_at=datetime(2026, 7, 31, 12, 0),
        )
    with raises(ValidationError, match="valid JSON"):
        BlsJsonResponse(
            payload=payload,
            raw_body=b"not-json",
            received_at=OBSERVED_AT,
        )
    with raises(ValidationError, match="JSON object"):
        BlsJsonResponse(
            payload=payload,
            raw_body=b"[]",
            received_at=OBSERVED_AT,
        )
    with raises(ValidationError, match="does not match"):
        BlsJsonResponse(
            payload=payload,
            raw_body=b'{"status":"REQUEST_FAILED"}',
            received_at=OBSERVED_AT,
        )


def test_provider_declares_macro_only_public_v1_boundary() -> None:
    provider = BlsPublicDataProvider(EmptyTransport())

    assert isinstance(provider, ProviderAdapter)
    assert isinstance(provider, BlsMacroSeriesProvider)
    assert provider.capability.schema_version == "3.0.0"
    assert provider.capability.provider_name == "bls-public-data-v1"
    assert provider.capability.supported_asset_types == ()
    assert provider.capability.operations == (ProviderOperation.MACRO_SERIES,)
    assert provider.capability.rate_limit[0].max_requests == 25
    assert provider.capability.rate_limit[0].window_seconds == 86_400
    assert provider.capability.rate_limit[0].max_concurrent == 1
    assert provider.access_profile.access_scope == "public-v1-no-registration"
    assert provider.access_profile.enabled_operations == (
        ProviderOperation.MACRO_SERIES,
    )
    assert provider.access_profile.market_data_quality == ()
    assert provider.capability.usage_policy.model_processing is (
        ProviderUsageStatus.ALLOWED
    )
    assert validate_provider_usage(
        provider.capability,
        ProviderUsage.MODEL_PROCESSING,
    ) is provider.capability.usage_policy
    with raises(PermissionError, match="BLOCKED_BY_PROVIDER_LICENSE"):
        validate_provider_usage(provider.capability, ProviderUsage.PUBLIC_DISPLAY)


def test_request_gate_requires_declared_and_enabled_macro_operation() -> None:
    provider = BlsPublicDataProvider(EmptyTransport())
    request = make_request(series_ids=("QFUSION_TEST_01",))

    assert validate_bls_series_request(
        provider.capability,
        provider.access_profile,
        request,
    ) is request

    no_capability = provider.capability.model_copy(
        update={"operations": (ProviderOperation.FILINGS,)}
    )
    with raises(ValueError, match="does not implement macro series"):
        validate_bls_series_request(no_capability, provider.access_profile, request)

    no_access = provider.access_profile.model_copy(update={"enabled_operations": ()})
    with raises(PermissionError, match="does not enable macro series"):
        validate_bls_series_request(provider.capability, no_access, request)
