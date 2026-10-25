from uuid import UUID

from fastapi import APIRouter, status

from app.core.dependencies import DbSession
from app.modules.auth.dependencies import CurrentUser
from app.modules.deployments import service
from app.modules.deployments.schemas import (
    ApprovalDecisionRequest,
    ApprovalRead,
    AWSAccountConnectRequest,
    AWSAccountRead,
    DeploymentCreateRequest,
    DeploymentRead,
)

router = APIRouter(tags=["deployments"])


# ───────────────────────── AWS Accounts ─────────────────────────


@router.post(
    "/teams/{team_id}/aws-accounts",
    response_model=AWSAccountRead,
    status_code=status.HTTP_201_CREATED,
)
def connect_aws_account_to_team(
    team_id: UUID,
    data: AWSAccountConnectRequest,
    db: DbSession,
    user: CurrentUser,
) -> AWSAccountRead:
    return service.connect_aws_account(db, team_id, user, data)


@router.get(
    "/teams/{team_id}/aws-accounts",
    response_model=list[AWSAccountRead],
)
def get_team_aws_accounts(
    team_id: UUID,
    db: DbSession,
    user: CurrentUser,
) -> list[AWSAccountRead]:
    return service.list_team_aws_accounts(db, team_id, user)


# ───────────────────────── Deployments ─────────────────────────


@router.post(
    "/projects/{project_id}/deployments",
    response_model=DeploymentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_deployment_for_project(
    project_id: UUID,
    data: DeploymentCreateRequest,
    db: DbSession,
    user: CurrentUser,
) -> DeploymentRead:
    return service.create_deployment_plan(db, project_id, user, data)


@router.get(
    "/projects/{project_id}/deployments",
    response_model=list[DeploymentRead],
)
def get_project_deployments(
    project_id: UUID,
    db: DbSession,
    user: CurrentUser,
) -> list[DeploymentRead]:
    return service.list_project_deployments(db, project_id, user)


@router.get(
    "/deployments/{deployment_id}",
    response_model=DeploymentRead,
)
def get_deployment_by_id(
    deployment_id: UUID,
    db: DbSession,
    user: CurrentUser,
) -> DeploymentRead:
    return service.get_deployment_details(db, deployment_id, user)


@router.post(
    "/deployments/{deployment_id}/approve",
    response_model=ApprovalRead,
)
def approve_or_reject_deployment(
    deployment_id: UUID,
    data: ApprovalDecisionRequest,
    db: DbSession,
    user: CurrentUser,
) -> ApprovalRead:
    return service.decide_approval(db, deployment_id, user, data)


@router.post(
    "/deployments/{deployment_id}/apply",
    response_model=DeploymentRead,
)
def trigger_deployment_execution(
    deployment_id: UUID,
    db: DbSession,
    user: CurrentUser,
) -> DeploymentRead:
    return service.apply_deployment(db, deployment_id, user)
