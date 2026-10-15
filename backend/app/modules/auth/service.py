from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.github import GitHubProfile
from app.models import User


def upsert_github_user(db: Session, profile: GitHubProfile) -> User:
    """Create the user on first login, refresh their profile on later logins."""
    user = db.scalar(select(User).where(User.github_user_id == profile.github_id))
    if user is None:
        user = User(github_user_id=profile.github_id)
        db.add(user)

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

    db.commit()
    db.refresh(user)
    return user


def get_user_by_github_id(db: Session, github_user_id: str) -> User | None:
    return db.scalar(select(User).where(User.github_user_id == github_user_id))
