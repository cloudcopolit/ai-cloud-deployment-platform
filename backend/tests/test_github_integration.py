"""GitHub OAuth client, exercised against a mocked GitHub HTTP API (no network)."""

from collections.abc import Callable
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from app.core.config import settings
from app.integrations import github

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def mock_github(monkeypatch: pytest.MonkeyPatch) -> Callable[[Handler], list[httpx.Request]]:
    """Route every request made by the integration through `handler`."""

    def install(handler: Handler) -> list[httpx.Request]:
        requests: list[httpx.Request] = []

        def record(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return handler(request)

        transport = httpx.MockTransport(record)
        real_client = httpx.Client

        def post(url: str, **kwargs) -> httpx.Response:
            with real_client(transport=transport) as client:
                return client.post(url, **kwargs)

        monkeypatch.setattr(github.httpx, "post", post)
        monkeypatch.setattr(
            github.httpx, "Client", lambda **kwargs: real_client(transport=transport, **kwargs)
        )
        return requests

    return install


def test_authorize_url_requests_identity_scopes_only() -> None:
    url = urlsplit(github.build_authorize_url("state-123"))
    query = parse_qs(url.query)

    assert f"{url.scheme}://{url.netloc}{url.path}" == github.AUTHORIZE_URL
    assert query == {
        "client_id": [settings.github_client_id],
        "redirect_uri": [settings.github_redirect_uri],
        "scope": ["read:user user:email"],
        "state": ["state-123"],
    }


def test_exchange_code_returns_access_token(mock_github) -> None:
    requests = mock_github(lambda _: httpx.Response(200, json={"access_token": "gho_test"}))

    assert github.exchange_code_for_token("the-code") == "gho_test"
    body = parse_qs(requests[0].content.decode())
    assert body["code"] == ["the-code"]
    assert body["client_secret"] == [settings.github_client_secret]


def test_exchange_code_raises_when_github_rejects_the_code(mock_github) -> None:
    mock_github(
        lambda _: httpx.Response(
            200, json={"error": "bad_verification_code", "error_description": "expired"}
        )
    )

    with pytest.raises(github.GitHubError, match="expired"):
        github.exchange_code_for_token("stale-code")


def test_exchange_code_raises_on_http_error(mock_github) -> None:
    mock_github(lambda _: httpx.Response(502))

    with pytest.raises(httpx.HTTPStatusError):
        github.exchange_code_for_token("the-code")


def test_fetch_profile_uses_public_email(mock_github) -> None:
    requests = mock_github(
        lambda _: httpx.Response(
            200,
            json={
                "id": 42,
                "login": "octocat",
                "name": "Mona",
                "email": "mona@example.com",
                "avatar_url": "https://avatars.example.com/42",
            },
        )
    )

    profile = github.fetch_profile("gho_test")

    assert profile == github.GitHubProfile(
        github_id="42",
        name="Mona",
        email="mona@example.com",
        avatar_url="https://avatars.example.com/42",
    )
    assert [r.url.path for r in requests] == ["/user"]
    assert requests[0].headers["Authorization"] == "Bearer gho_test"


def test_fetch_profile_falls_back_to_primary_verified_email_and_login(mock_github) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user":
            return httpx.Response(200, json={"id": 7, "login": "octocat", "name": None})
        return httpx.Response(
            200,
            json=[
                {"email": "old@example.com", "primary": False, "verified": True},
                {"email": "unverified@example.com", "primary": True, "verified": False},
                {"email": "primary@example.com", "primary": True, "verified": True},
            ],
        )

    mock_github(handler)

    profile = github.fetch_profile("gho_test")

    assert profile.name == "octocat"
    assert profile.email == "primary@example.com"
    assert profile.avatar_url is None
