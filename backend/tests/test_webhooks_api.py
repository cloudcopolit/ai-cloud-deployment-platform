"""POST /webhooks/github: HMAC-authenticated, idempotent, deployment branch only."""

import hashlib
import hmac

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Commit
from tests.factories import headers_for, make_project, make_team, make_user
from tests.fakes import FakeGitHub, push_payload

SECRET = "webhook-test-secret"


def _sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
def webhook_secret(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(settings, "github_webhook_secret", SECRET)
    return SECRET


@pytest.fixture
def connected(client: TestClient, db_session: Session, fake_github: FakeGitHub):
    owner = make_user(db_session)
    team = make_team(db_session, {owner: "OWNER"})
    project = make_project(db_session, team)
    repo = fake_github.add_repo("acme", "shop")
    repo.add_commit("main", "init")
    db_session.commit()
    res = client.post(
        f"/projects/{project.id}/repositories",
        json={"url": "https://github.com/acme/shop"},
        headers=headers_for(owner),
    )
    assert res.status_code == 201
    return repo


def _commit_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Commit)) or 0


def test_disabled_without_secret_returns_404(client: TestClient) -> None:
    res = client.post("/webhooks/github", content=b"{}", headers={"X-GitHub-Event": "ping"})
    assert res.status_code == 404


def test_missing_or_forged_signature_is_rejected(
    client: TestClient, db_session: Session, webhook_secret: str, connected
) -> None:
    body = push_payload(connected, "main", ["b" * 40])
    before = _commit_count(db_session)
    for signature in (None, "sha256=" + "0" * 64, _sign(body, "wrong-secret")):
        headers = {"X-GitHub-Event": "push"}
        if signature:
            headers["X-Hub-Signature-256"] = signature
        res = client.post("/webhooks/github", content=body, headers=headers)
        assert res.status_code == 401
    assert _commit_count(db_session) == before


def test_push_to_deployment_branch_records_commits_once(
    client: TestClient, db_session: Session, webhook_secret: str, connected
) -> None:
    body = push_payload(connected, "main", ["c" * 40, "d" * 40])
    headers = {"X-GitHub-Event": "push", "X-Hub-Signature-256": _sign(body)}
    before = _commit_count(db_session)

    # no Origin header: webhooks are server-to-server and exempt from the CSRF check
    assert client.post("/webhooks/github", content=body, headers=headers).status_code == 202
    assert _commit_count(db_session) == before + 2
    # redelivery (replay) is a no-op
    assert client.post("/webhooks/github", content=body, headers=headers).status_code == 202
    assert _commit_count(db_session) == before + 2


def test_push_to_other_branch_or_tag_is_ignored(
    client: TestClient, db_session: Session, webhook_secret: str, connected
) -> None:
    before = _commit_count(db_session)
    for ref_branch in ("feature/x",):
        body = push_payload(connected, ref_branch, ["e" * 40])
        headers = {"X-GitHub-Event": "push", "X-Hub-Signature-256": _sign(body)}
        assert client.post("/webhooks/github", content=body, headers=headers).status_code == 202
    tag = b'{"ref":"refs/tags/v1","repository":{"id":1},"commits":[]}'
    headers = {"X-GitHub-Event": "push", "X-Hub-Signature-256": _sign(tag)}
    assert client.post("/webhooks/github", content=tag, headers=headers).status_code == 202
    assert _commit_count(db_session) == before


def test_ping_and_malformed_payloads(client: TestClient, webhook_secret: str) -> None:
    ping = b'{"zen":"hi"}'
    res = client.post(
        "/webhooks/github",
        content=ping,
        headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": _sign(ping)},
    )
    assert res.status_code == 204
    for body in (b"not json", b"[1,2]"):
        res = client.post(
            "/webhooks/github",
            content=body,
            headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": _sign(body)},
        )
        assert res.status_code == 400
    weird = b'{"ref":"refs/heads/main","repository":{"id":1},"commits":[{"id":"short"}]}'
    res = client.post(
        "/webhooks/github",
        content=weird,
        headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": _sign(weird)},
    )
    assert res.status_code == 202
