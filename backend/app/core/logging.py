from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("cloudpilot")

REDACTED = "***REDACTED***"
SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api_key",
    "token",
    "secret",
    "password",
    "jwt_secret_key",
    "github_client_secret",
}


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_name = str(key).lower()
            if key_name in SENSITIVE_KEYS:
                redacted[str(key)] = REDACTED
            else:
                redacted[str(key)] = redact(item)
        return redacted
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        if "bearer " in lowered or "token=" in lowered:
            return REDACTED
        return value
    return value


def configure_logging() -> None:
    if logger.handlers:
        return

    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", None),
        }
        context = getattr(record, "context", None)
        if context is not None:
            payload["context"] = redact(context)
        return json.dumps(payload, default=str, separators=(",", ":"))


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.correlation_id = request_id
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = int((time.perf_counter() - start) * 1000)
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "request_completed",
            extra={
                "correlation_id": request_id,
                "context": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "query": redact(dict(request.query_params)),
                    "headers": redact(dict(request.headers)),
                    "client": request.client.host if request.client else None,
                },
            },
        )
        return response
