"""Project-local pnpm Store boundary tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest import CaptureFixture, MonkeyPatch
from scripts import check_pnpm_isolation

EXPECTED_STORE_RELATIVE_PATH = Path(".cache") / "pnpm" / "store" / "v10"


def write_metadata(repository_root: Path, content: str) -> Path:
    """Create synthetic pnpm metadata inside the pytest workspace."""
    metadata_path = repository_root / "node_modules" / ".modules.yaml"
    metadata_path.parent.mkdir(parents=True)
    metadata_path.write_text(content, encoding="utf-8")
    return metadata_path


def run_check(repository_root: Path) -> int:
    """Run the checker against an injected repository boundary."""
    return check_pnpm_isolation.main(
        modules_metadata_path=repository_root / "node_modules" / ".modules.yaml",
        repository_root=repository_root,
        expected_store_root=repository_root / ".cache" / "pnpm" / "store",
    )


def assert_blocked(capsys: CaptureFixture[str]) -> None:
    """Assert the checker emitted the mandatory non-sensitive marker."""
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "BLOCKED_BY_HOST_ISOLATION" in captured.err


def test_allows_missing_modules_tree(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    repository_root = tmp_path / "repository"
    repository_root.mkdir()

    assert run_check(repository_root) == 0
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("use_absolute_path", [False, True])
def test_allows_exact_versioned_project_store(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    use_absolute_path: bool,
) -> None:
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    store_path = repository_root / EXPECTED_STORE_RELATIVE_PATH
    recorded_path = store_path if use_absolute_path else EXPECTED_STORE_RELATIVE_PATH
    write_metadata(repository_root, f"storeDir: {recorded_path}\n")

    assert run_check(repository_root) == 0
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    "recorded_path",
    [
        ".cache/pnpm/store",
        ".cache/pnpm/store/v9",
        ".cache/pnpm/store/v11",
        "../shared-store/v10",
        ".cache/pnpm/store/v10/../../outside",
    ],
)
def test_rejects_wrong_or_traversing_store_path(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    recorded_path: str,
) -> None:
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    write_metadata(repository_root, f"storeDir: {recorded_path}\n")

    assert run_check(repository_root) == 1
    assert_blocked(capsys)


def test_rejects_absolute_store_outside_repository(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    outside_store = tmp_path / "other-project" / "store" / "v10"
    write_metadata(repository_root, f"storeDir: {outside_store}\n")

    assert run_check(repository_root) == 1
    assert_blocked(capsys)


@pytest.mark.parametrize(
    "metadata",
    [
        "layoutVersion: 5\n",
        "storeDir:\n",
        "storeDir: .cache/pnpm/store/v10\nstoreDir: .cache/pnpm/store/v10\n",
    ],
)
def test_rejects_missing_empty_or_duplicate_store_entry(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    metadata: str,
) -> None:
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    write_metadata(repository_root, metadata)

    assert run_check(repository_root) == 1
    assert_blocked(capsys)


def test_rejects_symlinked_store_component(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    monkeypatch: MonkeyPatch,
) -> None:
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    write_metadata(repository_root, f"storeDir: {EXPECTED_STORE_RELATIVE_PATH}\n")
    simulated_symlink = repository_root / ".cache" / "pnpm" / "store"
    original_is_symlink = Path.is_symlink

    def fake_is_symlink(path: Path) -> bool:
        if check_pnpm_isolation.normalized_path(path) == (
            check_pnpm_isolation.normalized_path(simulated_symlink)
        ):
            return True
        return original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)

    assert run_check(repository_root) == 1
    assert_blocked(capsys)


def test_rejects_symlinked_modules_metadata_path(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    monkeypatch: MonkeyPatch,
) -> None:
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    write_metadata(repository_root, f"storeDir: {EXPECTED_STORE_RELATIVE_PATH}\n")
    simulated_symlink = repository_root / "node_modules"
    original_is_symlink = Path.is_symlink

    def fake_is_symlink(path: Path) -> bool:
        if check_pnpm_isolation.normalized_path(path) == (
            check_pnpm_isolation.normalized_path(simulated_symlink)
        ):
            return True
        return original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)

    assert run_check(repository_root) == 1
    assert_blocked(capsys)
