"""GitHubClient unit tests against httpx.MockTransport (no network)."""

import hashlib
import hmac
import json

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.errors import (
    BadRequest,
    GitHubRateLimited,
    GitHubUnauthorized,
    RepositoryTooLarge,
    UpstreamError,
)
from app.integrations.github_app import (
    GitHubClient,
    parse_repository_url,
    verify_webhook_signature,
)
from tests.fakes import API, RAW, FakeGitHub

SHA = "a" * 40


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/Delivery-Plus0/delivery-plus", ("Delivery-Plus0", "delivery-plus")),
        ("https://github.com/o/r.git", ("o", "r")),
        ("https://www.github.com/o/r/", ("o", "r")),
        ("git@github.com:o/my.repo.git", ("o", "my.repo")),
        ("  o/r  ", ("o", "r")),
    ],
)
def test_parse_repository_url_accepts_common_forms(url: str, expected: tuple[str, str]) -> None:
    assert parse_repository_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://gitlab.com/o/r",
        "https://github.com/o",
        "https://github.com/o/r/tree/main",
        "https://github.com/-bad/r",
        "o/..",
        "file:///etc/passwd",
        "",
    ],
)
def test_parse_repository_url_rejects_everything_else(url: str) -> None:
    with pytest.raises(BadRequest):
        parse_repository_url(url)


def test_webhook_signature_is_constant_time_hmac_sha256() -> None:
    body = b'{"zen":"x"}'
    good = "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    assert verify_webhook_signature("s3cret", body, good)
    assert not verify_webhook_signature("s3cret", body + b" ", good)
    assert not verify_webhook_signature("other", body, good)
    assert not verify_webhook_signature("s3cret", body, None)
    assert not verify_webhook_signature("s3cret", body, good.replace("sha256=", "sha1="))
    assert not verify_webhook_signature("", body, good)


def _private_key_pem() -> tuple[str, rsa.RSAPublicKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return pem, key.public_key()


def test_app_installation_token_is_minted_cached_and_used() -> None:
    pem, public_key = _private_key_pem()
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.path
        if path == "/repos/acme/private-app/installation":
            app_jwt = request.headers["authorization"].removeprefix("Bearer ")
            claims = jwt.decode(app_jwt, public_key, algorithms=["RS256"])
            assert claims["iss"] == "42"
            assert claims["exp"] - claims["iat"] <= 600  # GitHub's maximum
            return httpx.Response(200, json={"id": 7})
        if path == "/app/installations/7/access_tokens":
            return httpx.Response(
                201, json={"token": "ghs_x", "expires_at": "2099-01-01T00:00:00Z"}
            )
        if path == "/repos/acme/private-app":
            assert request.headers["authorization"] == "Bearer ghs_x"
            return httpx.Response(
                200,
                json={
                    "id": 9,
                    "name": "private-app",
                    "owner": {"login": "acme"},
                    "html_url": "https://github.com/acme/private-app",
                    "default_branch": "main",
                    "private": True,
                    "size": 1,
                },
            )
        return httpx.Response(404)

    client = GitHubClient(
        api_url=API,
        raw_url=RAW,
        app_id="42",
        app_private_key=pem,
        transport=httpx.MockTransport(handler),
    )
    first = client.get_repository("acme", "private-app")
    second = client.get_repository("acme", "private-app")

    assert first.access_mode == "GITHUB_APP"
    assert first.private
    assert second == first
    minted = [r for r in seen if r.url.path.endswith("/access_tokens")]
    assert len(minted) == 1  # cached until shortly before expiry


def test_falls_back_to_token_then_anonymous_when_app_not_installed() -> None:
    fake = FakeGitHub()
    fake.add_repo("o", "r").add_commit("main", "x")
    with_token = fake.client(token="ghp_example")
    assert with_token.get_repository("o", "r").access_mode == "TOKEN"
    assert fake.requests[-1].headers["authorization"] == "Bearer ghp_example"
    anonymous = fake.client()
    assert anonymous.get_repository("o", "r").access_mode == "ANONYMOUS"
    assert "authorization" not in fake.requests[-1].headers


def test_tree_skips_symlinks_and_submodules() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "truncated": True,
                "tree": [
                    {"path": "a.py", "mode": "100644", "type": "blob", "sha": "1", "size": 3},
                    {"path": "run.sh", "mode": "100755", "type": "blob", "sha": "2", "size": 3},
                    {"path": "link", "mode": "120000", "type": "blob", "sha": "3", "size": 9},
                    {"path": "vendor", "mode": "160000", "type": "commit", "sha": "4"},
                    {"path": "src", "mode": "040000", "type": "tree", "sha": "5"},
                ],
            },
        )

    client = GitHubClient(api_url=API, raw_url=RAW, transport=httpx.MockTransport(handler))
    tree = client.get_tree("o", "r", SHA)
    assert [e.path for e in tree.entries] == ["a.py", "run.sh"]
    assert tree.truncated is True
    with pytest.raises(BadRequest):
        client.get_tree("o", "r", "main")  # only full SHAs, never a moving ref


def test_read_file_enforces_size_limit_and_rejects_path_tricks() -> None:
    fake = FakeGitHub()
    repo = fake.add_repo("o", "r")
    sha = repo.add_commit("main", "x", {"big.txt": "x" * 2048, "ok.txt": "fine"})
    client = fake.client()

    assert client.read_file("o", "r", sha, "ok.txt", max_bytes=100) == b"fine"
    with pytest.raises(RepositoryTooLarge):
        client.read_file("o", "r", sha, "big.txt", max_bytes=1024)
    for bad in ("../etc/passwd", "/abs", "a/../../b"):
        with pytest.raises(BadRequest):
            client.read_file("o", "r", sha, bad, max_bytes=100)
    # public content comes from the raw host, which does not consume API quota
    assert all(r.url.host == "raw.github.test" for r in fake.requests)


def test_retries_transient_failures_then_reports_upstream_error() -> None:
    attempts = {"n": 0}

    def flaky(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            return httpx.Response(502)
        return httpx.Response(200, json={"resources": {"core": {"limit": 60, "remaining": 1}}})

    client = GitHubClient(
        api_url=API, raw_url=RAW, transport=httpx.MockTransport(flaky), sleep=lambda _: None
    )
    assert client.access_status().rate_limit_remaining == 1

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    broken = GitHubClient(
        api_url=API, raw_url=RAW, transport=httpx.MockTransport(down), sleep=lambda _: None
    )
    with pytest.raises(UpstreamError):
        broken.get_repository("o", "r")


def test_status_codes_map_to_domain_errors() -> None:
    def respond(status: int, headers: dict[str, str] | None = None):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status, headers=headers or {}, json={})

        return GitHubClient(api_url=API, raw_url=RAW, transport=httpx.MockTransport(handler))

    with pytest.raises(GitHubRateLimited):
        respond(429).get_repository("o", "r")
    with pytest.raises(GitHubUnauthorized):
        respond(401).get_repository("o", "r")
    with pytest.raises(GitHubUnauthorized):
        respond(403, {"x-ratelimit-remaining": "12"}).get_repository("o", "r")
    with pytest.raises(BadRequest):
        respond(409).list_commits("o", "r", "main")  # empty repository
    with pytest.raises(UpstreamError):
        respond(418).get_repository("o", "r")


def test_tokens_never_appear_in_error_messages() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Bad credentials"})

    client = GitHubClient(
        api_url=API, raw_url=RAW, token="ghp_SUPERSECRET", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(GitHubUnauthorized) as exc:
        client.get_repository("o", "r")
    assert "SUPERSECRET" not in json.dumps({"m": exc.value.message, "d": exc.value.details})


def test_not_installed_lookup_is_cached_and_falls_back() -> None:
    pem, _ = _private_key_pem()
    fake = FakeGitHub()
    fake.add_repo("o", "r").add_commit("main", "x")
    client = fake.client(app_id="42", app_private_key=pem)

    assert client.get_repository("o", "r").access_mode == "ANONYMOUS"
    client.list_branches("o", "r")

    lookups = [r for r in fake.requests if r.url.path == "/repos/o/r/installation"]
    assert len(lookups) == 1


def test_renamed_repository_redirect_is_followed_on_the_same_host_only() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/old/name":
            return httpx.Response(301, headers={"Location": f"{API}/repositories/5"})
        if request.url.path == "/repos/evil/name":
            return httpx.Response(301, headers={"Location": "https://attacker.example/steal"})
        if request.url.path == "/repositories/5":
            return httpx.Response(
                200,
                json={
                    "id": 5,
                    "name": "new-name",
                    "owner": {"login": "new-owner"},
                    "html_url": "https://github.com/new-owner/new-name",
                    "default_branch": "main",
                    "private": False,
                    "size": 1,
                },
            )
        return httpx.Response(404)

    client = GitHubClient(
        api_url=API, raw_url=RAW, token="ghp_x", transport=httpx.MockTransport(handler)
    )
    info = client.get_repository("old", "name")
    assert (info.owner, info.name) == ("new-owner", "new-name")
    with pytest.raises(UpstreamError):
        client.get_repository("evil", "name")
