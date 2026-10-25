import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Branch, Commit, Project, Repository, Team, TeamMember, User
from tests.factories import FASTAPI_FILES, run_queued_job_inline
from tests.fakes import FakeGitHub


def _setup_analyzed_repo(
    client: TestClient, db_session: Session, fake_github: FakeGitHub
) -> tuple[User, Team, Project, Repository, str, str]:
    user = User(
        github_user_id="arch-tester-1",
        name="Architecture Tester",
        email="arch@example.com",
    )
    db_session.add(user)
    db_session.flush()

    team = Team(name="Architecture Team")
    db_session.add(team)
    db_session.flush()

    membership = TeamMember(team_id=team.id, user_id=user.id, role="OWNER")
    db_session.add(membership)

    project = Project(team_id=team.id, name="Arch Project")
    db_session.add(project)
    db_session.flush()

    repo = Repository(
        project_id=project.id,
        github_repository_id="88801",
        owner="cloudpilot-test",
        name="cloudpilot-fastapi-service",
        url="https://github.com/cloudpilot-test/cloudpilot-fastapi-service",
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
        sha=fake_github.add_repo("cloudpilot-test", "cloudpilot-fastapi-service").add_commit(
            "main", "init", FASTAPI_FILES
        ),
        message="feat: production api service",
        author_name="Arch Dev",
        author_email="archdev@example.com",
        committed_at=datetime.now(UTC),
    )
    db_session.add(commit)
    db_session.commit()

    token_resp = client.post(
        "/auth/dev-login",
        json={"github_user_id": user.github_user_id},
        headers={"Origin": "http://localhost:3000"},
    )
    token = token_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Origin": "http://localhost:3000"}

    # Run analysis
    analysis_resp = client.post(
        f"/repositories/{repo.id}/analyses",
        json={},
        headers=headers,
    )
    assert analysis_resp.status_code == 202
    analysis_id = analysis_resp.json()["id"]
    assert run_queued_job_inline(db_session, fake_github, uuid.UUID(analysis_id)) == "SUCCESS"

    return user, team, project, repo, token, analysis_id


def test_generate_and_retrieve_architecture(
    client: TestClient, db_session: Session, fake_github: FakeGitHub
) -> None:
    _, _, project, _, token, analysis_id = _setup_analyzed_repo(client, db_session, fake_github)
    headers = {"Authorization": f"Bearer {token}", "Origin": "http://localhost:3000"}

    # Generate Architecture Plan
    resp = client.post(
        f"/analyses/{analysis_id}/architectures",
        json={"region": "us-east-1"},
        headers=headers,
    )
    assert resp.status_code == 201
    plan_data = resp.json()
    assert plan_data["version_number"] == 1
    assert plan_data["status"] == "VALIDATED"
    assert plan_data["monthly_cost"] > 0
    arch_id = plan_data["architecture_id"]

    # Verify components
    components = plan_data["architecture_data"]["components"]
    component_types = [c["type"] for c in components]
    assert "vpc" in component_types
    assert "alb" in component_types
    assert "ecs_service" in component_types

    # Retrieve Version
    get_ver_resp = client.get(
        f"/architectures/{arch_id}/versions/1",
        headers=headers,
    )
    assert get_ver_resp.status_code == 200
    assert get_ver_resp.json()["id"] == plan_data["id"]

    # List Project Architectures
    list_resp = client.get(f"/projects/{project.id}/architectures", headers=headers)
    assert list_resp.status_code == 200
    arch_list = list_resp.json()
    assert len(arch_list) == 1
    assert arch_list[0]["versions_count"] == 1
    assert arch_list[0]["latest_version"]["version_number"] == 1

    # Generate Version 2
    v2_resp = client.post(
        f"/analyses/{analysis_id}/architectures",
        json={"region": "us-west-2"},
        headers=headers,
    )
    assert v2_resp.status_code == 201
    v2_data = v2_resp.json()
    assert v2_data["version_number"] == 2

    # Check that Version 1 is now marked SUPERSEDED
    v1_check = client.get(
        f"/architectures/{arch_id}/versions/1",
        headers=headers,
    )
    assert v1_check.status_code == 200
    assert v1_check.json()["status"] == "SUPERSEDED"


def test_architecture_permissions(
    client: TestClient, db_session: Session, fake_github: FakeGitHub
) -> None:
    _, _, _, _, _, analysis_id = _setup_analyzed_repo(client, db_session, fake_github)

    # Outsider
    outsider = User(
        github_user_id="outsider-arch-user",
        name="Outsider",
        email="outsider_arch@example.com",
    )
    db_session.add(outsider)
    db_session.commit()

    token_resp = client.post(
        "/auth/dev-login",
        json={"github_user_id": outsider.github_user_id},
        headers={"Origin": "http://localhost:3000"},
    )
    outsider_token = token_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {outsider_token}", "Origin": "http://localhost:3000"}

    resp = client.post(
        f"/analyses/{analysis_id}/architectures",
        json={},
        headers=headers,
    )
    # Foreign tenants must not learn that the object exists (08 §3).
    assert resp.status_code == 404


def test_architecture_not_found_handling(
    client: TestClient, db_session: Session, fake_github: FakeGitHub
) -> None:
    import uuid

    _, _, _, _, token, _analysis_id = _setup_analyzed_repo(client, db_session, fake_github)
    headers = {"Authorization": f"Bearer {token}", "Origin": "http://localhost:3000"}

    # 404 for unknown analysis
    bad_arch_url = f"/analyses/{uuid.uuid4()}/architectures"
    assert client.post(bad_arch_url, json={}, headers=headers).status_code == 404

    # 404 for unknown architecture
    bad_ver_url = f"/architectures/{uuid.uuid4()}/versions/1"
    assert client.get(bad_ver_url, headers=headers).status_code == 404

    # 404 for unknown project architecture list
    bad_proj_arch_url = f"/projects/{uuid.uuid4()}/architectures"
    assert client.get(bad_proj_arch_url, headers=headers).status_code == 404
