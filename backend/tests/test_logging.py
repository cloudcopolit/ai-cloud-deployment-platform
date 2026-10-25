import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import logging as core_logging


def test_request_id_is_generated_and_returned(monkeypatch) -> None:
    app = FastAPI()
    app.add_middleware(core_logging.RequestIDMiddleware)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    class CaptureLogger:
        def __init__(self) -> None:
            self.messages: list[dict] = []

        def info(self, message: str, extra: dict | None = None) -> None:
            self.messages.append({"message": message, "extra": extra})

    capture = CaptureLogger()
    monkeypatch.setattr(core_logging, "logger", capture)

    with TestClient(app) as client:
        response = client.get("/ping", headers={"Authorization": "Bearer super-secret-token"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    assert response.headers["X-Request-ID"] == capture.messages[0]["extra"]["correlation_id"]
    assert "super-secret-token" not in json.dumps(capture.messages)
    assert "Bearer" not in json.dumps(capture.messages)


def test_redact_function_masks_sensitive_map_values() -> None:
    payload = {
        "Authorization": "Bearer secret",
        "cookie": "session=abc123",
        "nested": {"token": "should-not-log"},
        "safe": "visible",
    }

    redacted = core_logging.redact(payload)

    assert redacted["Authorization"] == "***REDACTED***"
    assert redacted["cookie"] == "***REDACTED***"
    assert redacted["nested"]["token"] == "***REDACTED***"
    assert redacted["safe"] == "visible"
