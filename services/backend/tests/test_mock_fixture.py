"""Safety checks for the M0 synthetic financial fixture."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

FIXTURE_PATH = (
    Path(__file__).resolve().parents[3] / "fixtures" / "market_data" / "mock-analysis.json"
)


def load_fixture() -> dict[str, Any]:
    """Load the checked-in fixture without accepting malformed top-level data."""
    payload: object = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("mock analysis fixture must be an object")
    return payload


def test_mock_fixture_cannot_be_mistaken_for_live_data() -> None:
    fixture = load_fixture()

    assert fixture["fixture_kind"] == "SYNTHETIC_MOCK"
    assert fixture["data_freshness"] == "SYNTHETIC_MOCK"
    assert fixture["source"] == "qfusion-synthetic-fixture"
    assert fixture["risk_permission"] == "PAPER_TRADE_ONLY"


def test_mock_fixture_uses_permanent_id_and_explicit_time() -> None:
    fixture = load_fixture()
    instrument = fixture["instrument"]
    timestamp = datetime.fromisoformat(fixture["as_of"])

    assert instrument["instrument_id"] != instrument["symbol_alias"]
    assert timestamp.tzinfo is not None
    assert fixture["market_timezone"] == "America/New_York"


def test_mock_fixture_has_three_independent_models_and_fusion() -> None:
    fixture = load_fixture()
    model_types = {item["model_type"] for item in fixture["perspectives"]}

    assert model_types == {"wallstreet", "quant", "hotmoney", "fusion"}
