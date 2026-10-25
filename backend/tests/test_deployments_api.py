from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import AWSAccount, Branch, Commit, Project, Repository, Team, TeamMember, User


def _setup_deployment_env(client: TestClient, db_session: Session) -> dict:
    user = User(
        github_user_id="deploy-tester-1",
        name="Deploy Tester",
        email="deploy@example.com",
    )
    db_session.add(user)
    db_session.flush()

    team = Team(name="Deploy Team")
    db_session.add(team)
    db_session.flush()

    membership = TeamMember(team_id=team.id, user_id=user.id, role="OWNER")
    db_session.add(membership)

    project = Project(team_id=team.id, name="Production Store")
    db_session.add(project)
    db_session.flush()

    repo = Repository(
        project_id=project.id,
        github_repository_id="77701",
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
        sha="deadbeef112233445566778899aabbccddeeff00",
        message="feat: production release ready for aws",
        author_name="Dev Deployer",
        author_email="deployer@example.com",
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

    # 1. Run Analysis
    analysis_resp = client.post(f"/repositories/{repo.id}/analyses", json={}, headers=headers)
    assert analysis_resp.status_code == 202
    analysis_id = analysis_resp.json()["id"]

    # 2. Generate Architecture
    arch_resp = client.post(
        f"/analyses/{analysis_id}/architectures", json={"region": "us-east-1"}, headers=headers
    )
    assert arch_resp.status_code == 201
    arch_version_id = arch_resp.json()["id"]

    # 3. Connect AWS Account
    aws_resp = client.post(
        f"/teams/{team.id}/aws-accounts",
        json={
            "aws_account_id": "123456789012",
            "role_arn": "arn:aws:iam::123456789012:role/CloudPilotDeploymentRole",
            "default_region": "us-east-1",
        },
        headers=headers,
    )
    assert aws_resp.status_code == 201
    aws_account_id = aws_resp.json()["id"]

    return {
        "user": user,
        "team": team,
        "project": project,
        "repo": repo,
        "token": token,
        "headers": headers,
        "arch_version_id": arch_version_id,
        "aws_account_id": aws_account_id,
    }


def _mark_aws_account_verified(db_session: Session, account_id: str) -> None:
    account = db_session.get(AWSAccount, account_id)
    assert account is not None
    account.status = "ACTIVE"
    account.last_verified_at = datetime.now(UTC)
    db_session.commit()


def test_connect_and_list_aws_accounts(client: TestClient, db_session: Session) -> None:
    env = _setup_deployment_env(client, db_session)
    team = env["team"]
    headers = env["headers"]

    list_resp = client.get(f"/teams/{team.id}/aws-accounts", headers=headers)
    assert list_resp.status_code == 200
    accounts = list_resp.json()
    assert len(accounts) >= 1
    acc = accounts[0]
    assert acc["aws_account_id"] == "123456789012"
    assert acc["status"] == "PENDING_VERIFICATION"
    assert acc["last_verified_at"] is None
    assert acc["external_id"].startswith("cp-")


@pytest.mark.parametrize(
    "role_arn",
    [
        "arn:aws:sts::123456789012:assumed-role/CloudPilotDeploymentRole/session",
        "arn:aws:iam::210987654321:role/CloudPilotDeploymentRole",
    ],
)
def test_aws_account_rejects_invalid_or_mismatched_role_arn(
    client: TestClient,
    db_session: Session,
    role_arn: str,
) -> None:
    env = _setup_deployment_env(client, db_session)

    response = client.post(
        f"/teams/{env['team'].id}/aws-accounts",
        json={
            "aws_account_id": "123456789012",
            "role_arn": role_arn,
            "default_region": "us-east-1",
        },
        headers=env["headers"],
    )

    assert response.status_code == 422
    assert db_session.query(AWSAccount).filter_by(team_id=env["team"].id).count() == 1


def test_deployment_plan_requires_verified_aws_account(
    client: TestClient, db_session: Session
) -> None:
    env = _setup_deployment_env(client, db_session)

    response = client.post(
        f"/projects/{env['project'].id}/deployments",
        json={
            "repository_id": str(env["repo"].id),
            "architecture_version_id": env["arch_version_id"],
            "aws_account_id": env["aws_account_id"],
        },
        headers=env["headers"],
    )

    assert response.status_code == 400
    assert "not active" in response.json()["error"]["message"].lower()


def test_apply_fails_closed_without_aws_deployment_worker(
    client: TestClient, db_session: Session
) -> None:
    env = _setup_deployment_env(client, db_session)
    project = env["project"]
    repo = env["repo"]
    headers = env["headers"]
    arch_version_id = env["arch_version_id"]
    aws_account_id = env["aws_account_id"]

    # This marks the test fixture verified; no real AWS call is made.
    _mark_aws_account_verified(db_session, aws_account_id)

    plan_resp = client.post(
        f"/projects/{project.id}/deployments",
        json={
            "repository_id": str(repo.id),
            "architecture_version_id": arch_version_id,
            "aws_account_id": aws_account_id,
        },
        headers=headers,
    )
    assert plan_resp.status_code == 201
    plan_data = plan_resp.json()
    deployment_id = plan_data["id"]
    assert plan_data["status"] == "QUEUED"
    assert plan_data["approval"] is not None
    assert plan_data["approval"]["status"] == "PENDING"
    assert len(plan_data["steps"]) == 5
    assert all(s["status"] == "QUEUED" for s in plan_data["steps"])

    unapproved_apply = client.post(
        f"/deployments/{deployment_id}/apply",
        headers=headers,
    )
    assert unapproved_apply.status_code == 403
    assert "human approval" in unapproved_apply.json()["error"]["message"].lower()

    approval_resp = client.post(
        f"/deployments/{deployment_id}/approve",
        json={
            "decision": "APPROVED",
            "reason": "Architecture and cost validated. Approved for AWS staging deploy.",
        },
        headers=headers,
    )
    assert approval_resp.status_code == 200
    approval_data = approval_resp.json()
    assert approval_data["status"] == "APPROVED"
    assert approval_data["approved_by"] is not None

    apply_resp = client.post(
        f"/deployments/{deployment_id}/apply",
        headers=headers,
    )
    assert apply_resp.status_code == 503
    assert "no aws changes were made" in apply_resp.json()["error"]["message"].lower()

    detail_resp = client.get(f"/deployments/{deployment_id}", headers=headers)
    assert detail_resp.status_code == 200
    deployment_data = detail_resp.json()
    assert deployment_data["id"] == deployment_id
    assert deployment_data["status"] == "QUEUED"
    assert deployment_data["started_at"] is None
    assert deployment_data["completed_at"] is None
    assert deployment_data["live_endpoint"] is None
    assert deployment_data["resources"] == []
    assert all(step["status"] == "QUEUED" for step in deployment_data["steps"])

    proj_deployments = client.get(f"/projects/{project.id}/deployments", headers=headers)
    assert proj_deployments.status_code == 200
    assert len(proj_deployments.json()) >= 1


def test_deployment_rejection_cancels_steps(client: TestClient, db_session: Session) -> None:
    env = _setup_deployment_env(client, db_session)
    _mark_aws_account_verified(db_session, env["aws_account_id"])
    project = env["project"]
    repo = env["repo"]
    headers = env["headers"]

    plan_resp = client.post(
        f"/projects/{project.id}/deployments",
        json={
            "repository_id": str(repo.id),
            "architecture_version_id": env["arch_version_id"],
            "aws_account_id": env["aws_account_id"],
        },
        headers=headers,
    )
    deployment_id = plan_resp.json()["id"]

    # Reject
    reject_resp = client.post(
        f"/deployments/{deployment_id}/approve",
        json={"decision": "REJECTED", "reason": "Cost exceeds current budget"},
        headers=headers,
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "REJECTED"

    # Deployment should now be CANCELLED
    detail = client.get(f"/deployments/{deployment_id}", headers=headers).json()
    assert detail["status"] == "CANCELLED"
    assert all(s["status"] == "SKIPPED" for s in detail["steps"])
