"""SEC Adapter integration tests using only the repository fixture."""

from __future__ import annotations

import asyncio
import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import JsonValue, cast
from uuid import UUID

from pydantic import ValidationError
from pytest import raises

from qfusion.domain import Market
from qfusion.providers.sec import (
    SecEdgarProvider,
    SecFilingRequest,
    SecJsonResponse,
)

_FIXTURE = (
    Path(__file__).parents[3] / "fixtures" / "sec" / "submissions-schema-fixture.json"
)
INSTRUMENT_ID = UUID("30000000-0000-4000-8000-000000000001")
RECEIVED_AT = datetime(2026, 5, 8, tzinfo=UTC)


def load_fixture() -> dict[str, JsonValue]:
    decoded: object = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    if not isinstance(decoded, dict) or not all(isinstance(key, str) for key in decoded):
        raise TypeError("SEC test fixture must be a JSON object")
    return cast(dict[str, JsonValue], decoded)


class FixtureTransport:
    def __init__(self, payload: dict[str, JsonValue]) -> None:
        self.payload = copy.deepcopy(payload)
        self.ciks: list[str] = []

    async def get_submissions(self, cik: str) -> SecJsonResponse:
        self.ciks.append(cik)
        return SecJsonResponse(
            payload=copy.deepcopy(self.payload),
            received_at=RECEIVED_AT,
        )


def request(**overrides: object) -> SecFilingRequest:
    values: dict[str, object] = {
        "instrument_id": INSTRUMENT_ID,
        "provider_instrument_id": "0000000001",
        "market": Market.US,
        "decision_time": RECEIVED_AT + timedelta(seconds=1),
    }
    values.update(overrides)
    return SecFilingRequest.model_validate(values)


def test_adapter_uses_registry_cik_and_returns_point_in_time_records() -> None:
    transport = FixtureTransport(load_fixture())
    provider = SecEdgarProvider(transport)

    records = asyncio.run(provider.get_filings(request()))

    assert transport.ciks == ["0000000001"]
    assert len(records) == 2
    assert all(record.instrument_id == INSTRUMENT_ID for record in records)
    assert all(record.available_at <= request().decision_time for record in records)


def test_adapter_returns_empty_when_first_observation_is_after_decision() -> None:
    provider = SecEdgarProvider(FixtureTransport(load_fixture()))

    records = asyncio.run(
        provider.get_filings(
            request(decision_time=RECEIVED_AT - timedelta(microseconds=1))
        )
    )

    assert records == ()


def test_adapter_filters_form_without_mutating_transport_payload() -> None:
    payload = load_fixture()
    transport = FixtureTransport(payload)
    provider = SecEdgarProvider(transport)

    records = asyncio.run(provider.get_filings(request(forms=("10-k",))))

    assert len(records) == 1
    assert records[0].payload["form"] == "10-K"
    assert transport.payload == payload


def test_adapter_rejects_non_us_request_before_transport() -> None:
    with raises(ValidationError, match="US market"):
        request(market=Market.HK)
