import uuid
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Forbidden
from app.models import TeamMember, User

TeamRole = Literal["MEMBER", "ADMIN", "OWNER"]
ROLE_RANKS: dict[str, int] = {
    "MEMBER": 1,
    "ADMIN": 2,
    "OWNER": 3,
}


def check_team_role(
    db: Session,
    user: User,
    team_id: uuid.UUID,
    min_role: TeamRole = "MEMBER",
) -> TeamMember:
    """Verify that user is a member of the team and has at least `min_role`."""
    membership = db.scalar(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user.id,
        )
    )
    if membership is None:
        raise Forbidden("You do not have access to this team.")

    user_rank = ROLE_RANKS.get(membership.role, 0)
    required_rank = ROLE_RANKS.get(min_role, 1)

    if user_rank < required_rank:
        raise Forbidden(f"This action requires {min_role} role.")

    return membership
