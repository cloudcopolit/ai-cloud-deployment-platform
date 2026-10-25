import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import NotFound, handle_cloudpilot_error


def _base_env(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://cloudpilot:cloudpilot@localhost:5432/cloudpilot"
    )
    monkeypatch.setenv("GITHUB_CLIENT_ID", "client-id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("JWT_SECRET_KEY", "a-long-enough-secret-that-is-32-chars")


def test_environment_only_accepts_supported_values(monkeypatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")

    settings = Settings()

    assert settings.environment == "production"

    monkeypatch.setenv("ENVIRONMENT", "qa")
    with pytest.raises(ValidationError):
        Settings()


def test_jwt_secret_requires_minimum_length(monkeypatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET_KEY", "too-short")

    with pytest.raises(ValidationError, match="at least 32"):
        Settings()


def test_domain_errors_return_the_standard_error_envelope() -> None:
    app = FastAPI()

    @app.get("/missing")
    def missing() -> None:
        raise NotFound("The object was not found.")

    app.add_exception_handler(NotFound, handle_cloudpilot_error)

    with TestClient(app) as client:
        response = client.get("/missing")

    assert response.status_code == 404
    body = response.json()
    assert set(body["error"]) == {"code", "message", "correlation_id", "details"}
    assert body["error"]["code"] == "NOT_FOUND"
