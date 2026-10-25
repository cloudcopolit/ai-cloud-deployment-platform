import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import ACCESS_COOKIE, create_access_token
from app.models import Plan, Subscription, Team, TeamMember, User

FRONTEND = "http://localhost:3000"


@pytest.fixture
def owner_user(db_session: Session) -> User:
    user = User(github_user_id="2001", name="Alice Boss", email="alice.boss@example.com")
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def member_user(db_session: Session) -> User:
    user = User(github_user_id="2002", name="Bob Worker", email="bob.worker@example.com")
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def setup_team(db_session: Session, owner_user: User, member_user: User) -> Team:
    team = Team(name="Engineering Team")
    db_session.add(team)
    db_session.flush()

    m1 = TeamMember(team_id=team.id, user_id=owner_user.id, role="OWNER")
    m2 = TeamMember(team_id=team.id, user_id=member_user.id, role="MEMBER")
    db_session.add_all([m1, m2])

    free_plan = Plan(
        code=f"FREE_{uuid.uuid4().hex[:6]}",
        name="Free",
        monthly_price=Decimal("0.00"),
        limits={"max_projects": 2},
    )
    db_session.add(free_plan)
    db_session.flush()

    from datetime import UTC, datetime

    now = datetime.now(UTC)
    sub = Subscription(
        team_id=team.id,
        plan_id=free_plan.id,
        status="ACTIVE",
        price_at_subscription=Decimal("0.00"),
        started_at=now,
        current_period_start=now,
    )
    db_session.add(sub)
    db_session.commit()
    return team


def auth_client(client: TestClient, user: User) -> TestClient:
    token = create_access_token(user.id)
    client.cookies.set(ACCESS_COOKIE, token)
    return client


def test_list_and_create_teams(
    client: TestClient, db_session: Session, owner_user: User, setup_team: Team
) -> None:
    auth_client(client, owner_user)

    # List teams
    res = client.get("/teams")
    assert res.status_code == 200
    teams = res.json()
    assert len(teams) >= 1
    assert any(t["id"] == str(setup_team.id) for t in teams)

    # Create team
    create_res = client.post(
        "/teams",
        json={"name": "New Ventures"},
        headers={"Origin": FRONTEND},
    )
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["name"] == "New Ventures"
    assert created["role"] == "OWNER"


def test_project_crud_and_permissions(
    client: TestClient,
    db_session: Session,
    owner_user: User,
    member_user: User,
    setup_team: Team,
) -> None:
    # 1. Member cannot create project (requires ADMIN+)
    auth_client(client, member_user)
    denied = client.post(
        f"/teams/{setup_team.id}/projects",
        json={"name": "Member Project"},
        headers={"Origin": FRONTEND},
    )
    assert denied.status_code == 403

    # 2. Owner creates project
    auth_client(client, owner_user)
    res = client.post(
        f"/teams/{setup_team.id}/projects",
        json={"name": "Payment Gateway", "description": "Handles payments"},
        headers={"Origin": FRONTEND},
    )
    assert res.status_code == 201
    project = res.json()
    project_id = project["id"]
    assert project["name"] == "Payment Gateway"
    assert project["status"] == "ACTIVE"

    # 3. List projects
    list_res = client.get(f"/teams/{setup_team.id}/projects")
    assert list_res.status_code == 200
    assert any(p["id"] == project_id for p in list_res.json())

    # 4. Get project details
    get_res = client.get(f"/projects/{project_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Payment Gateway"

    # 5. Update project
    patch_res = client.patch(
        f"/projects/{project_id}",
        json={"name": "Payment Service v2"},
        headers={"Origin": FRONTEND},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Payment Service v2"

    # 6. Archive project
    archive_res = client.post(
        f"/projects/{project_id}/archive",
        headers={"Origin": FRONTEND},
    )
    assert archive_res.status_code == 200
    assert archive_res.json()["status"] == "ARCHIVED"


def test_project_quota_exceeded(
    client: TestClient, db_session: Session, owner_user: User, setup_team: Team
) -> None:
    auth_client(client, owner_user)

    # Create project 1 (limit is 2)
    p1 = client.post(
        f"/teams/{setup_team.id}/projects",
        json={"name": "App One"},
        headers={"Origin": FRONTEND},
    )
    assert p1.status_code == 201

    # Create project 2
    p2 = client.post(
        f"/teams/{setup_team.id}/projects",
        json={"name": "App Two"},
        headers={"Origin": FRONTEND},
    )
    assert p2.status_code == 201

    # Create project 3 (should exceed quota)
    p3 = client.post(
        f"/teams/{setup_team.id}/projects",
        json={"name": "App Three"},
        headers={"Origin": FRONTEND},
    )
    assert p3.status_code == 403
    assert p3.json()["error"]["code"] == "PLAN_LIMIT_REACHED"


def test_repository_lifecycle(
    client: TestClient, db_session: Session, owner_user: User, setup_team: Team
) -> None:
    auth_client(client, owner_user)

    # Create a project first
    p_res = client.post(
        f"/teams/{setup_team.id}/projects",
        json={"name": "Inventory App"},
        headers={"Origin": FRONTEND},
    )
    project_id = p_res.json()["id"]

    # Connect repository
    repo_res = client.post(
        f"/projects/{project_id}/repositories",
        json={
            "github_repository_id": "987654",
            "owner": "acme",
            "name": "inventory-app",
            "url": "https://github.com/acme/inventory-app",
            "default_branch": "main",
        },
        headers={"Origin": FRONTEND},
    )
    assert repo_res.status_code == 201
    repo = repo_res.json()
    repo_id = repo["id"]
    assert repo["name"] == "inventory-app"
    assert repo["default_branch"] == "main"
    assert repo["deployment_branch"] == "main"

    # Duplicate connect should conflict
    dup_res = client.post(
        f"/projects/{project_id}/repositories",
        json={
            "github_repository_id": "987654",
            "owner": "acme",
            "name": "inventory-app",
            "url": "https://github.com/acme/inventory-app",
            "default_branch": "main",
        },
        headers={"Origin": FRONTEND},
    )
    assert dup_res.status_code == 409

    # List project repositories
    list_repos = client.get(f"/projects/{project_id}/repositories")
    assert list_repos.status_code == 200
    assert len(list_repos.json()) == 1

    # List branches
    branches_res = client.get(f"/repositories/{repo_id}/branches")
    assert branches_res.status_code == 200
    branches = branches_res.json()
    assert len(branches) >= 1
    assert any(b["name"] == "main" and b["is_deployment_branch"] for b in branches)

    # Change deployment branch
    switch_res = client.put(
        f"/repositories/{repo_id}/deployment-branch",
        json={"branch_name": "release"},
        headers={"Origin": FRONTEND},
    )
    assert switch_res.status_code == 200
    assert switch_res.json()["name"] == "release"
    assert switch_res.json()["is_deployment_branch"] is True

    # List commits
    commits_res = client.get(f"/repositories/{repo_id}/commits")
    assert commits_res.status_code == 200
    assert len(commits_res.json()) >= 1

    # Available repositories
    avail_res = client.get("/repositories/available")
    assert avail_res.status_code == 200
    assert len(avail_res.json()) >= 3

    # Repository details
    repo_get = client.get(f"/repositories/{repo_id}")
    assert repo_get.status_code == 200
    assert repo_get.json()["id"] == repo_id

    # Repository not found
    bad_repo = client.get(f"/repositories/{uuid.uuid4()}")
    assert bad_repo.status_code == 404

    # Team details
    team_res = client.get(f"/teams/{setup_team.id}")
    assert team_res.status_code == 200
    assert team_res.json()["name"] == "Engineering Team"
    assert team_res.json()["member_count"] >= 1

    # Team update
    team_update = client.patch(
        f"/teams/{setup_team.id}",
        json={"name": "Engineering Alpha"},
        headers={"Origin": FRONTEND},
    )
    assert team_update.status_code == 200
    assert team_update.json()["name"] == "Engineering Alpha"

    # List team members
    members_res = client.get(f"/teams/{setup_team.id}/members")
    assert members_res.status_code == 200
    members = members_res.json()
    assert len(members) >= 2
    assert any(m["role"] == "OWNER" for m in members)
