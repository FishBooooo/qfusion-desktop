"""Dependency lock isolation guard tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.check_uv_lock_update import (
    load_package_versions,
    main,
    validate_lock_update,
)


def test_lock_update_guard_accepts_only_allowlisted_additions(tmp_path: Path) -> None:
    before = tmp_path / "before.lock"
    after = tmp_path / "after.lock"
    before.write_text(
        'version = 1\n\n[[package]]\nname = "existing"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )
    after.write_text(
        (
            'version = 1\n\n'
            '[[package]]\nname = "existing"\nversion = "1.0.0"\n\n'
            '[[package]]\nname = "SQLAlchemy"\nversion = "2.0.51"\n'
        ),
        encoding="utf-8",
    )

    assert load_package_versions(before) == {"existing": ("1.0.0",)}
    assert main(
        (
            "--before",
            str(before),
            "--after",
            str(after),
            "--allow-new",
            "sqlalchemy",
        )
    ) == 0


def test_lock_update_guard_reports_removal_version_change_and_unexpected_package() -> None:
    errors = validate_lock_update(
        {
            "removed": ("1",),
            "changed": ("1",),
        },
        {
            "changed": ("2",),
            "unexpected": ("3",),
        },
        allowed_new=set(),
    )

    assert errors == [
        "existing package removed: removed ('1',)",
        "existing package version changed: changed ('1',) -> ('2',)",
        "unexpected new package: unexpected ('3',)",
    ]


def test_lock_update_guard_rejects_invalid_lock_shape(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.lock"
    invalid.write_text('version = 1\npackage = "wrong"\n', encoding="utf-8")

    with pytest.raises(TypeError, match="package list"):
        load_package_versions(invalid)
