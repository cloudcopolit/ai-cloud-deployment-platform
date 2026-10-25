from __future__ import annotations

from urllib.parse import urlsplit

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.security import decode_access_token

CSRF_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _origin_from_url(candidate: str | None) -> str | None:
    if not candidate:
        return None
    parsed = urlsplit(candidate)
    if not parsed.scheme or not parsed.hostname:
        return None
    host = parsed.hostname.lower()
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    return f"{parsed.scheme.lower()}://{host}"


def _valid_bearer_token(raw_value: str | None) -> bool:
    if not raw_value or not raw_value.lower().startswith("bearer "):
        return False
    token = raw_value.split(None, 1)[1].strip()
    if not token:
        return False
    try:
        decode_access_token(token)
    except (TypeError, ValueError, jwt.PyJWTError):
        return False
    return True


def _is_allowed_reference(candidate: str | None, allowed: str) -> bool:
    return _origin_from_url(candidate) == _origin_from_url(allowed)


def _apply_security_headers(response):
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Permissions-Policy",
        "geolocation=(), microphone=(), camera=()",
    )
    response.headers.setdefault("Cache-Control", "no-store")
    return response


class OriginSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in CSRF_METHODS:
            if _valid_bearer_token(request.headers.get("Authorization")):
                response = await call_next(request)
                return _apply_security_headers(response)

            origin = request.headers.get("Origin")
            referer = request.headers.get("Referer")
            allowed_origin = _origin_from_url(settings.frontend_url)

            if origin is not None:
                if _origin_from_url(origin) != allowed_origin:
                    response = JSONResponse(
                        status_code=403,
                        content={
                            "error": {
                                "code": "INVALID_ORIGIN",
                                "message": "Origin is not allowed for this request.",
                                "details": {"origin": origin},
                            }
                        },
                    )
                    return _apply_security_headers(response)
            elif not _is_allowed_reference(referer, allowed_origin or settings.frontend_url):
                response = JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "code": "INVALID_ORIGIN",
                            "message": "Origin or Referer is required for state-changing requests.",
                            "details": {"origin": origin, "referer": referer},
                        }
                    },
                )
                return _apply_security_headers(response)

        response = await call_next(request)
        return _apply_security_headers(response)
