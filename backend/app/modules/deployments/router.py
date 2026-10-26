from uuid import UUID

from fastapi import APIRouter, Request, status

from app.core.dependencies import DbSession
from app.modules.auth.dependencies import CurrentUser
from app.modules.deployments import service
from app.modules.deployments.schemas import (
    ApprovalDecisionRequest,
    ApprovalRead,
    AuditEntryRead,
    AWSAccountConnectRequest,
    AWSAccountRead,
    DeploymentCreateRequest,
    DeploymentRead,
    DestroyRequest,
    EgressIpRead,
    OnboardingRead,
)

router = APIRouter(tags=["deployments"])


# ───────────────────────── AWS accounts ─────────────────────────
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
    request: Request,
) -> AWSAccountRead:
    return service.connect_aws_account(db, team_id, user, data, request)


@router.get("/teams/{team_id}/aws-accounts", response_model=list[AWSAccountRead])
def get_team_aws_accounts(team_id: UUID, db: DbSession, user: CurrentUser) -> list[AWSAccountRead]:
    return service.list_team_aws_accounts(db, team_id, user)


@router.get("/aws-accounts/{account_id}/onboarding", response_model=OnboardingRead)
def get_onboarding(account_id: UUID, db: DbSession, user: CurrentUser) -> OnboardingRead:
    """The CloudFormation template (and how to deploy it) for this account."""
    return service.onboarding(db, account_id, user)


@router.post("/aws-accounts/{account_id}/verify", response_model=AWSAccountRead)
def verify_aws_account(
    account_id: UUID, db: DbSession, user: CurrentUser, request: Request
) -> AWSAccountRead:
    """Real STS AssumeRole with the External ID; also proves it fails without it."""
    return service.verify_aws_account(db, account_id, user, request)


@router.get("/network/egress-ip", response_model=EgressIpRead)
def get_egress_ip(_: CurrentUser) -> EgressIpRead:
    return service.egress_ip()


# ───────────────────────── deployments ─────────────────────────
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
    request: Request,
) -> DeploymentRead:
    """Queues an OpenTofu plan. Nothing in AWS changes until the plan is approved and applied."""
    return service.create_deployment_plan(db, project_id, user, data, request)


@router.get("/projects/{project_id}/deployments", response_model=list[DeploymentRead])
def get_project_deployments(
    project_id: UUID, db: DbSession, user: CurrentUser
) -> list[DeploymentRead]:
    return service.list_project_deployments(db, project_id, user)


@router.get("/deployments/{deployment_id}", response_model=DeploymentRead)
def get_deployment_by_id(deployment_id: UUID, db: DbSession, user: CurrentUser) -> DeploymentRead:
    return service.get_deployment_details(db, deployment_id, user)


@router.get("/deployments/{deployment_id}/audit", response_model=list[AuditEntryRead])
def get_deployment_audit(
    deployment_id: UUID, db: DbSession, user: CurrentUser
) -> list[AuditEntryRead]:
    return service.deployment_audit(db, deployment_id, user)


@router.post("/deployments/{deployment_id}/approve", response_model=ApprovalRead)
def approve_or_reject_deployment(
    deployment_id: UUID,
    data: ApprovalDecisionRequest,
    db: DbSession,
    user: CurrentUser,
    request: Request,
) -> ApprovalRead:
    """ADMIN/OWNER only; the request must carry the hash of the plan that was reviewed."""
    return service.decide_approval(db, deployment_id, user, data, request)


@router.post("/deployments/{deployment_id}/apply", response_model=DeploymentRead)
def apply_deployment(
    deployment_id: UUID, db: DbSession, user: CurrentUser, request: Request
) -> DeploymentRead:
    return service.apply_deployment(db, deployment_id, user, request)


@router.post("/deployments/{deployment_id}/destroy", response_model=DeploymentRead)
def destroy_deployment(
    deployment_id: UUID, data: DestroyRequest, db: DbSession, user: CurrentUser, request: Request
) -> DeploymentRead:
    return service.destroy_deployment(db, deployment_id, user, data, request)
