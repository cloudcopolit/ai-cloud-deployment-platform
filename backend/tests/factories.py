"""Small factories for tests (10 §7). Each returns flushed ORM rows."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models import Plan, Project, Subscription, Team, TeamMember, User

if TYPE_CHECKING:
    from tests.fakes import FakeGitHub

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


# ───────────────────────── analysis jobs ─────────────────────────

FASTAPI_FILES = {
    "requirements.txt": "fastapi==0.115.0\nuvicorn==0.32.0\npsycopg==3.2.3\n",
    "main.py": 'from fastapi import FastAPI\napp = FastAPI()\n@app.get("/health")\ndef h():\n'
    "    return {}\n",
    "Dockerfile": 'FROM python:3.12-slim\nEXPOSE 8000\nCMD ["uvicorn", "main:app"]\n',
}


def connected_repository(
    db: Session, fake: FakeGitHub, owner_user: User, files: dict[str, str] | None = None
):
    """A team, project and repository connected from the fake GitHub, with one commit."""
    from app.models import Branch, Commit, Repository

    team = make_team(db, {owner_user: "OWNER"})
    project = make_project(db, team)
    remote = fake.add_repo("acme", f"svc-{next(_ids)}")
    sha = remote.add_commit("main", "init", files or FASTAPI_FILES)
    repo = Repository(
        project_id=project.id,
        github_repository_id=str(remote.github_id),
        owner=remote.owner,
        name=remote.name,
        url=f"https://github.com/{remote.owner}/{remote.name}",
        default_branch="main",
    )
    db.add(repo)
    db.flush()
    branch = Branch(repository_id=repo.id, name="main", is_default=True, is_deployment_branch=True)
    db.add(branch)
    db.flush()
    db.add(
        Commit(
            repository_id=repo.id,
            branch_id=branch.id,
            sha=sha,
            message="init",
            committed_at=datetime.now(UTC),
        )
    )
    db.commit()
    return team, project, repo


def run_queued_job_inline(db: Session, fake: FakeGitHub, analysis_id) -> str | None:
    """Claim and run a queued analysis in-process, inside the test transaction."""
    from contextlib import nullcontext

    from app.core.config import settings
    from app.jobs import queue
    from app.jobs.runner import execute

    old = settings.worker_heartbeat_interval_s
    settings.worker_heartbeat_interval_s = 3600  # no concurrent heartbeat on the shared session
    try:
        assert queue.claim_next(db, "inline") == analysis_id
        return execute(
            analysis_id,
            "inline",
            session_factory=lambda: nullcontext(db),  # type: ignore[arg-type,return-value]
            github=fake.client(),
        )
    finally:
        settings.worker_heartbeat_interval_s = old
