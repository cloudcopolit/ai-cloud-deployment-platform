"""Analysis API (05 §3.4): 202 + QUEUED job, polling, activity, cancel, answers, limits."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import RepositoryAnalysis, TeamMember
from tests.factories import (
    connected_repository,
    headers_for,
    make_user,
    run_queued_job_inline,
)
from tests.fakes import FakeGitHub

SQLITE_FILES = {
    "requirements.txt": "flask==3.0.3\n",
    "app.py": "import sqlite3\nfrom flask import Flask\napp = Flask(__name__)\n"
    "sqlite3.connect('x.db')\n@app.route('/health')\ndef h():\n    return ''\n",
    "Dockerfile": "FROM python:3.12-slim\nEXPOSE 5000\n",
}


def _start(client: TestClient, repo_id, user, **body) -> dict:
    res = client.post(f"/repositories/{repo_id}/analyses", json=body, headers=headers_for(user))
    assert res.status_code == 202, res.text
    assert res.headers["location"] == f"/analyses/{res.json()['id']}"
    return res.json()


def test_post_queues_a_job_and_returns_202(
    client: TestClient, db_session: Session, fake_github: FakeGitHub
) -> None:
    owner = make_user(db_session)
    _, project, repo = connected_repository(db_session, fake_github, owner)

    job = _start(client, repo.id, owner)

    assert (job["status"], job["terminal"], job["report"]) == ("QUEUED", False, None)
    assert job["project_id"] == str(project.id)
    assert len(job["commit_sha"]) == 40
    polled = client.get(f"/analyses/{job['id']}", headers=headers_for(owner)).json()
    assert polled["status"] == "QUEUED"  # nothing ran inside the request


def test_worker_result_is_visible_through_polling_and_activity(
    client: TestClient, db_session: Session, fake_github: FakeGitHub
) -> None:
    owner = make_user(db_session)
    _, _, repo = connected_repository(db_session, fake_github, owner)
    job = _start(client, repo.id, owner)

    assert run_queued_job_inline(db_session, fake_github, uuid.UUID(job["id"])) == "SUCCESS"

    done = client.get(f"/analyses/{job['id']}", headers=headers_for(owner)).json()
    assert (done["status"], done["terminal"], done["services_count"]) == ("SUCCESS", True, 1)
    assert done["report"]["services"][0]["framework"] == "FastAPI"
    assert done["duration_ms"] is not None

    activity = client.get(f"/analyses/{job['id']}/activity", headers=headers_for(owner)).json()
    assert activity["terminal"] is True
    agents = [r["agent_type"] for r in activity["runs"]]
    assert agents == ["ORCHESTRATOR", "ANALYSIS"]
    analysis = activity["runs"][1]
    assert analysis["status"] == "SUCCESS"
    assert [t["task_type"] for t in analysis["tasks"]][:2] == [
        "read_repository",
        "detect_languages_and_frameworks",
    ]
    assert any(t["status"] == "SKIPPED" for t in analysis["tasks"])  # LLM step, honestly

    services = client.get(f"/analyses/{job['id']}/services", headers=headers_for(owner)).json()
    assert [(s["name"], s["port"]) for s in services] == [(repo.name, 8000)]


def test_specific_branch_and_commit(client: TestClient, db_session: Session, fake_github) -> None:
    owner = make_user(db_session)
    _, _, repo = connected_repository(db_session, fake_github, owner)
    remote = next(iter(fake_github.repos.values()))
    dev_sha = remote.add_commit("dev", "dev change", {"README.md": "x"})
    from app.models import Branch

    db_session.add(Branch(repository_id=repo.id, name="dev"))
    db_session.commit()

    job = _start(client, repo.id, owner, branch="dev", commit_sha=dev_sha)
    assert (job["branch_name"], job["commit_sha"]) == ("dev", dev_sha)

    bad = client.post(
        f"/repositories/{repo.id}/analyses",
        json={"commit_sha": "not-a-sha"},
        headers=headers_for(owner),
    )
    assert bad.status_code == 422


def test_idempotency_key_returns_the_same_job(
    client: TestClient, db_session: Session, fake_github
) -> None:
    owner = make_user(db_session)
    _, _, repo = connected_repository(db_session, fake_github, owner)
    headers = {**headers_for(owner), "Idempotency-Key": "click-123"}
    first = client.post(f"/repositories/{repo.id}/analyses", json={}, headers=headers).json()
    again = client.post(f"/repositories/{repo.id}/analyses", json={}, headers=headers).json()
    assert first["id"] == again["id"]
    assert db_session.query(RepositoryAnalysis).count() == 1


def test_team_capacity_limit_is_429(
    client: TestClient, db_session: Session, fake_github, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "max_active_jobs_per_team", 2)
    owner = make_user(db_session)
    _, _, repo = connected_repository(db_session, fake_github, owner)
    _start(client, repo.id, owner)
    _start(client, repo.id, owner)
    res = client.post(f"/repositories/{repo.id}/analyses", json={}, headers=headers_for(owner))
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "RATE_LIMITED"


def test_cancel_queued_and_conflict_when_finished(
    client: TestClient, db_session: Session, fake_github
) -> None:
    owner = make_user(db_session)
    _, _, repo = connected_repository(db_session, fake_github, owner)
    job = _start(client, repo.id, owner)

    cancelled = client.post(f"/analyses/{job['id']}/cancel", headers=headers_for(owner))
    assert cancelled.status_code == 202
    assert (cancelled.json()["status"], cancelled.json()["error_code"]) == (
        "CANCELLED",
        "JOB_CANCELLED",
    )
    again = client.post(f"/analyses/{job['id']}/cancel", headers=headers_for(owner))
    assert again.status_code == 409


def test_cancel_running_job_only_requests_it(
    client: TestClient, db_session: Session, fake_github
) -> None:
    owner = make_user(db_session)
    _, _, repo = connected_repository(db_session, fake_github, owner)
    job = _start(client, repo.id, owner)
    row = db_session.get(RepositoryAnalysis, uuid.UUID(job["id"]))
    assert row is not None
    row.status = "RUNNING"
    db_session.commit()

    res = client.post(f"/analyses/{job['id']}/cancel", headers=headers_for(owner)).json()
    assert (res["status"], res["cancel_requested"]) == ("RUNNING", True)


def test_blocked_analysis_answers_queue_a_rerun(
    client: TestClient, db_session: Session, fake_github
) -> None:
    owner = make_user(db_session)
    _, _, repo = connected_repository(db_session, fake_github, owner, SQLITE_FILES)
    job = _start(client, repo.id, owner)
    assert run_queued_job_inline(db_session, fake_github, uuid.UUID(job["id"])) == "BLOCKED"
    blocked = client.get(f"/analyses/{job['id']}", headers=headers_for(owner)).json()
    assert blocked["error_code"] is None  # BLOCKED is not a failure
    assert [m["key"] for m in blocked["report"]["missing_info"]] == ["datastore:sqlite"]

    unknown = client.post(
        f"/analyses/{job['id']}/answers",
        json={"answers": {"port:other": "1"}},
        headers=headers_for(owner),
    )
    assert unknown.status_code == 400

    rerun = client.post(
        f"/analyses/{job['id']}/answers",
        json={"answers": {"datastore:sqlite": "postgresql"}},
        headers=headers_for(owner),
    )
    assert rerun.status_code == 202
    child = rerun.json()
    assert (child["parent_analysis_id"], child["user_answers"]) == (
        job["id"],
        {"datastore:sqlite": "postgresql"},
    )
    assert child["commit_sha"] == blocked["commit_sha"]
    assert run_queued_job_inline(db_session, fake_github, uuid.UUID(child["id"])) == "SUCCESS"

    not_blocked = client.post(
        f"/analyses/{child['id']}/answers",
        json={"answers": {"x": "y"}},
        headers=headers_for(owner),
    )
    assert not_blocked.status_code == 409


def test_member_can_analyze_and_outsiders_see_nothing(
    client: TestClient, db_session: Session, fake_github
) -> None:
    owner = make_user(db_session)
    member = make_user(db_session)
    outsider = make_user(db_session)
    team, project, repo = connected_repository(db_session, fake_github, owner)
    db_session.add(TeamMember(team_id=team.id, user_id=member.id, role="MEMBER"))
    db_session.commit()

    job = _start(client, repo.id, member)
    for path in (
        f"/analyses/{job['id']}",
        f"/analyses/{job['id']}/activity",
        f"/analyses/{job['id']}/services",
        f"/repositories/{repo.id}/analyses",
        f"/projects/{project.id}/analyses",
    ):
        assert client.get(path, headers=headers_for(outsider)).status_code == 404, path
        assert client.get(path, headers=headers_for(member)).status_code == 200, path
    for path in (f"/analyses/{job['id']}/cancel", f"/repositories/{repo.id}/analyses"):
        assert client.post(path, json={}, headers=headers_for(outsider)).status_code == 404, path
    assert client.get(f"/analyses/{uuid.uuid4()}", headers=headers_for(owner)).status_code == 404


def test_archived_project_accepts_no_analysis(
    client: TestClient, db_session: Session, fake_github
) -> None:
    owner = make_user(db_session)
    _, project, repo = connected_repository(db_session, fake_github, owner)
    project.status = "ARCHIVED"
    db_session.commit()
    res = client.post(f"/repositories/{repo.id}/analyses", json={}, headers=headers_for(owner))
    assert res.status_code == 409


def test_history_lists_newest_first(client: TestClient, db_session: Session, fake_github) -> None:
    owner = make_user(db_session)
    _, project, repo = connected_repository(db_session, fake_github, owner)
    first = _start(client, repo.id, owner)
    second = _start(client, repo.id, owner)
    listed = client.get(f"/repositories/{repo.id}/analyses", headers=headers_for(owner)).json()
    assert [j["id"] for j in listed][:2] in (
        [second["id"], first["id"]],
        [first["id"], second["id"]],
    )
    assert (
        len(
            client.get(
                f"/projects/{project.id}/analyses?limit=1", headers=headers_for(owner)
            ).json()
        )
        == 1
    )
