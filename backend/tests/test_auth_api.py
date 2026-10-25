"""Authentication endpoints, CORS, and the database health check."""

import uuid
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import ACCESS_COOKIE, create_access_token, decode_access_token
from app.integrations import github
from app.models import User
from app.modules.auth.router import STATE_COOKIE

FRONTEND = "http://localhost:3000"


@pytest.fixture
def user(db_session: Session) -> User:
    user = User(github_user_id="1001", name="Alice Owner", email="alice@example.com")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def fake_github_oauth(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace the GitHub HTTP calls; returns the codes that were exchanged."""
    exchanged: list[str] = []

    def exchange(code: str) -> str:
        exchanged.append(code)
        return "gho_test"

    def profile(token: str) -> github.GitHubProfile:
        assert token == "gho_test"
        return github.GitHubProfile(
            github_id="5005", name="New User", email="new@example.com", avatar_url=None
        )

    monkeypatch.setattr(github, "exchange_code_for_token", exchange)
    monkeypatch.setattr(github, "fetch_profile", profile)
    return exchanged


def test_health_check_reports_database_ok(client: TestClient) -> None:
    response = client.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"database": "ok"}


class TestCurrentUser:
    def test_requires_a_token(self, client: TestClient) -> None:
        response = client.get("/auth/me")

        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"

    def test_accepts_bearer_token(self, client: TestClient, user: User) -> None:
        response = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {create_access_token(user.id)}"}
        )

        assert response.status_code == 200
        assert response.json() == {
            "id": str(user.id),
            "github_user_id": "1001",
            "name": "Alice Owner",
            "email": "alice@example.com",
            "avatar_url": None,
        }

    def test_accepts_cookie(self, client: TestClient, user: User) -> None:
        client.cookies.set(ACCESS_COOKIE, create_access_token(user.id))

        assert client.get("/auth/me").json()["id"] == str(user.id)

    def test_rejects_invalid_token(self, client: TestClient) -> None:
        response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})

        assert response.status_code == 401

    def test_rejects_token_for_unknown_user(self, client: TestClient) -> None:
        token = create_access_token(uuid.uuid4())

        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 401


class TestDevLogin:
    def test_issues_token_for_seeded_user(self, client: TestClient, user: User) -> None:
        response = client.post(
            "/auth/dev-login", json={"github_user_id": "1001"}, headers={"Origin": FRONTEND}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert decode_access_token(body["access_token"]) == user.id

    def test_sets_the_same_httponly_cookie_as_github_sign_in(
        self, client: TestClient, user: User
    ) -> None:
        response = client.post(
            "/auth/dev-login", json={"github_user_id": "1001"}, headers={"Origin": FRONTEND}
        )

        cookie = response.headers["set-cookie"]
        assert cookie.startswith(f"{ACCESS_COOKIE}=")
        assert "HttpOnly" in cookie
        assert "samesite=lax" in cookie.lower()
        assert decode_access_token(response.cookies[ACCESS_COOKIE]) == user.id

    def test_unknown_user_is_not_found(self, client: TestClient) -> None:
        response = client.post(
            "/auth/dev-login", json={"github_user_id": "missing"}, headers={"Origin": FRONTEND}
        )

        assert response.status_code == 404

    def test_is_disabled_outside_development(
        self, client: TestClient, user: User, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "environment", "production")

        response = client.post(
            "/auth/dev-login", json={"github_user_id": "1001"}, headers={"Origin": FRONTEND}
        )

        assert response.status_code == 404


def test_logout_clears_the_access_cookie(client: TestClient) -> None:
    response = client.post("/auth/logout", headers={"Origin": FRONTEND})

    assert response.status_code == 204
    set_cookie = response.headers["set-cookie"]
    assert set_cookie.startswith(f"{ACCESS_COOKIE}=")
    assert "Max-Age=0" in set_cookie


class TestGitHubLogin:
    def test_redirects_to_github_with_state_cookie(self, client: TestClient) -> None:
        response = client.get("/auth/github/login", follow_redirects=False)

        assert response.status_code == 307
        location = urlsplit(response.headers["location"])
        assert f"{location.scheme}://{location.netloc}{location.path}" == github.AUTHORIZE_URL
        state = parse_qs(location.query)["state"][0]
        assert response.cookies[STATE_COOKIE] == state
        assert "HttpOnly" in response.headers["set-cookie"]

    def test_state_cookie_is_secure_outside_development(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "environment", "production")

        response = client.get("/auth/github/login", follow_redirects=False)

        assert "Secure" in response.headers["set-cookie"]


class TestGitHubCallback:
    @staticmethod
    def _callback(client: TestClient, **params: str) -> httpx2.Response:
        return client.get("/auth/github/callback", params=params, follow_redirects=False)

    def test_creates_user_sets_cookie_and_redirects_to_dashboard(
        self, client: TestClient, db_session: Session, fake_github_oauth: list[str]
    ) -> None:
        client.cookies.set(STATE_COOKIE, "expected-state")

        response = self._callback(client, code="the-code", state="expected-state")

        assert response.status_code == 302
        assert response.headers["location"] == f"{FRONTEND}/dashboard"
        assert fake_github_oauth == ["the-code"]
        user = db_session.scalar(select(User).where(User.github_user_id == "5005"))
        assert user is not None
        assert user.email == "new@example.com"
        assert decode_access_token(response.cookies[ACCESS_COOKIE]) == user.id

    @pytest.mark.parametrize(
        ("cookie_state", "params"),
        [
            pytest.param("expected", {"code": "c", "state": "forged"}, id="state-mismatch"),
            pytest.param(None, {"code": "c", "state": "expected"}, id="missing-state-cookie"),
            pytest.param("expected", {"state": "expected"}, id="missing-code"),
            pytest.param("expected", {"code": "c"}, id="missing-state"),
            pytest.param(
                "expected", {"error": "access_denied", "state": "expected"}, id="user-denied"
            ),
        ],
    )
    def test_rejects_invalid_callbacks_without_calling_github(
        self,
        client: TestClient,
        fake_github_oauth: list[str],
        cookie_state: str | None,
        params: dict[str, str],
    ) -> None:
        if cookie_state:
            client.cookies.set(STATE_COOKIE, cookie_state)

        response = self._callback(client, **params)

        assert response.status_code == 307
        assert response.headers["location"] == f"{FRONTEND}/login?error=github_failed"
        assert ACCESS_COOKIE not in response.cookies
        assert fake_github_oauth == []

    def test_github_failure_redirects_to_login(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def reject(code: str) -> str:
            raise github.GitHubError("bad_verification_code")

        monkeypatch.setattr(github, "exchange_code_for_token", reject)
        client.cookies.set(STATE_COOKIE, "expected")

        response = self._callback(client, code="c", state="expected")

        assert response.headers["location"] == f"{FRONTEND}/login?error=github_failed"
        assert ACCESS_COOKIE not in response.cookies


class TestCors:
    def test_allows_the_frontend_origin_with_credentials(self, client: TestClient) -> None:
        response = client.options(
            "/auth/me",
            headers={"Origin": FRONTEND, "Access-Control-Request-Method": "GET"},
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == FRONTEND
        assert response.headers["access-control-allow-credentials"] == "true"

    def test_rejects_other_origins(self, client: TestClient) -> None:
        response = client.options(
            "/auth/me",
            headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
        )

        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers
