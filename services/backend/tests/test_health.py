"""M0 health endpoint contract tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import ValidationError
from pytest import raises

from qfusion.config.settings import Settings
from qfusion.main import create_app


def make_client() -> TestClient:
    """Create an isolated application without reading developer environment files."""
    settings = Settings(
        _env_file=None,
        environment="test",
        llm_mode="off",
    )
    return TestClient(create_app(settings))


def test_health_contract() -> None:
    with make_client() as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "QFusion Backend",
        "version": "0.1.0",
        "api_version": "v1",
        "execution_mode": "research",
        "data_mode": "synthetic-m0",
        "llm_mode": "off",
    }


def test_health_allows_only_declared_dev_origin() -> None:
    with make_client() as client:
        allowed = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://127.0.0.1:1420",
                "Access-Control-Request-Method": "GET",
            },
        )
        denied = client.options(
            "/api/v1/health",
            headers={
                "Origin": "https://example.invalid",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:1420"
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


def test_backend_cannot_bind_public_interfaces() -> None:
    with raises(ValidationError):
        Settings(_env_file=None, host="0.0.0.0")  # type: ignore[arg-type]


def test_openapi_exposes_no_order_submission_path() -> None:
    schema = create_app(Settings(_env_file=None, environment="test")).openapi()
    paths = set(schema["paths"])

    assert paths == {"/api/v1/health"}
    assert all("order" not in path.lower() for path in paths)
