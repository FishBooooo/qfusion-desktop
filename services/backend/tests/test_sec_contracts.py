"""SEC request, capability, and declared-access contract tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from pytest import raises

from qfusion.domain import Market
from qfusion.providers import ProviderAdapter, ProviderOperation
from qfusion.providers.sec import (
    SecEdgarProvider,
    SecFilingProvider,
    SecFilingRequest,
    SecJsonResponse,
    SecTransportConfig,
)

INSTRUMENT_ID = UUID("30000000-0000-4000-8000-000000000001")
DECISION_TIME = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)


class EmptyTransport:
    async def get_submissions(self, cik: str) -> SecJsonResponse:
        return SecJsonResponse(
            payload={
                "cik": int(cik),
                "name": "EMPTY",
                "filings": {
                    "recent": {
                        "accessionNumber": [],
                        "filingDate": [],
                        "reportDate": [],
                        "acceptanceDateTime": [],
                        "form": [],
                        "primaryDocument": [],
                    }
                },
            },
            received_at=DECISION_TIME,
        )


def make_request(**overrides: object) -> SecFilingRequest:
    values: dict[str, object] = {
        "instrument_id": INSTRUMENT_ID,
        "provider_instrument_id": "0000000001",
        "market": Market.US,
        "decision_time": DECISION_TIME,
    }
    values.update(overrides)
    return SecFilingRequest.model_validate(values)


def test_request_normalizes_forms_and_exposes_exact_cik() -> None:
    request = make_request(forms=("10-q", " 8-k "))

    assert request.forms == ("10-Q", "8-K")
    assert request.cik == "0000000001"


def test_request_rejects_noncanonical_cik_market_time_and_duplicate_forms() -> None:
    with raises(ValidationError, match="string_pattern_mismatch"):
        make_request(provider_instrument_id="1")
    with raises(ValidationError, match="US market"):
        make_request(market=Market.HK)
    with raises(ValidationError, match="timezone-aware"):
        make_request(decision_time=datetime(2026, 7, 30, 12, 0))
    with raises(ValidationError, match="forms must be unique"):
        make_request(forms=("10-k", "10-K"))


def test_transport_config_requires_declared_contact_and_caps_rate() -> None:
    config = SecTransportConfig(user_agent="QFusion CI ci@example.com")

    assert config.max_requests_per_second == 5
    assert config.max_attempts == 3

    with raises(ValidationError, match="product name and contact email"):
        SecTransportConfig(user_agent="anonymous")
    with raises(ValidationError, match="line breaks"):
        SecTransportConfig(user_agent="QFusion ci@example.com\nInjected: value")
    with raises(ValidationError):
        SecTransportConfig(
            user_agent="QFusion CI ci@example.com",
            max_requests_per_second=6,
        )


def test_provider_declares_public_no_auth_filings_only() -> None:
    provider = SecEdgarProvider(EmptyTransport())

    assert isinstance(provider, ProviderAdapter)
    assert isinstance(provider, SecFilingProvider)
    assert provider.capability.provider_name == "sec-edgar"
    assert provider.capability.operations == (ProviderOperation.FILINGS,)
    assert provider.capability.supports_filings
    assert not provider.capability.supports_fundamentals
    assert provider.access_profile.access_scope == "public-no-authentication"
    assert provider.access_profile.enabled_operations == (ProviderOperation.FILINGS,)
    assert provider.access_profile.market_data_quality == ()
    assert provider.capability.rate_limit[0].max_requests == 5
    assert provider.capability.rate_limit[0].max_concurrent == 1
