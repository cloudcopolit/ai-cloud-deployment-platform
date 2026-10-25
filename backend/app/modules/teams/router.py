from uuid import UUID

from fastapi import APIRouter, status

from app.core.dependencies import DbSession
from app.modules.auth.dependencies import CurrentUser
from app.modules.teams import service
from app.modules.teams.schemas import TeamCreate, TeamMemberRead, TeamRead, TeamUpdate

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_model=list[TeamRead])
def get_user_teams(db: DbSession, user: CurrentUser) -> list[TeamRead]:
    return service.list_user_teams(db, user)


@router.post("", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
def create_new_team(data: TeamCreate, db: DbSession, user: CurrentUser) -> TeamRead:
    return service.create_team(db, user, data)


@router.get("/{team_id}", response_model=TeamRead)
def get_team_by_id(team_id: UUID, db: DbSession, user: CurrentUser) -> TeamRead:
    return service.get_team_details(db, team_id, user)


@router.patch("/{team_id}", response_model=TeamRead)
def update_team_by_id(
    team_id: UUID, data: TeamUpdate, db: DbSession, user: CurrentUser
) -> TeamRead:
    return service.update_team(db, team_id, user, data)


@router.get("/{team_id}/members", response_model=list[TeamMemberRead])
def get_team_members(team_id: UUID, db: DbSession, user: CurrentUser) -> list[TeamMemberRead]:
    return service.list_team_members(db, team_id, user)
