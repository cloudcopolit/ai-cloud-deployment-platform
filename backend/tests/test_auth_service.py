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


def test_concurrent_first_login_reuses_the_row_instead_of_failing(
    db_session: Session, monkeypatch
) -> None:
    """I7: two simultaneous first logins must not end in an IntegrityError (HTTP 500)."""
    existing = User(github_user_id="2002", name="Inserted by the other request")
    db_session.add(existing)
    db_session.flush()

    real_scalar = db_session.scalar
    calls = {"n": 0}

    def first_lookup_misses(statement, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:  # the other request had not committed when we looked
            return None
        return real_scalar(statement, *args, **kwargs)

    monkeypatch.setattr(db_session, "scalar", first_lookup_misses)

    user = service.upsert_github_user(db_session, _profile())

    assert user.id == existing.id
    assert user.name == "Dana"
    count = real_scalar(select(func.count()).select_from(User).where(User.github_user_id == "2002"))
    assert count == 1
