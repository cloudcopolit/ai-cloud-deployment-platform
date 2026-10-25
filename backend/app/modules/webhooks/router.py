import json
from typing import Annotated

from fastapi import APIRouter, Header, Request, Response, status
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.dependencies import DbSession
from app.core.errors import BadRequest, NotFound, Unauthorized
from app.integrations.github_app import verify_webhook_signature
from app.modules.webhooks import service

router = APIRouter(tags=["webhooks"])

MAX_BODY_BYTES = 1_000_000  # GitHub caps payloads at 25 MB; pushes we use are far smaller


@router.post("/webhooks/github", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    db: DbSession,
    x_github_event: Annotated[str | None, Header()] = None,
    x_hub_signature_256: Annotated[str | None, Header()] = None,
) -> Response:
    """Authenticated by HMAC signature, not by cookie (exempt from the Origin check)."""
    secret = settings.github_webhook_secret
    if not secret:
        raise NotFound("Not found.")  # disabled until GITHUB_WEBHOOK_SECRET is configured
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise BadRequest("Webhook payload too large.")
    if not verify_webhook_signature(secret, body, x_hub_signature_256):
        raise Unauthorized("Invalid webhook signature.")
    if x_github_event == "ping":
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    if x_github_event != "push":
        return Response(status_code=status.HTTP_202_ACCEPTED)
    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise BadRequest("Webhook payload is not JSON.") from exc
    if not isinstance(payload, dict):
        raise BadRequest("Webhook payload is not a JSON object.")
    await run_in_threadpool(service.handle_push, db, payload)
    return Response(status_code=status.HTTP_202_ACCEPTED)
