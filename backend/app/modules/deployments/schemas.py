import ipaddress
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

IMAGE_DIGEST = r"^[a-z0-9][a-z0-9._/:-]{0,250}@sha256:[0-9a-f]{64}$"
REGION = r"^[a-z]{2}(-[a-z]+)+-\d$"


# ───────────────────────── AWS accounts ─────────────────────────
class AWSAccountConnectRequest(BaseModel):
    aws_account_id: str = Field(..., pattern=r"^\d{12}$")
    default_region: str = Field(default="us-east-1", pattern=REGION)


class AWSAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    team_id: UUID
    aws_account_id: str
    role_arn: str | None = None
    external_id: str
    default_region: str
    status: str
    connected_at: datetime
    last_verified_at: datetime | None = None
    state_bucket: str | None = None
    onboarding_stack: str | None = None
    verified_identity_arn: str | None = None
    external_id_enforced: bool | None = None
    verification_message: str | None = None


class OnboardingRead(BaseModel):
    """Everything the customer needs to deploy the onboarding stack. No secrets: the External ID
    is a shared identifier, not a credential."""

    stack_name: str
    region: str
    role_arn: str
    state_bucket: str
    boundary_arn: str
    external_id: str
    platform_principal_arn: str
    template: str
    cli_command: str


# ───────────────────────── deployments ─────────────────────────
class DeploymentCreateRequest(BaseModel):
    architecture_version_id: UUID
    aws_account_id: UUID
    image_uri: str = Field(..., max_length=300, pattern=IMAGE_DIGEST)
    ingress_cidrs: list[str] = Field(..., min_length=1, max_length=5)

    @field_validator("ingress_cidrs")
    @classmethod
    def _cidrs(cls, values: list[str]) -> list[str]:
        out = []
        for value in values:
            net = ipaddress.ip_network(value.strip(), strict=False)
            if net.version != 4 or net.prefixlen < 16:
                raise ValueError(
                    "Use IPv4 CIDRs no wider than /16 (e.g. your IP as 203.0.113.7/32)."
                )
            out.append(str(net))
        return out


class ApprovalDecisionRequest(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    plan_hash: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    reason: str | None = Field(None, max_length=500)


class DestroyRequest(BaseModel):
    confirm: Literal["destroy"]


class DeploymentStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    deployment_id: UUID
    step_type: str
    step_order: int
    status: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    output_data: dict | None = None


class ApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    deployment_id: UUID | None = None
    requested_by: UUID
    approved_by: UUID | None = None
    status: str
    reason: str | None = None
    requested_at: datetime
    decided_at: datetime | None = None
    plan_hash: str | None = None
    expires_at: datetime | None = None
    consumed_at: datetime | None = None


class InfrastructureResourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    resource_type: str
    resource_name: str
    aws_resource_id: str | None = None
    aws_arn: str | None = None
    region: str
    status: str


class AuditEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    action: str
    actor_user_id: UUID | None = None
    target_type: str
    target_id: str | None = None
    plan_hash: str | None = None
    ip: str | None = None
    details: dict[str, Any] = {}
    entry_hash: str


class DeploymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    repository_id: UUID
    commit_id: UUID
    architecture_version_id: UUID
    aws_account_id: UUID
    status: str
    trigger_type: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_by: UUID | None = None
    image_uri: str | None = None
    ingress_cidrs: list[str] = []
    region: str | None = None
    plan_hash: str | None = None
    plan_summary: dict | None = None
    cost_estimate: dict | None = None
    policy_results: list | None = None
    outputs: dict | None = None
    health: dict | None = None
    destroy_check: dict | None = None
    sessions: list = []
    live_endpoint: str | None = None
    terminal: bool = False
    steps: list[DeploymentStepRead] = []
    approval: ApprovalRead | None = None
    resources: list[InfrastructureResourceRead] = []


class EgressIpRead(BaseModel):
    ip: str
    cidr: str
    source: str
