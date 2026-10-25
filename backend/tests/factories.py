"""Small factories for tests (10 §7). Each returns flushed ORM rows."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models import Plan, Project, Subscription, Team, TeamMember, User

FRONTEND = "http://localhost:3000"
_ids = itertools.count(50_000)


def make_user(db: Session, name: str = "User") -> User:
    n = next(_ids)
    user = User(github_user_id=str(n), name=f"{name} {n}", email=f"user{n}@example.com")
    db.add(user)
    db.flush()
    return user


def make_team(
    db: Session, members: dict[User, str], *, max_projects: int = 10, name: str = "Team"
) -> Team:
    team = Team(name=f"{name} {next(_ids)}")
    db.add(team)
    db.flush()
    for user, role in members.items():
        db.add(TeamMember(team_id=team.id, user_id=user.id, role=role))
    plan = Plan(
        code=f"TEST_{next(_ids)}",
        name="Test plan",
        monthly_price=Decimal("0.00"),
        limits={"max_projects": max_projects, "max_team_members": 10},
    )
    db.add(plan)
    db.flush()
    now = datetime.now(UTC)
    db.add(
        Subscription(
            team_id=team.id,
            plan_id=plan.id,
            status="ACTIVE",
            price_at_subscription=Decimal("0.00"),
            started_at=now,
            current_period_start=now,
        )
    )
    db.flush()
    return team


def make_project(db: Session, team: Team, name: str = "Project") -> Project:
    project = Project(team_id=team.id, name=f"{name} {next(_ids)}", status="ACTIVE")
    db.add(project)
    db.flush()
    return project


def headers_for(user: User) -> dict[str, str]:
    """Bearer auth + the allowed Origin, as the browser frontend would send."""
    return {"Authorization": f"Bearer {create_access_token(user.id)}", "Origin": FRONTEND}
