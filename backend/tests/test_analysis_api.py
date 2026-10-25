from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Branch, Commit, Project, Repository, Team, TeamMember, User


def _setup_repo_and_auth(
    db_session: Session, client: TestClient, role: str = "OWNER"
) -> tuple[User, Team, Project, Repository, str]:
    user = User(
        github_user_id="analysis-tester-1",
        name="Analysis Tester",
        email="analyzer@example.com",
    )
    db_session.add(user)
    db_session.flush()

    team = Team(name="Analysis Team")
    db_session.add(team)
    db_session.flush()

    membership = TeamMember(team_id=team.id, user_id=user.id, role=role)
    db_session.add(membership)

    project = Project(team_id=team.id, name="Analysis Project")

    db_session.add(project)
    db_session.flush()

    repo = Repository(
        project_id=project.id,
        github_repository_id="99901",
        owner="cloudpilot-test",
        name="demo-shop",
        url="https://github.com/cloudpilot-test/demo-shop",
    )
    db_session.add(repo)
    db_session.flush()

    branch = Branch(
        repository_id=repo.id,
        name="main",
        is_deployment_branch=True,
    )
    db_session.add(branch)
    db_session.flush()

    commit = Commit(
        repository_id=repo.id,
        branch_id=branch.id,
        sha="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        message="feat: initial commit for analysis",
        author_name="Dev Tester",
        author_email="dev@example.com",
        committed_at=datetime.now(UTC),
    )
    db_session.add(commit)
    db_session.commit()

    token_resp = client.post(
        "/auth/dev-login",
        json={"github_user_id": user.github_user_id},
        headers={"Origin": "http://localhost:3000"},
    )
    assert token_resp.status_code == 200
    token = token_resp.json()["access_token"]
    return user, team, project, repo, token


def test_trigger_and_retrieve_analysis(client: TestClient, db_session: Session) -> None:
    _, _, project, repo, token = _setup_repo_and_auth(db_session, client)

    headers = {
        "Authorization": f"Bearer {token}",
        "Origin": "http://localhost:3000",
    }

    # Trigger analysis
    resp = client.post(
        f"/repositories/{repo.id}/analyses",
        json={},
        headers=headers,
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["commit_sha"] == "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
    assert data["services_count"] >= 1
    assert data["report"] is not None
    assert "services" in data["report"]
    analysis_id = data["id"]

    # Get analysis details
    detail_resp = client.get(f"/analyses/{analysis_id}", headers=headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == analysis_id
    assert detail["status"] == "SUCCESS"

    # List repository analyses
    repo_list_resp = client.get(f"/repositories/{repo.id}/analyses", headers=headers)
    assert repo_list_resp.status_code == 200
    assert len(repo_list_resp.json()) >= 1

    # List project analyses
    proj_list_resp = client.get(f"/projects/{project.id}/analyses", headers=headers)
    assert proj_list_resp.status_code == 200
    assert len(proj_list_resp.json()) >= 1


def test_analysis_permissions(client: TestClient, db_session: Session) -> None:
    _, _, _, repo, _ = _setup_repo_and_auth(db_session, client)

    # Create outsider user
    outsider = User(
        github_user_id="outsider-user-1",
        name="Outsider",
        email="outsider@example.com",
    )
    db_session.add(outsider)
    db_session.commit()

    token_resp = client.post(
        "/auth/dev-login",
        json={"github_user_id": outsider.github_user_id},
        headers={"Origin": "http://localhost:3000"},
    )
    outsider_token = token_resp.json()["access_token"]
    headers = {
        "Authorization": f"Bearer {outsider_token}",
        "Origin": "http://localhost:3000",
    }

    resp = client.post(
        f"/repositories/{repo.id}/analyses",
        json={},
        headers=headers,
    )
    # Foreign tenants must not learn that the object exists (08 §3).
    assert resp.status_code == 404


def test_analysis_not_found_handling(client: TestClient, db_session: Session) -> None:
    import uuid

    _, _, _, _, token = _setup_repo_and_auth(db_session, client)
    headers = {"Authorization": f"Bearer {token}", "Origin": "http://localhost:3000"}

    # 404 for unknown analysis
    assert client.get(f"/analyses/{uuid.uuid4()}", headers=headers).status_code == 404

    # 404 for unknown repo analysis trigger
    bad_repo_url = f"/repositories/{uuid.uuid4()}/analyses"
    assert client.post(bad_repo_url, json={}, headers=headers).status_code == 404

    # 404 for unknown repo analysis list
    assert client.get(bad_repo_url, headers=headers).status_code == 404

    # 404 for unknown project analysis list
    bad_proj_url = f"/projects/{uuid.uuid4()}/analyses"
    assert client.get(bad_proj_url, headers=headers).status_code == 404
