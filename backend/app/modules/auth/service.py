from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.integrations.github import GitHubProfile
from app.models import Plan, Subscription, Team, TeamMember, User


def upsert_github_user(db: Session, profile: GitHubProfile) -> User:
    """Create the user on first login, refresh their profile on later logins."""
    user = db.scalar(select(User).where(User.github_user_id == profile.github_id))
    is_new = user is None
    if user is None:
        candidate = User(github_user_id=profile.github_id)
        try:
            # Savepoint: a concurrent first login may insert the same github_user_id (I7).
            with db.begin_nested():
                db.add(candidate)
                db.flush()
            user = candidate
        except IntegrityError:
            user = db.scalar(select(User).where(User.github_user_id == profile.github_id))
            if user is None:  # pragma: no cover - the conflicting row must exist
                raise
            is_new = False

    user.name = profile.name
    user.avatar_url = profile.avatar_url

    # email is UNIQUE, so only set it if no other user already has it
    if profile.email:
        taken = (
            db.scalar(select(User.id).where(User.email == profile.email, User.id != user.id))
            if user.id
            else db.scalar(select(User.id).where(User.email == profile.email))
        )
        if taken is None:
            user.email = profile.email

    if is_new:
        has_team = db.scalar(select(TeamMember.team_id).where(TeamMember.user_id == user.id))
        if not has_team:
            team_name = f"{profile.name or profile.github_id}'s Team"
            team = Team(name=team_name)
            db.add(team)
            db.flush()

            membership = TeamMember(team_id=team.id, user_id=user.id, role="OWNER")
            db.add(membership)

            free_plan = db.scalar(select(Plan).where(Plan.code == "FREE"))
            if free_plan:
                now = datetime.now(UTC)
                sub = Subscription(
                    team_id=team.id,
                    plan_id=free_plan.id,
                    status="ACTIVE",
                    price_at_subscription=free_plan.monthly_price,
                    started_at=now,
                    current_period_start=now,
                )
                db.add(sub)

    db.commit()
    db.refresh(user)
    return user


def get_user_by_github_id(db: Session, github_user_id: str) -> User | None:
    return db.scalar(select(User).where(User.github_user_id == github_user_id))
