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


def _load_executable() -> tuple[Path, str]:
    manifest_value = json.loads(BUILD_MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(manifest_value, dict):
        raise RuntimeError("Backend build manifest must be a JSON object.")

    relative_executable = manifest_value.get("executable")
    expected_sha256 = manifest_value.get("sha256")
    if not isinstance(relative_executable, str) or not isinstance(expected_sha256, str):
        raise RuntimeError("Backend build manifest is missing executable or SHA-256 fields.")

    manifest_path = Path(relative_executable)
    if manifest_path.is_absolute() or ".." in manifest_path.parts:
        raise RuntimeError("Backend build manifest contains an unsafe executable path.")

    executable = (REPOSITORY_ROOT / manifest_path).resolve(strict=True)
    output_root = (REPOSITORY_ROOT / "dist" / "backend").resolve()
    if not executable.is_relative_to(output_root) or not executable.is_file():
        raise RuntimeError("Backend executable is outside the generated artifact directory.")
    if _sha256(executable) != expected_sha256:
        raise RuntimeError("Backend executable SHA-256 does not match the build manifest.")
    return executable, expected_sha256


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
    request = Request(health_url, headers={"Accept": "application/json"})
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
            with opener.open(request, timeout=2.0) as response:  # noqa: S310
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
    except subprocess.TimeoutExpired:
        if process.pid != recorded_pid or process.args != expected_arguments:
            raise RuntimeError("Refusing to force-stop a process whose held identity changed.")
        process.kill()
        process.wait(timeout=10.0)


def main() -> None:
    """Start, verify, and stop the exact backend process created by this smoke test."""
    executable, executable_sha256 = _load_executable()
    port = _allocate_dynamic_port()
    health_url = f"http://127.0.0.1:{port}/api/v1/health"
    run_directory = SMOKE_ROOT / uuid4().hex
    run_directory.mkdir(parents=True)
    log_path = run_directory / "backend.log"
    journal_path = run_directory / "journal.json"

    environment = os.environ.copy()
    environment.update(
        {
            "QFUSION_ENVIRONMENT": "test",
            "QFUSION_HOST": "127.0.0.1",
            "QFUSION_LLM_MODE": "off",
            "QFUSION_LOG_LEVEL": "warning",
            "QFUSION_PORT": str(port),
        }
    )
    arguments = [str(executable)]
    process: subprocess.Popen[bytes] | None = None
    recorded_pid: int | None = None
    journal: dict[str, object] = {
        "schema_version": 1,
        "status": "starting",
        "purpose": "QFusion Windows standalone health smoke",
        "started_at": _utc_now(),
        "cwd": str(executable.parent),
        "executable": str(executable),
        "executable_sha256": executable_sha256,
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
        f"pid={journal['pid']} port={port} sha256={executable_sha256}"
    )


if __name__ == "__main__":
    main()
