import secrets

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.core.dependencies import DbSession
from app.core.security import ACCESS_COOKIE, create_access_token
from app.integrations import github
from app.modules.auth import service
from app.modules.auth.dependencies import CurrentUser
from app.modules.auth.schemas import DevLoginRequest, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

STATE_COOKIE = "oauth_state"


def _cookie_secure() -> bool:
    return settings.environment != "development"


@router.get("/github/login")
def github_login():
    state = secrets.token_urlsafe(32)
    response = RedirectResponse(github.build_authorize_url(state))
    response.set_cookie(
        STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=settings.environment != "development",
    )
    return response


@router.get("/github/callback")
def github_callback(
    request: Request,
    db: DbSession,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    login_failed = RedirectResponse(f"{settings.frontend_url}/login?error=github_failed")

    cookie_state = request.cookies.get(STATE_COOKIE)
    if (
        error
        or not code
        or not state
        or not cookie_state
        or not secrets.compare_digest(state, cookie_state)
    ):
        return login_failed

    try:
        github_token = github.exchange_code_for_token(code)
        profile = github.fetch_profile(github_token)
    except (httpx.HTTPError, github.GitHubError):
        return login_failed

    user = service.upsert_github_user(db, profile)

    response = RedirectResponse(f"{settings.frontend_url}/dashboard", status_code=302)
    response.delete_cookie(STATE_COOKIE)
    response.set_cookie(
        ACCESS_COOKIE,
        create_access_token(user.id),
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,  # JavaScript cannot read it
        samesite="lax",  # not sent on cross-site POST requests (CSRF protection)
        secure=_cookie_secure(),  # HTTPS only outside development
        path="/",
    )
    return response


@router.get("/me", response_model=UserRead)
def read_me(user: CurrentUser):
    return user


@router.post("/dev-login", response_model=TokenResponse)
def dev_login(body: DevLoginRequest, db: DbSession):
    """Development only: sign in as a seeded user without GitHub."""
    if settings.environment != "development":
        raise HTTPException(status_code=404)
    user = service.get_user_by_github_id(db, body.github_user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(ACCESS_COOKIE, path="/")
