from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import DbSession
from app.integrations.github_app import GitHubClient, get_github_client
from app.modules.auth.dependencies import CurrentUser
from app.modules.repositories import service
from app.modules.repositories.schemas import (
    BranchRead,
    CommitRead,
    DeploymentBranchUpdate,
    GitHubAccessRead,
    RepositoryConnect,
    RepositoryRead,
)

router = APIRouter(tags=["repositories"])

GitHub = Annotated[GitHubClient, Depends(get_github_client)]


@router.get("/github/access", response_model=GitHubAccessRead)
def get_github_access(_: CurrentUser, github: GitHub) -> GitHubAccessRead:
    """Which GitHub access modes this deployment has (App, token, anonymous) and the quota."""
    return service.github_access(github)


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
    project_id: UUID, data: RepositoryConnect, db: DbSession, user: CurrentUser, github: GitHub
) -> RepositoryRead:
    return service.connect_repository(db, github, project_id, user, data)


@router.get("/repositories/{repo_id}", response_model=RepositoryRead)
def get_repository_by_id(repo_id: UUID, db: DbSession, user: CurrentUser) -> RepositoryRead:
    return service.get_repository_details(db, repo_id, user)


@router.post("/repositories/{repo_id}/sync", response_model=RepositoryRead)
def sync_repository(
    repo_id: UUID, db: DbSession, user: CurrentUser, github: GitHub
) -> RepositoryRead:
    return service.sync_repository(db, github, repo_id, user)


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
    github: GitHub,
    branch: Annotated[str | None, Query(max_length=255)] = None,
    refresh: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=500)] = 0,
) -> list[CommitRead]:
    """Commits of ``branch`` (default: the deployment branch). ``refresh=true`` reads GitHub."""
    return service.list_repository_commits(
        db, github, repo_id, user, branch_name=branch, refresh=refresh, limit=limit, offset=offset
    )
