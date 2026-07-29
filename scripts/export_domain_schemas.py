"""Export deterministic JSON Schemas for versioned domain contracts."""

from __future__ import annotations

import json
from pathlib import Path

from qfusion.domain.contracts import AnalysisSnapshot, DataSourceRecord

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIRECTORY = REPOSITORY_ROOT / "schemas"
SCHEMAS = {
    "analysis_snapshot.schema.json": AnalysisSnapshot.model_json_schema(),
    "data_source_record.schema.json": DataSourceRecord.model_json_schema(),
}


def main() -> None:
    """Write deterministic UTF-8 JSON Schema documents."""

    SCHEMA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for filename, schema in sorted(SCHEMAS.items()):
        output = json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True)
        output_path = SCHEMA_DIRECTORY / filename
        output_path.write_text(f"{output}\n", encoding="utf-8")
        print(f"Wrote {output_path.relative_to(REPOSITORY_ROOT)}")


if __name__ == "__main__":
    main()
