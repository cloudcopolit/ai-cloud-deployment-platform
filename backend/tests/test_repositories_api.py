"""Connecting repositories, branches and commits: everything comes from (fake) GitHub."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Branch, Commit, Repository
from tests.factories import headers_for, make_project, make_team, make_user
from tests.fakes import FakeGitHub


def _world(db: Session, fake: FakeGitHub):
    owner = make_user(db, "Owner")
    member = make_user(db, "Member")
    team = make_team(db, {owner: "OWNER", member: "MEMBER"})
    project = make_project(db, team)
    repo = fake.add_repo("Delivery-Plus0", "delivery-plus", default_branch="main")
    repo.add_commit("main", "init", {"README.md": "hello"})
    repo.add_commit("main", "add api", {"api/app.py": "print(1)"})
    dev_head = repo.add_commit("dev", "dev work", {"README.md": "dev"})
    db.commit()
    return owner, member, team, project, repo, dev_head


def test_connect_by_url_resolves_everything_from_github(
    client: TestClient, db_session: Session, fake_github: FakeGitHub
) -> None:
    owner, _, _, project, fake_repo, _ = _world(db_session, fake_github)

    res = client.post(
        f"/projects/{project.id}/repositories",
        json={"url": "https://github.com/delivery-plus0/Delivery-Plus.git"},
        headers=headers_for(owner),
    )

    assert res.status_code == 201, res.text
    body = res.json()
    # canonical names and the numeric id come from GitHub, not from the request
    assert (body["owner"], body["name"]) == ("Delivery-Plus0", "delivery-plus")
    assert body["github_repository_id"] == str(fake_repo.github_id)
    assert body["default_branch"] == "main"
    assert body["deployment_branch"] == "main"
    assert body["access_mode"] == "ANONYMOUS"
    assert body["is_private"] is False
    assert body["branch_count"] == 2

    shas = set(db_session.scalars(select(Commit.sha)))
    assert shas == {c["sha"] for c in fake_repo.commits["main"]}


def test_client_supplied_ids_are_rejected(
    client: TestClient, db_session: Session, fake_github: FakeGitHub
) -> None:
    owner, _, _, project, _, _ = _world(db_session, fake_github)
    res = client.post(
        f"/projects/{project.id}/repositories",
        json={"url": "https://github.com/a/b", "github_repository_id": "1", "owner": "x"},
        headers=headers_for(owner),
    )
    assert res.status_code == 422


def test_unknown_or_private_repository_is_a_clear_404(
    client: TestClient, db_session: Session, fake_github: FakeGitHub
) -> None:
    owner, _, _, project, _, _ = _world(db_session, fake_github)
    fake_github.add_repo("acme", "secret", private=True).add_commit("main", "x")

    for url in ("https://github.com/acme/does-not-exist", "https://github.com/acme/secret"):
        res = client.post(
            f"/projects/{project.id}/repositories", json={"url": url}, headers=headers_for(owner)
        )
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "REPOSITORY_NOT_FOUND"
        assert "GitHub App" in res.json()["error"]["message"]


def test_invalid_url_is_400(client: TestClient, db_session: Session, fake_github) -> None:
    owner, _, _, project, _, _ = _world(db_session, fake_github)
    for url in ("https://gitlab.com/a/b", "not a url", "https://github.com/a/../b"):
        res = client.post(
            f"/projects/{project.id}/repositories", json={"url": url}, headers=headers_for(owner)
        )
        assert res.status_code == 400, url


def test_rate_limit_is_reported_honestly(
    client: TestClient, db_session: Session, fake_github: FakeGitHub
) -> None:
    owner, _, _, project, _, _ = _world(db_session, fake_github)
    fake_github.rate_limited = True
    res = client.post(
        f"/projects/{project.id}/repositories",
        json={"url": "https://github.com/Delivery-Plus0/delivery-plus"},
        headers=headers_for(owner),
    )
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "GITHUB_RATE_LIMITED"
    assert res.json()["error"]["details"]["reset_at"].startswith("2030-01-01")


def test_github_outage_is_502_and_nothing_is_stored(
    client: TestClient, db_session: Session, fake_github: FakeGitHub
) -> None:
    owner, _, _, project, _, _ = _world(db_session, fake_github)
    fake_github.fail_with = 503
    res = client.post(
        f"/projects/{project.id}/repositories",
        json={"url": "https://github.com/Delivery-Plus0/delivery-plus"},
        headers=headers_for(owner),
    )
    assert res.status_code == 502
    assert db_session.scalar(select(func.count()).select_from(Repository)) == 0


def test_duplicate_connect_conflicts_but_another_project_may_connect_it(
    client: TestClient, db_session: Session, fake_github: FakeGitHub
) -> None:
    owner, _, team, project, _, _ = _world(db_session, fake_github)
    other_project = make_project(db_session, team)
    db_session.commit()
    url = {"url": "https://github.com/Delivery-Plus0/delivery-plus"}

    assert (
        client.post(
            f"/projects/{project.id}/repositories", json=url, headers=headers_for(owner)
        ).status_code
        == 201
    )
    dup = client.post(f"/projects/{project.id}/repositories", json=url, headers=headers_for(owner))
    assert dup.status_code == 409
    # Q-3 / ADR-021: the same GitHub repository may back several projects
    again = client.post(
        f"/projects/{other_project.id}/repositories", json=url, headers=headers_for(owner)
    )
    assert again.status_code == 201


def test_member_cannot_connect_and_outsider_gets_404(
    client: TestClient, db_session: Session, fake_github: FakeGitHub
) -> None:
    _, member, _, project, _, _ = _world(db_session, fake_github)
    outsider = make_user(db_session, "Outsider")
    db_session.commit()
    url = {"url": "https://github.com/Delivery-Plus0/delivery-plus"}

    res = client.post(f"/projects/{project.id}/repositories", json=url, headers=headers_for(member))
    assert res.status_code == 403
    res = client.post(
        f"/projects/{project.id}/repositories", json=url, headers=headers_for(outsider)
    )
    assert res.status_code == 404


def test_archived_project_accepts_no_new_repository(
    client: TestClient, db_session: Session, fake_github: FakeGitHub
) -> None:
    owner, _, _, project, _, _ = _world(db_session, fake_github)
    project.status = "ARCHIVED"
    db_session.commit()
    res = client.post(
        f"/projects/{project.id}/repositories",
        json={"url": "https://github.com/Delivery-Plus0/delivery-plus"},
        headers=headers_for(owner),
    )
    assert res.status_code == 409


def test_branch_picker_commit_picker_and_deployment_branch(
    client: TestClient, db_session: Session, fake_github: FakeGitHub
) -> None:
    owner, member, _, project, _, dev_head = _world(db_session, fake_github)
    repo_id = client.post(
        f"/projects/{project.id}/repositories",
        json={"url": "https://github.com/Delivery-Plus0/delivery-plus"},
        headers=headers_for(owner),
    ).json()["id"]

    branches = client.get(f"/repositories/{repo_id}/branches", headers=headers_for(member)).json()
    assert [b["name"] for b in branches] == ["main", "dev"]  # deployment branch first

    commits = client.get(
        f"/repositories/{repo_id}/commits",
        params={"branch": "dev", "refresh": "true"},
        headers=headers_for(member),
    ).json()
    assert [c["sha"] for c in commits] == [dev_head]

    # cached afterwards, no GitHub call needed
    calls = len(fake_github.requests)
    cached = client.get(
        f"/repositories/{repo_id}/commits", params={"branch": "dev"}, headers=headers_for(member)
    ).json()
    assert [c["sha"] for c in cached] == [dev_head]
    assert len(fake_github.requests) == calls

    assert (
        client.put(
            f"/repositories/{repo_id}/deployment-branch",
            json={"branch_name": "dev"},
            headers=headers_for(member),
        ).status_code
        == 403
    )
    switched = client.put(
        f"/repositories/{repo_id}/deployment-branch",
        json={"branch_name": "dev"},
        headers=headers_for(owner),
    )
    assert switched.status_code == 200
    assert switched.json()["is_deployment_branch"] is True
    deployment_branches = db_session.scalars(
        select(Branch.name).where(Branch.is_deployment_branch.is_(True))
    ).all()
    assert deployment_branches == ["dev"]

    unknown = client.put(
        f"/repositories/{repo_id}/deployment-branch",
        json={"branch_name": "nope"},
        headers=headers_for(owner),
    )
    assert unknown.status_code == 404


def test_sync_picks_up_new_branches_and_commits(
    client: TestClient, db_session: Session, fake_github: FakeGitHub
) -> None:
    owner, _, _, project, fake_repo, _ = _world(db_session, fake_github)
    repo_id = client.post(
        f"/projects/{project.id}/repositories",
        json={"url": "https://github.com/Delivery-Plus0/delivery-plus"},
        headers=headers_for(owner),
    ).json()["id"]
    new_sha = fake_repo.add_commit("main", "hotfix")
    fake_repo.add_commit("feature/x", "wip")

    res = client.post(f"/repositories/{repo_id}/sync", headers=headers_for(owner))

    assert res.status_code == 200
    assert res.json()["branch_count"] == 3
    assert db_session.scalar(select(Commit.id).where(Commit.sha == new_sha)) is not None
    assert res.json()["last_synced_at"] is not None


def test_repository_reads_are_tenant_scoped(
    client: TestClient, db_session: Session, fake_github: FakeGitHub
) -> None:
    owner, _, _, project, _, _ = _world(db_session, fake_github)
    outsider = make_user(db_session, "Outsider")
    db_session.commit()
    repo_id = client.post(
        f"/projects/{project.id}/repositories",
        json={"url": "https://github.com/Delivery-Plus0/delivery-plus"},
        headers=headers_for(owner),
    ).json()["id"]

    for path in (
        f"/repositories/{repo_id}",
        f"/repositories/{repo_id}/branches",
        f"/repositories/{repo_id}/commits",
        f"/projects/{project.id}/repositories",
    ):
        assert client.get(path, headers=headers_for(outsider)).status_code == 404, path
    assert client.get(f"/repositories/{uuid4()}", headers=headers_for(owner)).status_code == 404


def test_github_access_status_has_no_secrets(
    client: TestClient,
    db_session: Session,
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # hermetic: the developer's .env may name a real App slug
    monkeypatch.setattr("app.modules.repositories.service.settings.github_app_slug", None)
    owner, *_ = _world(db_session, fake_github)
    res = client.get("/github/access", headers=headers_for(owner))
    assert res.status_code == 200
    assert res.json() == {
        "app_configured": False,
        "app_installations": None,
        "app_installations_usable": None,
        "app_install_url": None,
        "token_configured": False,
        "rate_limit_remaining": 57,
        "rate_limit_limit": 60,
        "mode_for_public_repos": "ANONYMOUS",
        "webhook_enabled": False,
    }


def test_sync_prunes_vanished_branches_but_keeps_history(
    client: TestClient, db_session: Session, fake_github: FakeGitHub
) -> None:
    owner, _, _, project, fake_repo, _ = _world(db_session, fake_github)
    fake_repo.add_commit("tmp", "throwaway")
    repo_id = client.post(
        f"/projects/{project.id}/repositories",
        json={"url": "https://github.com/Delivery-Plus0/delivery-plus"},
        headers=headers_for(owner),
    ).json()["id"]
    # commits of "dev" are recorded, "tmp" was only listed
    client.get(
        f"/repositories/{repo_id}/commits",
        params={"branch": "dev", "refresh": "true"},
        headers=headers_for(owner),
    )
    del fake_repo.commits["tmp"]
    del fake_repo.commits["dev"]

    client.post(f"/repositories/{repo_id}/sync", headers=headers_for(owner))

    names = set(db_session.scalars(select(Branch.name)))
    assert names == {"main", "dev"}  # "dev" stays: its commits reference it


def test_sync_refuses_when_the_name_now_points_to_another_repository(
    client: TestClient, db_session: Session, fake_github: FakeGitHub
) -> None:
    owner, _, _, project, _, _ = _world(db_session, fake_github)
    repo_id = client.post(
        f"/projects/{project.id}/repositories",
        json={"url": "https://github.com/Delivery-Plus0/delivery-plus"},
        headers=headers_for(owner),
    ).json()["id"]
    replacement = fake_github.add_repo("Delivery-Plus0", "delivery-plus")  # same name, new id
    replacement.add_commit("main", "x")

    res = client.post(f"/repositories/{repo_id}/sync", headers=headers_for(owner))
    assert res.status_code == 409


def test_resolve_commit_uses_github_for_unknown_shas_and_branch_heads(
    client: TestClient, db_session: Session, fake_github: FakeGitHub
) -> None:
    from app.modules.repositories.service import resolve_commit

    owner, _, _, project, fake_repo, dev_head = _world(db_session, fake_github)
    repo_id = client.post(
        f"/projects/{project.id}/repositories",
        json={"url": "https://github.com/Delivery-Plus0/delivery-plus"},
        headers=headers_for(owner),
    ).json()["id"]
    repo = db_session.get(Repository, repo_id)
    assert repo is not None
    client.post(f"/repositories/{repo_id}/sync", headers=headers_for(owner))
    github = fake_github.client()

    head = resolve_commit(db_session, github, repo, "dev", None)
    assert head.sha == dev_head
    known = resolve_commit(db_session, github, repo, "main", fake_repo.commits["main"][1]["sha"])
    assert known.sha == fake_repo.commits["main"][1]["sha"]
    default_branch_head = resolve_commit(db_session, github, repo, None, None)
    assert default_branch_head.sha == fake_repo.commits["main"][0]["sha"]

    import pytest

    from app.core.errors import NotFound

    with pytest.raises(NotFound):
        resolve_commit(db_session, github, repo, "no-such-branch", None)
    with pytest.raises(NotFound):  # GitHub answers 422 for a SHA it does not know
        resolve_commit(db_session, github, repo, "main", "f" * 40)
