from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.dependencies import DbSession
from app.modules.auth.dependencies import CurrentUser
from app.modules.repositories import service
from app.modules.repositories.schemas import (
    AvailableRepository,
    BranchRead,
    CommitRead,
    DeploymentBranchUpdate,
    RepositoryConnect,
    RepositoryRead,
)

router = APIRouter(tags=["repositories"])


@router.get("/repositories/available", response_model=list[AvailableRepository])
def get_available_repos(user: CurrentUser) -> list[AvailableRepository]:
    return service.get_available_repositories(user)


@router.get("/projects/{project_id}/repositories", response_model=list[RepositoryRead])
def get_project_repositories(
    project_id: UUID, db: DbSession, user: CurrentUser
) -> list[RepositoryRead]:
    return service.list_project_repositories(db, project_id, user)


@router.post(
    "/projects/{project_id}/repositories",
    response_model=RepositoryRead,
    status_code=status.HTTP_201_CREATED,
)
def connect_repo_to_project(
    project_id: UUID, data: RepositoryConnect, db: DbSession, user: CurrentUser
) -> RepositoryRead:
    return service.connect_repository(db, project_id, user, data)


@router.get("/repositories/{repo_id}", response_model=RepositoryRead)
def get_repository_by_id(repo_id: UUID, db: DbSession, user: CurrentUser) -> RepositoryRead:
    return service.get_repository_details(db, repo_id, user)


@router.get("/repositories/{repo_id}/branches", response_model=list[BranchRead])
def get_repository_branches(repo_id: UUID, db: DbSession, user: CurrentUser) -> list[BranchRead]:
    return service.list_repository_branches(db, repo_id, user)


@router.put("/repositories/{repo_id}/deployment-branch", response_model=BranchRead)
def set_repo_deployment_branch(
    repo_id: UUID, data: DeploymentBranchUpdate, db: DbSession, user: CurrentUser
) -> BranchRead:
    return service.set_deployment_branch(db, repo_id, user, data)


@router.get("/repositories/{repo_id}/commits", response_model=list[CommitRead])
def get_repository_commits(
    repo_id: UUID,
    db: DbSession,
    user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[CommitRead]:
    return service.list_repository_commits(db, repo_id, user, limit, offset)
