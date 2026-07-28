"""Export the backend OpenAPI document used to generate frontend API types."""

from __future__ import annotations

import json
from pathlib import Path

from qfusion.config.settings import Settings
from qfusion.main import create_app

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPOSITORY_ROOT / "packages" / "contracts" / "openapi.json"


def main() -> None:
    """Write a deterministic, UTF-8 OpenAPI contract."""
    application = create_app(Settings(_env_file=None, environment="test"))
    output = json.dumps(
        application.openapi(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(f"{output}\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(REPOSITORY_ROOT)}")


if __name__ == "__main__":
    main()
