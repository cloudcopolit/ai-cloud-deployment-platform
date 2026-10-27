import uuid

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.middleware import OriginSecurityMiddleware
from app.core.security import ACCESS_COOKIE, create_access_token
from app.db.session import get_db
from app.models import User
from app.modules.auth.dependencies import get_current_user


class FakeDB:
    def __init__(self, user: User | None = None):
        self._user = user

    def get(self, model, obj_id):
        if model is User and self._user and self._user.id == obj_id:
            return self._user
        return None


def _base_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(OriginSecurityMiddleware)

    @app.post("/unsafe")
    def unsafe() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/safe")
    def safe() -> dict[str, str]:
        return {"status": "ok"}

    return app


def _protected_app(fake_db: FakeDB) -> FastAPI:
    app = _base_app()
    app.dependency_overrides[get_db] = lambda: fake_db

    @app.post("/protected")
    def protected(user: User = Depends(get_current_user)) -> dict[str, str]:  # noqa: B008
        return {"status": "ok", "user_id": str(user.id)}

    return app


def test_valid_frontend_origin_is_allowed() -> None:
    with TestClient(_base_app()) as client:
        response = client.post(
            "/unsafe",
            headers={"Origin": settings.frontend_url},
        )

    assert response.status_code == 200


def test_missing_origin_without_referer_is_rejected() -> None:
    with TestClient(_base_app()) as client:
        response = client.post("/unsafe")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INVALID_ORIGIN"


def test_missing_origin_with_valid_referer_is_allowed() -> None:
    with TestClient(_base_app()) as client:
        response = client.post(
            "/unsafe",
            headers={"Referer": f"{settings.frontend_url}/dashboard"},
        )

    assert response.status_code == 200


def test_invalid_referer_is_rejected() -> None:
    with TestClient(_base_app()) as client:
        response = client.post(
            "/unsafe",
            headers={"Referer": "https://evil.example/checkout"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INVALID_ORIGIN"


def test_invalid_origin_is_rejected() -> None:
    with TestClient(_base_app()) as client:
        response = client.post(
            "/unsafe",
            headers={"Origin": "https://evil.example"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INVALID_ORIGIN"


def test_invalid_bearer_token_does_not_bypass_origin_checks() -> None:
    with TestClient(_base_app()) as client:
        response = client.post(
            "/unsafe",
            headers={
                "Authorization": "Bearer not-a-valid-jwt",
                "Referer": f"{settings.frontend_url}/dashboard",
            },
        )

    assert response.status_code == 200


def test_cookie_authenticated_state_change_uses_valid_referer() -> None:
    with TestClient(_base_app()) as client:
        client.cookies.set(ACCESS_COOKIE, create_access_token(uuid.uuid4()))
        response = client.post(
            "/unsafe",
            headers={"Referer": f"{settings.frontend_url}/dashboard"},
        )

    assert response.status_code == 200


def test_referer_exact_origin_comparison_rejects_different_port() -> None:
    with TestClient(_base_app()) as client:
        response = client.post(
            "/unsafe",
            headers={"Referer": "http://localhost:3001/dashboard"},
        )

    assert response.status_code == 403


def test_security_headers_are_present() -> None:
    with TestClient(_base_app()) as client:
        response = client.get("/safe")

    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cache-Control"] == "no-store"


def test_invalid_bearer_token_is_rejected_by_protected_route() -> None:
    with TestClient(_protected_app(FakeDB())) as client:
        response = client.post(
            "/protected",
            headers={
                "Authorization": "Bearer not-a-valid-jwt",
                "Referer": f"{settings.frontend_url}/dashboard",
            },
        )

    assert response.status_code == 401


def test_valid_bearer_token_is_accepted_for_protected_route() -> None:
    user = User(github_user_id="101", name="Alice", email="alice@example.com")
    user.id = uuid.uuid4()

    with TestClient(_protected_app(FakeDB(user))) as client:
        response = client.post(
            "/protected",
            headers={
                "Authorization": f"Bearer {create_access_token(user.id)}",
                "Referer": f"{settings.frontend_url}/dashboard",
            },
        )

    assert response.status_code == 200
    assert response.json()["user_id"] == str(user.id)


def test_cookie_authenticated_protected_route_accepts_valid_referer() -> None:
    user = User(github_user_id="101", name="Alice", email="alice@example.com")
    user.id = uuid.uuid4()

    with TestClient(_protected_app(FakeDB(user))) as client:
        client.cookies.set(ACCESS_COOKIE, create_access_token(user.id))
        response = client.post(
            "/protected",
            headers={"Referer": f"{settings.frontend_url}/dashboard"},
        )

    assert response.status_code == 200
    assert response.json()["user_id"] == str(user.id)
