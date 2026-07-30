"""BLS Adapter tests for license gates, transport delegation, and PIT output."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from pydantic import JsonValue
from pytest import raises

from qfusion.providers import (
    BlsJsonResponse,
    BlsPublicDataProvider,
    BlsSeriesRequest,
    ProviderCapability,
    ProviderUsageStatus,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = REPOSITORY_ROOT / "fixtures/bls/public-data-v1-schema-fixture.json"
OBSERVED_AT = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
REQUEST = BlsSeriesRequest(
    series_ids=("QFUSION_TEST_01",),
    start_year=2025,
    end_year=2026,
)


class FixtureTransport:
    def __init__(self) -> None:
        self.requests: list[BlsSeriesRequest] = []

    async def get_series(self, request: BlsSeriesRequest) -> BlsJsonResponse:
        self.requests.append(request)
        raw_body = FIXTURE_PATH.read_bytes()
        loaded: object = json.loads(raw_body)
        assert isinstance(loaded, dict)
        return BlsJsonResponse(
            payload=cast(dict[str, JsonValue], loaded),
            raw_body=raw_body,
            received_at=OBSERVED_AT,
            content_type="application/json",
        )


class CapabilityOverrideProvider(BlsPublicDataProvider):
    def __init__(
        self,
        transport: FixtureTransport,
        capability: ProviderCapability,
    ) -> None:
        super().__init__(transport)
        self._capability_override = capability

    @property
    def capability(self) -> ProviderCapability:
        return self._capability_override


def test_adapter_delegates_once_and_returns_first_observed_records() -> None:
    transport = FixtureTransport()
    provider = BlsPublicDataProvider(transport)

    records = asyncio.run(provider.get_series(REQUEST))

    assert transport.requests == [REQUEST]
    assert len(records) == 2
    assert all(record.available_at == OBSERVED_AT for record in records)
    assert all(record.source == "bls-public-data-v1" for record in records)


def test_persistent_storage_license_gate_runs_before_transport() -> None:
    transport = FixtureTransport()
    base = BlsPublicDataProvider(transport).capability
    policy = base.usage_policy.model_copy(
        update={"persistent_storage": ProviderUsageStatus.PROHIBITED}
    )
    provider = CapabilityOverrideProvider(
        transport,
        base.model_copy(update={"usage_policy": policy}),
    )

    with raises(PermissionError, match="BLOCKED_BY_PROVIDER_LICENSE.*persistent_storage"):
        asyncio.run(provider.get_series(REQUEST))
    assert transport.requests == []


def test_model_processing_license_gate_runs_before_transport() -> None:
    transport = FixtureTransport()
    base = BlsPublicDataProvider(transport).capability
    policy = base.usage_policy.model_copy(
        update={"model_processing": ProviderUsageStatus.UNVERIFIED}
    )
    provider = CapabilityOverrideProvider(
        transport,
        base.model_copy(update={"usage_policy": policy}),
    )

    with raises(PermissionError, match="BLOCKED_BY_PROVIDER_LICENSE.*model_processing"):
        asyncio.run(provider.get_series(REQUEST))
    assert transport.requests == []
