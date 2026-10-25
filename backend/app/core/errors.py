from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class CloudPilotError(Exception):
    status_code = 500
    code = "INTERNAL_SERVER_ERROR"

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | list[Any] | None = None,
    ) -> None:
        self.message = message
        self.details = details or {}


class BadRequest(CloudPilotError):
    status_code = 400
    code = "BAD_REQUEST"


class NotFound(CloudPilotError):
    status_code = 404
    code = "NOT_FOUND"


class Forbidden(CloudPilotError):
    status_code = 403
    code = "FORBIDDEN"


class Conflict(CloudPilotError):
    status_code = 409
    code = "CONFLICT"


class QuotaExceeded(CloudPilotError):
    status_code = 403
    code = "PLAN_LIMIT_REACHED"


class UpstreamError(CloudPilotError):
    status_code = 502
    code = "UPSTREAM_ERROR"


class ServiceUnavailable(CloudPilotError):
    status_code = 503
    code = "SERVICE_UNAVAILABLE"


class RepositoryNotFound(CloudPilotError):
    status_code = 404
    code = "REPOSITORY_NOT_FOUND"


class GitHubUnauthorized(CloudPilotError):
    status_code = 401
    code = "GITHUB_UNAUTHORIZED"


class GitHubRateLimited(CloudPilotError):
    status_code = 429
    code = "GITHUB_RATE_LIMITED"


class RepositoryTooLarge(CloudPilotError):
    status_code = 413
    code = "REPOSITORY_TOO_LARGE"


class LLMTimeout(CloudPilotError):
    status_code = 504
    code = "LLM_TIMEOUT"


class LLMUnavailable(CloudPilotError):
    status_code = 503
    code = "LLM_UNAVAILABLE"


class LLMRateLimited(CloudPilotError):
    status_code = 429
    code = "LLM_RATE_LIMITED"


class LLMAuthFailed(CloudPilotError):
    status_code = 401
    code = "LLM_AUTH_FAILED"


class LLMInvalidOutput(CloudPilotError):
    status_code = 502
    code = "LLM_INVALID_OUTPUT"


class LLMContextTooLong(CloudPilotError):
    status_code = 400
    code = "LLM_CONTEXT_TOO_LONG"


def _http_error_code(status_code: int) -> str:
    if status_code == 400:
        return "VALIDATION_ERROR"
    if status_code == 401:
        return "UNAUTHENTICATED"
    if status_code == 403:
        return "FORBIDDEN"
    if status_code == 404:
        return "NOT_FOUND"
    if status_code == 409:
        return "CONFLICT"
    if status_code == 422:
        return "VALIDATION_ERROR"
    if status_code == 429:
        return "RATE_LIMITED"
    if status_code in {502, 504}:
        return "UPSTREAM_ERROR"
    return "INTERNAL_SERVER_ERROR"


def _error_payload(
    *,
    code: str,
    message: str,
    details: dict[str, Any] | list[Any] | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "correlation_id": correlation_id or uuid.uuid4().hex,
            "details": details or {},
        }
    }


def _correlation_id(request: Request) -> str:
    request_id = getattr(request.state, "correlation_id", None)
    if request_id:
        return request_id
    header_id = request.headers.get("X-Request-ID")
    if header_id:
        return header_id
    return uuid.uuid4().hex


async def handle_cloudpilot_error(request: Request, exc: Exception) -> JSONResponse:
    app_error = exc if isinstance(exc, CloudPilotError) else CloudPilotError(str(exc))
    return JSONResponse(
        status_code=app_error.status_code,
        content=_error_payload(
            code=app_error.code,
            message=app_error.message,
            details=app_error.details,
            correlation_id=_correlation_id(request),
        ),
    )


async def handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    http_exc = exc if isinstance(exc, StarletteHTTPException) else StarletteHTTPException(500)
    detail = http_exc.detail
    if isinstance(detail, dict):
        message = detail.get("message") or detail.get("error") or "Request failed"
        payload_details: dict[str, Any] | list[Any] = detail
    elif isinstance(detail, list):
        message = "Request failed"
        payload_details = detail
    else:
        message = str(detail)
        payload_details = {}

    return JSONResponse(
        status_code=http_exc.status_code,
        content=_error_payload(
            code=_http_error_code(http_exc.status_code),
            message=message,
            details=payload_details,
            correlation_id=_correlation_id(request),
        ),
        headers=dict(http_exc.headers or {}),
    )


async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    validation_error = (
        exc if isinstance(exc, RequestValidationError) else RequestValidationError([])
    )
    return JSONResponse(
        status_code=422,
        content=_error_payload(
            code="VALIDATION_ERROR",
            message="Validation failed",
            details={"errors": jsonable_encoder(validation_error.errors())},
            correlation_id=_correlation_id(request),
        ),
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=_error_payload(
            code="INTERNAL_SERVER_ERROR",
            message="Internal server error",
            details={},
            correlation_id=_correlation_id(request),
        ),
    )
