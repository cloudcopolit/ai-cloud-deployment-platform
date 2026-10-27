import uuid
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Forbidden, NotFound
from app.models import Project, Repository, TeamMember, User

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
    """Verify that user is a member of the team and has at least `min_role`.

    Non-members get 404, not 403, so other tenants' objects stay invisible (08 §3).
    Members with too low a role get 403.
    """
    membership = db.scalar(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user.id,
        )
    )
    if membership is None:
        raise NotFound("Not found.")

    user_rank = ROLE_RANKS.get(membership.role, 0)
    required_rank = ROLE_RANKS.get(min_role, 1)

    if user_rank < required_rank:
        raise Forbidden(f"This action requires {min_role} role.")

    return membership


def get_project_for_user(
    db: Session, user: User, project_id: uuid.UUID, min_role: TeamRole = "MEMBER"
) -> Project:
    """The project, if the caller's team owns it and their role is high enough (else 404/403)."""
    project = db.get(Project, project_id)
    if project is None:
        raise NotFound("Project not found.")
    check_team_role(db, user, project.team_id, min_role)
    return project


def get_repository_for_user(
    db: Session, user: User, repository_id: uuid.UUID, min_role: TeamRole = "MEMBER"
) -> tuple[Repository, Project]:
    """The repository and its project, scoped to the caller's team (else 404/403)."""
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise NotFound("Repository not found.")
    project = get_project_for_user(db, user, repository.project_id, min_role)
    return repository, project
