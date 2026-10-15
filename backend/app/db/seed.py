from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    Branch,
    Commit,
    Plan,
    Project,
    Repository,
    Subscription,
    Team,
    TeamMember,
    User,
)


def get_or_create(db: Session, model, lookup: dict, defaults: dict | None = None):
    """Return the row matching `lookup`, creating it if it does not exist."""
    obj = db.scalar(select(model).filter_by(**lookup))
    if obj is None:
        obj = model(**lookup, **(defaults or {}))
        db.add(obj)
        db.flush()  # assigns the id without committing
    return obj


def seed_reference_data(db: Session) -> dict[str, Plan]:
    free = get_or_create(
        db,
        Plan,
        {"code": "FREE"},
        {
            "name": "Free",
            "monthly_price": Decimal("0.00"),
            "limits": {"max_projects": 1, "max_team_members": 3, "max_deployments_per_month": 10},
        },
    )
    standard = get_or_create(
        db,
        Plan,
        {"code": "STANDARD"},
        {
            "name": "Standard",
            "monthly_price": Decimal("29.00"),
            "limits": {
                "max_projects": 10,
                "max_team_members": 10,
                "max_deployments_per_month": 200,
            },
        },
    )
    return {"FREE": free, "STANDARD": standard}


def seed_dev_data(db: Session, plans: dict[str, Plan]) -> None:
    now = datetime.now(UTC)

    alice = get_or_create(
        db, User, {"github_user_id": "1001"}, {"name": "Alice Owner", "email": "alice@example.com"}
    )
    bob = get_or_create(
        db, User, {"github_user_id": "1002"}, {"name": "Bob Developer", "email": "bob@example.com"}
    )
    carol = get_or_create(
        db, User, {"github_user_id": "1003"}, {"name": "Carol Developer", "email": None}
    )  # hidden email

    team = get_or_create(db, Team, {"name": "Acme Startup"})

    get_or_create(db, TeamMember, {"team_id": team.id, "user_id": alice.id}, {"role": "OWNER"})
    get_or_create(db, TeamMember, {"team_id": team.id, "user_id": bob.id}, {"role": "ADMIN"})
    get_or_create(db, TeamMember, {"team_id": team.id, "user_id": carol.id}, {"role": "MEMBER"})

    get_or_create(
        db,
        Subscription,
        {"team_id": team.id, "plan_id": plans["FREE"].id},
        {
            "status": "ACTIVE",
            "price_at_subscription": plans["FREE"].monthly_price,
            "started_at": now,
            "current_period_start": now,
            "current_period_end": now + timedelta(days=30),
        },
    )

    project = get_or_create(
        db,
        Project,
        {"team_id": team.id, "name": "Demo Shop"},
        {"description": "Sample e-commerce app"},
    )

    repo = get_or_create(
        db,
        Repository,
        {"project_id": project.id, "github_repository_id": "900001"},
        {
            "owner": "acme",
            "name": "demo-shop",
            "url": "https://github.com/acme/demo-shop",
            "default_branch": "main",
        },
    )

    main = get_or_create(
        db,
        Branch,
        {"repository_id": repo.id, "name": "main"},
        {"is_default": True, "is_deployment_branch": True},
    )

    commits = [
        ("a1b2c3d4e5f60718293a4b5c6d7e8f9012345678", "Initial commit", alice),
        ("b2c3d4e5f60718293a4b5c6d7e8f901234567890", "Add backend API", bob),
        ("c3d4e5f60718293a4b5c6d7e8f90123456789012", "Add Dockerfile", bob),
    ]
    for i, (sha, message, author) in enumerate(commits):
        get_or_create(
            db,
            Commit,
            {"repository_id": repo.id, "sha": sha},
            {
                "branch_id": main.id,
                "message": message,
                "author_name": author.name,
                "author_email": author.email,
                "committed_at": now - timedelta(days=3 - i),
            },
        )


def main() -> None:
    with SessionLocal() as db:
        plans = seed_reference_data(db)
        seed_dev_data(db, plans)
        db.commit()
    print("Seed completed.")


if __name__ == "__main__":
    main()
