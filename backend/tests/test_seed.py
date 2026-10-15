"""The development seed must be complete and idempotent."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.seed import seed_dev_data, seed_reference_data
from app.models import Branch, Plan, Subscription, TeamMember


def _row_counts(db: Session) -> dict[str, int]:
    return {
        table.name: db.scalar(select(func.count()).select_from(table)) or 0
        for table in Base.metadata.sorted_tables
    }


def test_seed_creates_reference_and_development_data(db_session: Session) -> None:
    plans = seed_reference_data(db_session)
    seed_dev_data(db_session, plans)

    assert set(plans) == {"FREE", "STANDARD"}
    assert _row_counts(db_session) == {
        "plans": 2,
        "teams": 1,
        "users": 3,
        "projects": 1,
        "subscriptions": 1,
        "team_members": 3,
        "repositories": 1,
        "branches": 1,
        "commits": 3,
    }
    roles = db_session.scalars(select(TeamMember.role).order_by(TeamMember.role)).all()
    assert roles == ["ADMIN", "MEMBER", "OWNER"]
    assert db_session.scalar(select(Subscription.status)) == "ACTIVE"
    assert db_session.scalar(select(Branch.is_deployment_branch)) is True


def test_seed_is_idempotent(db_session: Session) -> None:
    seed_dev_data(db_session, seed_reference_data(db_session))
    first = _row_counts(db_session)

    seed_dev_data(db_session, seed_reference_data(db_session))

    assert _row_counts(db_session) == first
    assert db_session.scalar(select(func.count()).select_from(Plan)) == 2
