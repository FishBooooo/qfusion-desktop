"""Checked-in JSON Schema drift tests."""

from __future__ import annotations

import json
from pathlib import Path

from qfusion.domain import AnalysisSnapshot, DataSourceRecord

SCHEMA_DIRECTORY = Path(__file__).resolve().parents[3] / "schemas"


def load_schema(filename: str) -> object:
    return json.loads((SCHEMA_DIRECTORY / filename).read_text(encoding="utf-8"))


def test_analysis_snapshot_schema_matches_pydantic_contract() -> None:
    assert load_schema("analysis_snapshot.schema.json") == AnalysisSnapshot.model_json_schema()


def test_data_source_record_schema_matches_pydantic_contract() -> None:
    assert load_schema("data_source_record.schema.json") == DataSourceRecord.model_json_schema()
