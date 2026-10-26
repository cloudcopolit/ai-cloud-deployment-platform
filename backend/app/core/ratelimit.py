"""Rate limits in PostgreSQL (ADR-031): fixed-window counters, no Redis.

- Every mutating request is counted per client IP (middleware).
- Expensive actions are also counted per team (`limit_team`, called from the services).
The client IP comes from X-Forwarded-For only when the direct peer is a trusted proxy.
"""

from __future__ import annotations

import ipaddress
import math
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.errors import RateLimited

MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})
EXEMPT_PATHS = ("/webhooks/github",)  # signed by GitHub; abuse is rejected by HMAC first

# per team, (limit, window seconds)
TEAM_LIMITS: dict[str, tuple[int, int]] = {
    "analysis": (30, 3600),
    "architecture": (30, 3600),
    "aws_verify": (10, 600),
    "deploy_plan": (10, 3600),
    "deploy_approve": (20, 3600),
    "deploy_apply": (10, 3600),
    "deploy_destroy": (10, 3600),
}


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    trusted = {p.strip() for p in settings.trusted_proxies.split(",") if p.strip()}
    if peer in trusted:
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        try:
            ipaddress.ip_address(first)
            return first
        except ValueError:
            pass
    return peer


def hit(db: Session, key: str, limit: int, window_s: int, *, now: datetime | None = None) -> None:
    """Count one event; raise RateLimited once the window's limit is exceeded."""
    now = now or datetime.now(UTC)
    start_epoch = math.floor(now.timestamp() / window_s) * window_s
    window_start = datetime.fromtimestamp(start_epoch, UTC)
    count = db.execute(
        text(
            "INSERT INTO rate_limit_buckets (key, window_start, count) VALUES (:k, :w, 1) "
            "ON CONFLICT (key, window_start) DO UPDATE SET count = rate_limit_buckets.count + 1 "
            "RETURNING count"
        ),
        {"k": key[:200], "w": window_start},
    ).scalar_one()
    if count > limit:
        retry_after = max(1, int(start_epoch + window_s - now.timestamp()))
        raise RateLimited(
            f"Too many requests; try again in {retry_after} s.",
            details={"limit": limit, "window_s": window_s},
            retry_after=retry_after,
        )


def limit_team(db: Session, team_id: object, action: str) -> None:
    if not settings.rate_limit_enabled:
        return
    limit, window = TEAM_LIMITS[action]
    hit(db, f"team:{team_id}:{action}", limit, window)
    db.commit()


class IpRateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP budget for every mutating request."""

    def __init__(self, app: object, session_factory: Callable[[], Session]) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._session_factory = session_factory

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if (
            settings.rate_limit_enabled
            and request.method in MUTATING
            and not request.url.path.startswith(EXEMPT_PATHS)
        ):
            db = self._session_factory()
            try:
                hit(db, f"ip:{client_ip(request)}", settings.rate_limit_ip_per_minute, 60)
                db.commit()
            except RateLimited as exc:
                db.rollback()
                from app.core.errors import handle_cloudpilot_error

                return await handle_cloudpilot_error(request, exc)
            finally:
                db.close()
        return await call_next(request)
