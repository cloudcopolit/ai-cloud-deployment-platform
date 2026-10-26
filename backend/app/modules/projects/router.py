from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.dependencies import DbSession
from app.modules.auth.dependencies import CurrentUser
from app.modules.projects import service
from app.modules.projects.schemas import ProjectCreate, ProjectRead, ProjectUpdate

router = APIRouter(tags=["projects"])


@router.get("/projects", response_model=list[ProjectRead])
def get_user_projects(
    db: DbSession,
    user: CurrentUser,
    status_filter: str | None = Query(default="ACTIVE", alias="status"),
) -> list[ProjectRead]:
    return service.list_user_projects(db, user, status_filter)


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project_by_id(project_id: UUID, db: DbSession, user: CurrentUser) -> ProjectRead:
    return service.get_project_details(db, project_id, user)


@router.patch("/projects/{project_id}", response_model=ProjectRead)
def update_project_by_id(
    project_id: UUID, data: ProjectUpdate, db: DbSession, user: CurrentUser
) -> ProjectRead:
    return service.update_project(db, project_id, user, data)


@router.post("/projects/{project_id}/archive", response_model=ProjectRead)
def archive_project_by_id(project_id: UUID, db: DbSession, user: CurrentUser) -> ProjectRead:
    return service.archive_project(db, project_id, user)


@router.get("/teams/{team_id}/projects", response_model=list[ProjectRead])
def get_team_projects(
    team_id: UUID,
    db: DbSession,
    user: CurrentUser,
    status_filter: str | None = Query(default="ACTIVE", alias="status"),
) -> list[ProjectRead]:
    return service.list_team_projects(db, team_id, user, status_filter)


@router.post(
    "/teams/{team_id}/projects",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
def create_project_in_team(
    team_id: UUID, data: ProjectCreate, db: DbSession, user: CurrentUser
) -> ProjectRead:
    return service.create_project(db, team_id, user, data)
