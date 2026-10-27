"""AWS accounts and deployments (ADR-027..033). The API only records intent and evidence; the
deploy runner does every AWS change, and only for a plan an ADMIN/OWNER approved by hash."""

from __future__ import annotations

import secrets
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.config import settings
from app.core.errors import (
    BadRequest,
    Conflict,
    Forbidden,
    NotFound,
    ServiceUnavailable,
    UpstreamError,
)
from app.core.permissions import check_team_role
from app.core.ratelimit import client_ip, limit_team
from app.deploy import aws
from app.deploy.onboarding import OnboardingNames, render_template
from app.models import (
    Approval,
    ArchitectureVersion,
    AuditLog,
    AWSAccount,
    Deployment,
    DeploymentStep,
    InfrastructureResource,
    Project,
    RepositoryAnalysis,
    User,
)
from app.modules.deployments.schemas import (
    ApprovalDecisionRequest,
    ApprovalRead,
    AuditEntryRead,
    AWSAccountConnectRequest,
    AWSAccountRead,
    DeploymentCreateRequest,
    DeploymentRead,
    DeploymentStepRead,
    DestroyRequest,
    EgressIpRead,
    InfrastructureResourceRead,
    OnboardingRead,
)

STEPS = ["PLAN", "POLICY_CHECK", "APPROVAL", "APPLY", "HEALTH_CHECK", "DESTROY", "VERIFY_CLEAN"]
TERMINAL = frozenset(
    {
        "AWAITING_APPROVAL",
        "BLOCKED",
        "SUCCESS",
        "FAILED",
        "TIMED_OUT",
        "CANCELLED",
        "DESTROYED",
        "DESTROY_FAILED",
    }
)
# after an apply was attempted, infrastructure may exist: destroy is offered
DESTROYABLE = frozenset({"SUCCESS", "FAILED", "TIMED_OUT", "DESTROY_FAILED"})


def _now() -> datetime:
    return datetime.now(UTC)


def _request_info(request: Request | None) -> audit.RequestInfo:
    if request is None:
        return audit.RequestInfo()
    return audit.RequestInfo(
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
        correlation_id=getattr(request.state, "correlation_id", None),
    )


def _require_deploy() -> None:
    if not aws.deploy_enabled():
        raise ServiceUnavailable(
            "Deployments are disabled: CloudPilot's AWS identity (CLOUDPILOT_AWS_*) is not "
            "configured. No AWS call was made."
        )


# ───────────────────────── AWS accounts ─────────────────────────
def _names(account: AWSAccount) -> OnboardingNames:
    return OnboardingNames(account_id=account.aws_account_id, suffix=account.id.hex[:8])


def connect_aws_account(
    db: Session,
    team_id: uuid.UUID,
    user: User,
    data: AWSAccountConnectRequest,
    request: Request | None = None,
) -> AWSAccountRead:
    check_team_role(db, user, team_id, "ADMIN")
    account = AWSAccount(
        id=uuid.uuid4(),
        team_id=team_id,
        aws_account_id=data.aws_account_id,
        # unique per account, >= 32 chars (ADR-027); an identifier, not a secret
        external_id=f"cp-{secrets.token_hex(20)}",
        default_region=data.default_region,
        status="PENDING_VERIFICATION",
    )
    names = _names(account)
    account.role_arn = names.role_arn
    account.state_bucket = names.state_bucket
    account.boundary_arn = names.boundary_arn
    account.onboarding_stack = names.stack_name
    db.add(account)
    db.flush()
    audit.record(
        db,
        team_id=team_id,
        action="AWS_ACCOUNT_CONNECTED",
        target_type="aws_account",
        target_id=account.id,
        actor_user_id=user.id,
        request=_request_info(request),
        details={"aws_account_id": account.aws_account_id, "region": account.default_region},
    )
    db.commit()
    db.refresh(account)
    return AWSAccountRead.model_validate(account)


def list_team_aws_accounts(db: Session, team_id: uuid.UUID, user: User) -> list[AWSAccountRead]:
    check_team_role(db, user, team_id, "MEMBER")
    rows = db.scalars(
        select(AWSAccount)
        .where(AWSAccount.team_id == team_id)
        .order_by(AWSAccount.connected_at.desc())
    ).all()
    return [AWSAccountRead.model_validate(r) for r in rows]


def _account_for(
    db: Session, account_id: uuid.UUID, user: User, role: str = "MEMBER"
) -> AWSAccount:
    account = db.get(AWSAccount, account_id)
    if account is None:
        raise NotFound("AWS account not found.")
    check_team_role(db, user, account.team_id, role)  # type: ignore[arg-type]
    return account


_principal_cache: tuple[float, str] | None = None
_principal_lock = threading.Lock()


def _platform_principal() -> str:
    global _principal_cache
    with _principal_lock:
        if _principal_cache and time.monotonic() - _principal_cache[0] < 600:
            return _principal_cache[1]
        arn = aws.platform_principal_arn()
        _principal_cache = (time.monotonic(), arn)
        return arn


def onboarding(db: Session, account_id: uuid.UUID, user: User) -> OnboardingRead:
    account = _account_for(db, account_id, user, "ADMIN")
    _require_deploy()
    names = _names(account)
    principal = _platform_principal()
    template = render_template(
        names,
        external_id=account.external_id,
        platform_principal_arn=principal,
        region=account.default_region,
    )
    return OnboardingRead(
        stack_name=names.stack_name,
        region=account.default_region,
        role_arn=names.role_arn,
        state_bucket=names.state_bucket,
        boundary_arn=names.boundary_arn,
        external_id=account.external_id,
        platform_principal_arn=principal,
        template=template,
        cli_command=(
            f"aws cloudformation deploy --region {account.default_region} --stack-name "
            f"{names.stack_name} --template-file cloudpilot-onboarding.json "
            "--capabilities CAPABILITY_NAMED_IAM"
        ),
    )


def verify_aws_account(
    db: Session, account_id: uuid.UUID, user: User, request: Request | None = None
) -> AWSAccountRead:
    account = _account_for(db, account_id, user, "ADMIN")
    _require_deploy()
    limit_team(db, account.team_id, "aws_verify")
    session_name = f"cp-verify-{account.id.hex[:8]}-{int(time.time())}"
    result = aws.verify_account(
        account_id=account.aws_account_id,
        role_arn=account.role_arn or "",
        external_id=account.external_id,
        state_bucket=account.state_bucket or "",
        region=account.default_region,
        session_name=session_name,
    )
    account.status = "ACTIVE" if result.ok else "VERIFICATION_FAILED"
    account.verified_identity_arn = result.identity_arn
    account.external_id_enforced = result.external_id_enforced
    account.verification_message = result.message
    if result.ok:
        account.last_verified_at = _now()
    audit.record(
        db,
        team_id=account.team_id,
        action="AWS_ACCOUNT_VERIFIED" if result.ok else "AWS_ACCOUNT_VERIFICATION_FAILED",
        target_type="aws_account",
        target_id=account.id,
        actor_user_id=user.id,
        request=_request_info(request),
        details={
            "session_name": session_name,
            "identity_arn": result.identity_arn,
            "external_id_enforced": result.external_id_enforced,
            "state_bucket_ok": result.state_bucket_ok,
            "message": result.message,
        },
    )
    db.commit()
    db.refresh(account)
    return AWSAccountRead.model_validate(account)


_egress_cache: tuple[float, str] | None = None


def egress_ip() -> EgressIpRead:
    """This server's public IP (correct for the ALB allow-list when CloudPilot runs on your
    machine). Cached for five minutes."""
    global _egress_cache
    if _egress_cache and time.monotonic() - _egress_cache[0] < 300:
        ip = _egress_cache[1]
    else:
        try:
            ip = httpx.get("https://checkip.amazonaws.com", timeout=5).text.strip()
        except httpx.HTTPError as exc:
            raise UpstreamError("Could not detect the public IP (checkip.amazonaws.com).") from exc
        _egress_cache = (time.monotonic(), ip)
    return EgressIpRead(ip=ip, cidr=f"{ip}/32", source="checkip.amazonaws.com")


# ───────────────────────── deployments ─────────────────────────
def _variables(
    deployment: Deployment,
    plan: dict,
    account: AWSAccount,
    project: Project,
    image: str,
    cidrs: list[str],
) -> dict:
    components = plan.get("components", [])
    app = next(c for c in components if c["type"] == "ecs_service")
    db_c = next(c for c in components if c["type"] == "rds")
    logs: dict[str, Any] = next(
        (c for c in components if c["type"] == "cloudwatch"), {"config": {}}
    )
    return {
        "deployment_id": str(deployment.id),
        "name_prefix": f"cp-{deployment.id.hex[:8]}",
        "region": account.default_region,
        "image": image,
        "container_port": int(app["config"]["container_port"]),
        "health_path": str(app["config"]["health_path"]),
        "cpu": int(app["config"]["cpu"]),
        "memory": int(app["config"]["memory"]),
        "desired_count": int(app["config"]["desired_count"]),
        "ingress_cidrs": cidrs,
        "db_instance_class": str(db_c["config"]["instance_class"]),
        "db_engine_version": str(db_c["config"]["engine_version"]),
        "db_storage_gb": int(db_c["config"]["storage_gb"]),
        "log_retention_days": int(logs["config"].get("log_group_retention_days", 7)),
        "permissions_boundary_arn": account.boundary_arn,
        "tags": {
            "cloudpilot:team-id": str(project.team_id),
            "cloudpilot:project-id": str(project.id),
        },
    }


def create_deployment_plan(
    db: Session,
    project_id: uuid.UUID,
    user: User,
    data: DeploymentCreateRequest,
    request: Request | None = None,
) -> DeploymentRead:
    project = db.get(Project, project_id)
    if project is None:
        raise NotFound("Project not found.")
    check_team_role(db, user, project.team_id, "ADMIN")
    _require_deploy()

    version = db.get(ArchitectureVersion, data.architecture_version_id)
    analysis = (
        db.get(RepositoryAnalysis, version.source_analysis_id)
        if version and version.source_analysis_id
        else None
    )
    if version is None or analysis is None:
        raise NotFound("Architecture version not found.")
    if _project_of(db, analysis) != project.id:  # another project's version: invisible
        raise NotFound("Architecture version not found.")
    plan = version.architecture_data or {}
    if not plan.get("automated"):
        raise BadRequest(
            "This architecture is not automated: CloudPilot can deploy only priced, module-backed "
            "archetypes (today: one HTTP service with a Dockerfile plus PostgreSQL)."
        )
    account = db.get(AWSAccount, data.aws_account_id)
    if account is None or account.team_id != project.team_id:
        raise NotFound("AWS account not found.")
    if account.status != "ACTIVE":
        raise BadRequest("The AWS account is not active: verify the connection first.")
    if account.default_region != plan.get("region"):
        raise BadRequest(
            f"The plan is for {plan.get('region')}; "
            f"the account deploys to {account.default_region}."
        )
    limit_team(db, project.team_id, "deploy_plan")

    deployment = Deployment(
        id=uuid.uuid4(),
        project_id=project.id,
        repository_id=analysis.repository_id,
        commit_id=analysis.commit_id,
        architecture_version_id=version.id,
        aws_account_id=account.id,
        status="QUEUED",
        trigger_type="MANUAL",
        created_by=user.id,
        image_uri=data.image_uri,
    )
    deployment.config = {
        "variables": _variables(
            deployment, plan, account, project, data.image_uri, data.ingress_cidrs
        ),
        "stack": "container-postgres",
        "archetype": plan.get("archetype"),
    }
    db.add(deployment)
    db.flush()
    for order, step in enumerate(STEPS, start=1):
        db.add(
            DeploymentStep(
                deployment_id=deployment.id, step_type=step, step_order=order, status="QUEUED"
            )
        )
    audit.record(
        db,
        team_id=project.team_id,
        action="DEPLOYMENT_PLAN_REQUESTED",
        target_type="deployment",
        target_id=deployment.id,
        actor_user_id=user.id,
        request=_request_info(request),
        details={
            "image_uri": data.image_uri,
            "ingress_cidrs": data.ingress_cidrs,
            "account": account.aws_account_id,
        },
    )
    db.commit()
    return _read(db, deployment)


def _project_of(db: Session, analysis: RepositoryAnalysis) -> uuid.UUID | None:
    from app.models import Repository

    repo = db.get(Repository, analysis.repository_id)
    return repo.project_id if repo else None


def _deployment_for(
    db: Session, deployment_id: uuid.UUID, user: User, role: str = "MEMBER"
) -> tuple[Deployment, Project]:
    deployment = db.get(Deployment, deployment_id)
    if deployment is None:
        raise NotFound("Deployment not found.")
    project = db.get(Project, deployment.project_id)
    if project is None:
        raise NotFound("Deployment not found.")
    check_team_role(db, user, project.team_id, role)  # type: ignore[arg-type]
    return deployment, project


def _latest_approval(db: Session, deployment_id: uuid.UUID) -> Approval | None:
    return db.scalar(
        select(Approval)
        .where(Approval.deployment_id == deployment_id)
        .order_by(Approval.requested_at.desc(), Approval.id.desc())
        .limit(1)
    )


def _set_step(db: Session, deployment_id: uuid.UUID, step: str, status: str) -> None:
    row = db.scalar(
        select(DeploymentStep).where(
            DeploymentStep.deployment_id == deployment_id, DeploymentStep.step_type == step
        )
    )
    if row is not None:
        row.status = status
        now = _now()
        row.started_at = row.started_at or now
        row.completed_at = now if status in {"SUCCESS", "FAILED", "SKIPPED"} else None


def decide_approval(
    db: Session,
    deployment_id: uuid.UUID,
    user: User,
    data: ApprovalDecisionRequest,
    request: Request | None = None,
) -> ApprovalRead:
    deployment, project = _deployment_for(db, deployment_id, user, "ADMIN")
    limit_team(db, project.team_id, "deploy_approve")
    if deployment.status != "AWAITING_APPROVAL":
        raise Conflict(f"Nothing to approve: the deployment is {deployment.status}.")
    if data.plan_hash != deployment.plan_hash:
        audit.record(
            db,
            team_id=project.team_id,
            action="APPROVAL_REFUSED_HASH_MISMATCH",
            target_type="deployment",
            target_id=deployment.id,
            actor_user_id=user.id,
            plan_hash=data.plan_hash,
            request=_request_info(request),
            details={"current_plan_hash": deployment.plan_hash},
        )
        db.commit()
        raise Conflict(
            "The plan changed since you reviewed it; review the current plan and approve that one."
        )
    now = _now()
    for old in db.scalars(
        select(Approval).where(
            Approval.deployment_id == deployment.id, Approval.status == "APPROVED"
        )
    ):
        old.status = "SUPERSEDED"
    approval = Approval(
        deployment_id=deployment.id,
        requested_by=deployment.created_by or user.id,
        approved_by=user.id,
        status=data.decision,
        reason=data.reason,
        decided_at=now,
        plan_hash=deployment.plan_hash,
        expires_at=now + timedelta(hours=settings.deploy_approval_ttl_hours)
        if data.decision == "APPROVED"
        else None,
    )
    db.add(approval)
    if data.decision == "APPROVED":
        _set_step(db, deployment.id, "APPROVAL", "SUCCESS")
    else:
        deployment.status = "CANCELLED"
        deployment.completed_at = now
        for row in db.scalars(
            select(DeploymentStep).where(DeploymentStep.deployment_id == deployment.id)
        ):
            if row.status == "QUEUED":
                row.status = "SKIPPED"
        _set_step(db, deployment.id, "APPROVAL", "FAILED")
    audit.record(
        db,
        team_id=project.team_id,
        action="DEPLOYMENT_APPROVED" if data.decision == "APPROVED" else "DEPLOYMENT_REJECTED",
        target_type="deployment",
        target_id=deployment.id,
        actor_user_id=user.id,
        plan_hash=deployment.plan_hash,
        request=_request_info(request),
        details={
            "reason": data.reason,
            "self_approval": deployment.created_by == user.id,
            "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
        },
    )
    db.commit()
    db.refresh(approval)
    return ApprovalRead.model_validate(approval)


def apply_deployment(
    db: Session, deployment_id: uuid.UUID, user: User, request: Request | None = None
) -> DeploymentRead:
    deployment, project = _deployment_for(db, deployment_id, user, "ADMIN")
    _require_deploy()
    approval = _latest_approval(db, deployment.id)
    if approval is None or approval.status not in {"APPROVED", "CONSUMED"}:
        raise Forbidden(
            "Deployment requires explicit human approval of the current plan before apply."
        )
    if deployment.status != "AWAITING_APPROVAL":
        raise Conflict(f"Cannot apply: the deployment is {deployment.status}.")
    if approval.status == "CONSUMED" or approval.consumed_at is not None:
        raise Conflict("This approval was already used; plan and approve again.")
    if approval.expires_at is not None and approval.expires_at < _now():
        approval.status = "EXPIRED"
        db.commit()
        raise Conflict("The approval expired; approve the plan again.")
    if approval.plan_hash != deployment.plan_hash:
        raise Conflict("The approval is for a different plan; approve the current plan.")
    limit_team(db, project.team_id, "deploy_apply")
    deployment.status = "APPLY_QUEUED"
    deployment.error_code = None
    deployment.error_message = None
    audit.record(
        db,
        team_id=project.team_id,
        action="APPLY_REQUESTED",
        target_type="deployment",
        target_id=deployment.id,
        actor_user_id=user.id,
        plan_hash=deployment.plan_hash,
        request=_request_info(request),
    )
    db.commit()
    return _read(db, deployment)


def destroy_deployment(
    db: Session,
    deployment_id: uuid.UUID,
    user: User,
    data: DestroyRequest,
    request: Request | None = None,
) -> DeploymentRead:
    deployment, project = _deployment_for(db, deployment_id, user, "ADMIN")
    _require_deploy()
    if deployment.status not in DESTROYABLE:
        raise Conflict(f"Nothing to destroy: the deployment is {deployment.status}.")
    limit_team(db, project.team_id, "deploy_destroy")
    deployment.status = "DESTROY_QUEUED"
    deployment.error_code = None
    deployment.error_message = None
    audit.record(
        db,
        team_id=project.team_id,
        action="DESTROY_REQUESTED",
        target_type="deployment",
        target_id=deployment.id,
        actor_user_id=user.id,
        request=_request_info(request),
    )
    db.commit()
    return _read(db, deployment)


def _read(db: Session, deployment: Deployment) -> DeploymentRead:
    steps = db.scalars(
        select(DeploymentStep)
        .where(DeploymentStep.deployment_id == deployment.id)
        .order_by(DeploymentStep.step_order)
    ).all()
    resources = db.scalars(
        select(InfrastructureResource)
        .where(InfrastructureResource.deployment_id == deployment.id)
        .order_by(InfrastructureResource.resource_type, InfrastructureResource.resource_name)
    ).all()
    approval = _latest_approval(db, deployment.id)
    variables = (deployment.config or {}).get("variables", {})
    outputs = deployment.outputs or {}
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
        error_code=deployment.error_code,
        error_message=deployment.error_message,
        created_by=deployment.created_by,
        image_uri=deployment.image_uri,
        ingress_cidrs=variables.get("ingress_cidrs", []),
        region=variables.get("region"),
        plan_hash=deployment.plan_hash,
        plan_summary=deployment.plan_summary,
        cost_estimate=deployment.cost_estimate,
        policy_results=deployment.policy_results,
        outputs=outputs or None,
        health=deployment.health,
        destroy_check=deployment.destroy_check,
        sessions=deployment.sessions or [],
        live_endpoint=outputs.get("endpoint_url") if deployment.status == "SUCCESS" else None,
        terminal=deployment.status in TERMINAL,
        steps=[DeploymentStepRead.model_validate(s) for s in steps],
        approval=ApprovalRead.model_validate(approval) if approval else None,
        resources=[InfrastructureResourceRead.model_validate(r) for r in resources],
    )


def get_deployment_details(db: Session, deployment_id: uuid.UUID, user: User) -> DeploymentRead:
    deployment, _ = _deployment_for(db, deployment_id, user)
    return _read(db, deployment)


def list_project_deployments(
    db: Session, project_id: uuid.UUID, user: User
) -> list[DeploymentRead]:
    project = db.get(Project, project_id)
    if project is None:
        raise NotFound("Project not found.")
    check_team_role(db, user, project.team_id, "MEMBER")
    rows = db.scalars(
        select(Deployment)
        .where(Deployment.project_id == project_id)
        .order_by(Deployment.created_at.desc())
        .limit(50)
    ).all()
    return [_read(db, d) for d in rows]


def deployment_audit(db: Session, deployment_id: uuid.UUID, user: User) -> list[AuditEntryRead]:
    deployment, project = _deployment_for(db, deployment_id, user)
    rows = db.scalars(
        select(AuditLog)
        .where(
            AuditLog.team_id == project.team_id,
            AuditLog.target_id.in_([str(deployment.id), str(deployment.aws_account_id)]),
        )
        .order_by(AuditLog.created_at)
    ).all()
    return [AuditEntryRead.model_validate(r) for r in rows]
