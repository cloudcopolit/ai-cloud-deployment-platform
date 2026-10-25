import uuid
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BadRequest, Forbidden, NotFound, ServiceUnavailable
from app.core.permissions import check_team_role
from app.models import (
    Approval,
    ArchitectureVersion,
    AWSAccount,
    Branch,
    Commit,
    Deployment,
    DeploymentStep,
    InfrastructureResource,
    Project,
    Repository,
    User,
)
from app.modules.deployments.schemas import (
    ApprovalDecisionRequest,
    ApprovalRead,
    AWSAccountConnectRequest,
    AWSAccountRead,
    DeploymentCreateRequest,
    DeploymentRead,
    DeploymentStepRead,
    InfrastructureResourceRead,
)


def _to_deployment_read(db: Session, deployment: Deployment) -> DeploymentRead:
    steps = db.scalars(
        select(DeploymentStep)
        .where(DeploymentStep.deployment_id == deployment.id)
        .order_by(DeploymentStep.step_order.asc())
    ).all()

    approval = db.scalar(select(Approval).where(Approval.deployment_id == deployment.id))

    resources = db.scalars(
        select(InfrastructureResource)
        .where(InfrastructureResource.deployment_id == deployment.id)
        .order_by(InfrastructureResource.created_at.asc())
    ).all()

    live_endpoint = None
    health_step = next((s for s in steps if s.step_type == "VERIFY_HEALTH"), None)
    if health_step and health_step.status == "SUCCESS" and health_step.output_data:
        live_endpoint = health_step.output_data.get("endpoint")

    return DeploymentRead(
        id=deployment.id,
        project_id=deployment.project_id,
        repository_id=deployment.repository_id,
        commit_id=deployment.commit_id,
        architecture_version_id=deployment.architecture_version_id,
        aws_account_id=deployment.aws_account_id,
        status=deployment.status,
        trigger_type=deployment.trigger_type,
        created_at=deployment.created_at,
        started_at=deployment.started_at,
        completed_at=deployment.completed_at,
        created_by=deployment.created_by,
        error_code=deployment.error_code,
        error_message=deployment.error_message,
        steps=[DeploymentStepRead.model_validate(s) for s in steps],
        approval=ApprovalRead.model_validate(approval) if approval else None,
        live_endpoint=live_endpoint,
        resources=[InfrastructureResourceRead.model_validate(r) for r in resources],
    )


# ───────────────────────── AWS Accounts ─────────────────────────


def connect_aws_account(
    db: Session, team_id: UUID, user: User, data: AWSAccountConnectRequest
) -> AWSAccountRead:
    check_team_role(db, user, team_id, "ADMIN")

    external_id = f"cp-{uuid.uuid4().hex[:28]}"
    account = AWSAccount(
        team_id=team_id,
        aws_account_id=data.aws_account_id,
        role_arn=data.role_arn,
        readonly_role_arn=data.readonly_role_arn,
        external_id=external_id,
        default_region=data.default_region,
        status="PENDING_VERIFICATION",
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    return AWSAccountRead.model_validate(account)


def list_team_aws_accounts(db: Session, team_id: UUID, user: User) -> list[AWSAccountRead]:
    check_team_role(db, user, team_id, "MEMBER")

    accounts = db.scalars(
        select(AWSAccount)
        .where(AWSAccount.team_id == team_id)
        .order_by(AWSAccount.connected_at.desc())
    ).all()

    return [AWSAccountRead.model_validate(a) for a in accounts]


# ───────────────────────── Deployments ─────────────────────────


def create_deployment_plan(
    db: Session, project_id: UUID, user: User, data: DeploymentCreateRequest
) -> DeploymentRead:
    project = db.get(Project, project_id)
    if not project:
        raise NotFound("Project not found.")

    check_team_role(db, user, project.team_id, "MEMBER")

    arch_version = db.get(ArchitectureVersion, data.architecture_version_id)
    if not arch_version:
        raise NotFound("Architecture version not found.")

    if arch_version.status not in ["VALIDATED", "APPROVED"]:
        raise BadRequest(
            "Architecture version must be VALIDATED or APPROVED to generate deployment plan."
        )

    aws_acc = db.get(AWSAccount, data.aws_account_id)
    if not aws_acc or aws_acc.team_id != project.team_id:
        raise NotFound("AWS Account not found for project team.")

    if aws_acc.status != "ACTIVE":
        raise BadRequest("AWS Account is not active.")

    repo = db.get(Repository, data.repository_id)
    if not repo or repo.project_id != project.id:
        raise NotFound("Repository not found in project.")

    # Resolve commit
    commit = None
    if data.commit_sha:
        commit = db.scalar(
            select(Commit).where(Commit.repository_id == repo.id, Commit.sha == data.commit_sha)
        )
    if not commit:
        dep_branch_id = db.scalar(
            select(Branch.id).where(
                Branch.repository_id == repo.id,
                Branch.is_deployment_branch.is_(True),
            )
        )
        if dep_branch_id:
            commit = db.scalar(
                select(Commit)
                .where(Commit.repository_id == repo.id, Commit.branch_id == dep_branch_id)
                .order_by(Commit.committed_at.desc())
            )
    if not commit:
        commit = db.scalar(
            select(Commit)
            .where(Commit.repository_id == repo.id)
            .order_by(Commit.committed_at.desc())
        )
    if not commit:
        raise NotFound("No commits found to deploy.")

    now = datetime.now(UTC)
    deployment = Deployment(
        project_id=project.id,
        repository_id=repo.id,
        commit_id=commit.id,
        architecture_version_id=arch_version.id,
        aws_account_id=aws_acc.id,
        status="QUEUED",
        trigger_type=data.trigger_type,
        created_at=now,
        created_by=user.id,
    )
    db.add(deployment)
    db.flush()

    # Explicit Human Approval gate: initialized as PENDING
    approval = Approval(
        deployment_id=deployment.id,
        requested_by=user.id,
        status="PENDING",
        requested_at=now,
    )
    db.add(approval)

    # Initialize 5 canonical deployment steps in QUEUED state
    canonical_steps = [
        "VALIDATE_PERMISSIONS",
        "SYNTHESIZE_TERRAFORM",
        "PROVISION_INFRASTRUCTURE",
        "DEPLOY_CONTAINER",
        "VERIFY_HEALTH",
    ]
    for order, st in enumerate(canonical_steps, start=1):
        step = DeploymentStep(
            deployment_id=deployment.id,
            step_type=st,
            step_order=order,
            status="QUEUED",
            created_at=now,
        )
        db.add(step)

    db.commit()
    db.refresh(deployment)

    return _to_deployment_read(db, deployment)


def decide_approval(
    db: Session, deployment_id: UUID, user: User, request: ApprovalDecisionRequest
) -> ApprovalRead:
    deployment = db.get(Deployment, deployment_id)
    if not deployment:
        raise NotFound("Deployment not found.")

    project = db.get(Project, deployment.project_id)
    if not project:
        raise NotFound("Project not found.")

    # Human approval gate: only team ADMIN or OWNER can approve
    check_team_role(db, user, project.team_id, "ADMIN")

    approval = db.scalar(select(Approval).where(Approval.deployment_id == deployment_id))
    if not approval:
        raise NotFound("Approval record not found.")

    if approval.status != "PENDING":
        raise BadRequest(f"Approval has already been decided ({approval.status}).")

    now = datetime.now(UTC)
    approval.status = request.decision
    approval.approved_by = user.id
    approval.decided_at = now
    approval.reason = request.reason

    if request.decision == "REJECTED":
        deployment.status = "CANCELLED"
        deployment.completed_at = now
        steps = db.scalars(
            select(DeploymentStep).where(DeploymentStep.deployment_id == deployment.id)
        ).all()
        for s in steps:
            s.status = "SKIPPED"
    elif request.decision == "APPROVED":
        arch_v = db.get(ArchitectureVersion, deployment.architecture_version_id)
        if arch_v:
            arch_v.status = "APPROVED"

    db.commit()
    db.refresh(approval)

    return ApprovalRead.model_validate(approval)


def apply_deployment(db: Session, deployment_id: UUID, user: User) -> DeploymentRead:
    deployment = db.get(Deployment, deployment_id)
    if not deployment:
        raise NotFound("Deployment not found.")

    project = db.get(Project, deployment.project_id)
    if not project:
        raise NotFound("Project not found.")

    check_team_role(db, user, project.team_id, "ADMIN")

    # Strict Human Approval Check
    approval = db.scalar(select(Approval).where(Approval.deployment_id == deployment_id))
    if not approval or approval.status != "APPROVED":
        raise Forbidden("Deployment requires explicit human approval before execution.")

    raise ServiceUnavailable(
        "AWS deployment is unavailable until role assumption, reviewed Terraform planning, "
        "and a controlled deployment worker are configured. No AWS changes were made."
    )


def get_deployment_details(db: Session, deployment_id: UUID, user: User) -> DeploymentRead:
    deployment = db.get(Deployment, deployment_id)
    if not deployment:
        raise NotFound("Deployment not found.")

    project = db.get(Project, deployment.project_id)
    if not project:
        raise NotFound("Project not found.")

    check_team_role(db, user, project.team_id, "MEMBER")
    return _to_deployment_read(db, deployment)


def list_project_deployments(db: Session, project_id: UUID, user: User) -> list[DeploymentRead]:
    project = db.get(Project, project_id)
    if not project:
        raise NotFound("Project not found.")

    check_team_role(db, user, project.team_id, "MEMBER")

    deployments = db.scalars(
        select(Deployment)
        .where(Deployment.project_id == project_id)
        .order_by(Deployment.created_at.desc())
    ).all()

    return [_to_deployment_read(db, d) for d in deployments]
