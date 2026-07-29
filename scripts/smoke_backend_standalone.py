"""Smoke-test the generated QFusion backend on an owned dynamic loopback port."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BUILD_MANIFEST = REPOSITORY_ROOT / "dist" / "backend" / "build-manifest.json"
SMOKE_ROOT = REPOSITORY_ROOT / ".tmp" / "backend-standalone-smoke"
EXPECTED_HEALTH = {
    "status": "ok",
    "service": "QFusion Backend",
    "version": "0.1.0",
    "api_version": "v1",
    "execution_mode": "research",
    "data_mode": "synthetic-m0",
    "llm_mode": "off",
}


class _RejectRedirects(HTTPRedirectHandler):
    """Prevent the smoke request from leaving its recorded loopback endpoint."""

    def redirect_request(
        self,
        request: Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        del request, file_pointer, code, message, headers, new_url
        return None


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256(filename: Path) -> str:
    digest = hashlib.sha256()
    with filename.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_relative_path(value: object, label: str) -> Path:
    if not isinstance(value, str):
        raise RuntimeError(f"Backend build manifest {label} must be a string.")
    relative_path = Path(value)
    if (
        relative_path.is_absolute()
        or not relative_path.parts
        or ".." in relative_path.parts
    ):
        raise RuntimeError(f"Backend build manifest contains an unsafe {label}.")
    return relative_path


def _load_migration_assets(
    manifest_value: dict[Any, Any],
    executable: Path,
) -> tuple[str, ...]:
    migration_value = manifest_value.get("migration_assets")
    if not isinstance(migration_value, dict):
        raise RuntimeError("Backend build manifest is missing migration assets.")

    relative_directory = _manifest_relative_path(
        migration_value.get("directory"),
        "migration directory",
    )
    unresolved_directory = REPOSITORY_ROOT / relative_directory
    if unresolved_directory.is_symlink():
        raise RuntimeError("Backend migration directory must not be a symlink.")
    migration_directory = unresolved_directory.resolve(strict=True)
    output_root = (REPOSITORY_ROOT / "dist" / "backend").resolve()
    if (
        not migration_directory.is_relative_to(output_root)
        or migration_directory.parent != executable.parent
        or migration_directory.name != "qfusion_migrations"
    ):
        raise RuntimeError("Backend migration directory is outside the standalone artifact.")

    heads_value = migration_value.get("heads")
    if (
        not isinstance(heads_value, list)
        or len(heads_value) != 1
        or not all(isinstance(head, str) and head for head in heads_value)
    ):
        raise RuntimeError("Backend build manifest must declare exactly one migration head.")
    expected_heads = tuple(heads_value)

    files_value = migration_value.get("files")
    if not isinstance(files_value, list) or not files_value:
        raise RuntimeError("Backend build manifest contains no migration files.")

    expected_files: set[str] = set()
    for entry in files_value:
        if not isinstance(entry, dict):
            raise RuntimeError("Backend migration file records must be objects.")
        relative_file = _manifest_relative_path(
            entry.get("path"),
            "migration file path",
        )
        expected_sha256 = entry.get("sha256")
        if not isinstance(expected_sha256, str):
            raise RuntimeError("Backend migration file record is missing SHA-256.")

        unresolved_file = migration_directory / relative_file
        if unresolved_file.is_symlink():
            raise RuntimeError("Backend migration assets must not be symlinks.")
        migration_file = unresolved_file.resolve(strict=True)
        if not migration_file.is_relative_to(migration_directory) or not migration_file.is_file():
            raise RuntimeError("Backend migration asset escaped its packaged directory.")
        if _sha256(migration_file) != expected_sha256:
            raise RuntimeError(
                f"Backend migration asset SHA-256 mismatch: {relative_file.as_posix()}"
            )
        expected_files.add(relative_file.as_posix())

    actual_files = {
        path.relative_to(migration_directory).as_posix()
        for path in migration_directory.rglob("*")
        if path.is_file()
    }
    if actual_files != expected_files:
        raise RuntimeError("Backend migration asset inventory does not match the build manifest.")
    return expected_heads


def _load_executable() -> tuple[Path, str, tuple[str, ...]]:
    manifest_value = json.loads(BUILD_MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(manifest_value, dict):
        raise RuntimeError("Backend build manifest must be a JSON object.")
    if manifest_value.get("schema_version") != 2:
        raise RuntimeError("Backend build manifest schema is not supported.")

    relative_executable = manifest_value.get("executable")
    expected_sha256 = manifest_value.get("sha256")
    manifest_path = _manifest_relative_path(relative_executable, "executable path")
    if not isinstance(expected_sha256, str):
        raise RuntimeError("Backend build manifest is missing executable SHA-256.")

    executable = (REPOSITORY_ROOT / manifest_path).resolve(strict=True)
    output_root = (REPOSITORY_ROOT / "dist" / "backend").resolve()
    if not executable.is_relative_to(output_root) or not executable.is_file():
        raise RuntimeError("Backend executable is outside the generated artifact directory.")
    if _sha256(executable) != expected_sha256:
        raise RuntimeError("Backend executable SHA-256 does not match the build manifest.")

    migration_heads = _load_migration_assets(manifest_value, executable)
    return executable, expected_sha256, migration_heads


def _verify_migration_assets(
    executable: Path,
    expected_heads: tuple[str, ...],
    environment: dict[str, str],
) -> None:
    arguments = [str(executable), "--verify-migration-assets"]
    completed = subprocess.run(  # noqa: S603
        arguments,
        cwd=executable.parent,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=30.0,
        check=False,
    )
    expected_output = (
        f"QFUSION_MIGRATION_ASSETS_OK heads={','.join(expected_heads)}\n"
    ).encode()
    if completed.returncode != 0 or completed.stdout != expected_output:
        stdout = completed.stdout.decode("utf-8", errors="replace")
        stderr = completed.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(
            "Standalone migration asset verification failed: "
            f"exit={completed.returncode} stdout={stdout!r} stderr={stderr!r}"
        )


def _allocate_dynamic_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        address = reservation.getsockname()
    port = address[1]
    if not isinstance(port, int) or not 1024 <= port <= 65535:
        raise RuntimeError("The operating system did not allocate a usable loopback port.")
    return port


def _write_journal(path: Path, journal: dict[str, object]) -> None:
    path.write_text(
        json.dumps(journal, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _tail_log(path: Path) -> str:
    if not path.is_file():
        return "<no process log>"
    return path.read_text(encoding="utf-8", errors="replace")[-8000:]


def _wait_for_health(
    process: subprocess.Popen[bytes],
    health_url: str,
    log_path: Path,
) -> dict[str, object]:
    opener = build_opener(_RejectRedirects())
    request = Request(health_url, headers={"Accept": "application/json"})  # noqa: S310
    deadline = time.monotonic() + 90.0
    last_error = "service has not accepted a connection"

    while time.monotonic() < deadline:
        exit_code = process.poll()
        if exit_code is not None:
            raise RuntimeError(
                f"Standalone backend exited before readiness with code {exit_code}.\n"
                f"{_tail_log(log_path)}"
            )

        try:
            with opener.open(request, timeout=2.0) as response:
                if response.geturl() != health_url:
                    raise RuntimeError("Standalone health request was redirected.")
                if response.status != 200:
                    last_error = f"health endpoint returned HTTP {response.status}"
                else:
                    payload = json.loads(response.read().decode("utf-8"))
                    if payload != EXPECTED_HEALTH:
                        raise RuntimeError(
                            "Standalone health payload did not match the M0 contract: "
                            f"{payload!r}"
                        )
                    return payload
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = str(error)
        time.sleep(0.2)

    raise RuntimeError(
        "Timed out waiting for the owned standalone backend "
        f"({last_error}).\n{_tail_log(log_path)}"
    )


def _stop_owned_process(
    process: subprocess.Popen[bytes],
    recorded_pid: int,
    expected_arguments: list[str],
) -> None:
    if process.poll() is not None:
        return
    if process.pid != recorded_pid or process.args != expected_arguments:
        raise RuntimeError("Refusing to stop a process whose held identity changed.")

    process.terminate()
    try:
        process.wait(timeout=10.0)
    except subprocess.TimeoutExpired as error:
        if process.pid != recorded_pid or process.args != expected_arguments:
            raise RuntimeError(
                "Refusing to force-stop a process whose held identity changed."
            ) from error
        process.kill()
        process.wait(timeout=10.0)


def main() -> None:
    """Verify migration assets, then start and stop the exact owned backend process."""

    executable, executable_sha256, migration_heads = _load_executable()
    environment = os.environ.copy()
    environment.update(
        {
            "QFUSION_ENVIRONMENT": "test",
            "QFUSION_HOST": "127.0.0.1",
            "QFUSION_LLM_MODE": "off",
            "QFUSION_LOG_LEVEL": "warning",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    _verify_migration_assets(executable, migration_heads, environment)

    port = _allocate_dynamic_port()
    environment["QFUSION_PORT"] = str(port)
    health_url = f"http://127.0.0.1:{port}/api/v1/health"
    run_directory = SMOKE_ROOT / uuid4().hex
    run_directory.mkdir(parents=True)
    log_path = run_directory / "backend.log"
    journal_path = run_directory / "journal.json"

    arguments = [str(executable)]
    process: subprocess.Popen[bytes] | None = None
    recorded_pid: int | None = None
    journal: dict[str, object] = {
        "schema_version": 2,
        "status": "starting",
        "purpose": "QFusion Windows standalone migration and health smoke",
        "started_at": _utc_now(),
        "cwd": str(executable.parent),
        "executable": str(executable),
        "executable_sha256": executable_sha256,
        "migration_heads": list(migration_heads),
        "migration_assets_verified_at": _utc_now(),
        "port": port,
        "health_url": health_url,
    }

    with log_path.open("wb") as process_log:
        try:
            process = subprocess.Popen(  # noqa: S603
                arguments,
                cwd=executable.parent,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=process_log,
                stderr=subprocess.STDOUT,
            )
            recorded_pid = process.pid
            journal["pid"] = recorded_pid
            _write_journal(journal_path, journal)
            print(
                "QFusion standalone smoke started: "
                f"pid={recorded_pid} port={port} cwd={executable.parent} "
                f"started_at={journal['started_at']}"
            )

            payload = _wait_for_health(process, health_url, log_path)
            journal["status"] = "health_verified"
            journal["health"] = payload
            journal["health_verified_at"] = _utc_now()
            _write_journal(journal_path, journal)
        except BaseException as error:
            journal["status"] = "failed"
            journal["error_type"] = type(error).__name__
            journal["failed_at"] = _utc_now()
            _write_journal(journal_path, journal)
            raise
        finally:
            if process is not None and recorded_pid is not None:
                _stop_owned_process(process, recorded_pid, arguments)
                journal["stopped_at"] = _utc_now()
                journal["exit_code_after_stop"] = process.returncode
                if journal["status"] == "health_verified":
                    journal["status"] = "passed"
                _write_journal(journal_path, journal)

    print(
        "QFUSION_STANDALONE_SMOKE_OK "
        f"pid={journal['pid']} port={port} sha256={executable_sha256} "
        f"migration_heads={','.join(migration_heads)}"
    )


if __name__ == "__main__":
    main()
