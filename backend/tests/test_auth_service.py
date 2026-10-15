"""User creation and refresh on GitHub sign-in."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.integrations.github import GitHubProfile
from app.models import User
from app.modules.auth import service


def _profile(**overrides) -> GitHubProfile:
    values = {
        "github_id": "2002",
        "name": "Dana",
        "email": "dana@example.com",
        "avatar_url": "https://avatars.example.com/2002",
    }
    return GitHubProfile(**(values | overrides))


def test_first_login_creates_the_user(db_session: Session) -> None:
    user = service.upsert_github_user(db_session, _profile())

    assert user.id is not None
    assert (user.github_user_id, user.name, user.email) == ("2002", "Dana", "dana@example.com")
    assert service.get_user_by_github_id(db_session, "2002") == user


def test_later_login_refreshes_profile_without_duplicating(db_session: Session) -> None:
    first = service.upsert_github_user(db_session, _profile())

    second = service.upsert_github_user(
        db_session, _profile(name="Dana Renamed", avatar_url=None, email="new@example.com")
    )

    assert second.id == first.id
    assert (second.name, second.avatar_url, second.email) == (
        "Dana Renamed",
        None,
        "new@example.com",
    )
    assert db_session.scalar(select(func.count()).select_from(User)) == 1


def test_email_already_used_by_another_user_is_not_taken(db_session: Session) -> None:
    db_session.add(User(github_user_id="1", name="Owner", email="shared@example.com"))
    db_session.commit()

    new_user = service.upsert_github_user(db_session, _profile(email="shared@example.com"))
    db_session.add(User(github_user_id="3", name="Other", email="other@example.com"))
    db_session.commit()
    existing_user = service.upsert_github_user(
        db_session, _profile(email="other@example.com", name="Dana again")
    )

    assert new_user.email is None
    assert existing_user.id == new_user.id
    assert existing_user.email is None


def test_hidden_email_keeps_the_stored_one(db_session: Session) -> None:
    service.upsert_github_user(db_session, _profile())

    user = service.upsert_github_user(db_session, _profile(email=None))

    assert user.email == "dana@example.com"


def test_unknown_github_id_returns_none(db_session: Session) -> None:
    assert service.get_user_by_github_id(db_session, "does-not-exist") is None
