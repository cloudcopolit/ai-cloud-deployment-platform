import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AWSAccountConnectRequest(BaseModel):
    aws_account_id: str = Field(..., min_length=12, max_length=12, pattern=r"^\d{12}$")
    role_arn: str = Field(..., min_length=20, max_length=255)
    readonly_role_arn: str | None = Field(None, max_length=255)
    default_region: str = Field(default="us-east-1", max_length=32)

    @model_validator(mode="after")
    def validate_role_accounts(self) -> "AWSAccountConnectRequest":
        arns = [self.role_arn]
        if self.readonly_role_arn:
            arns.append(self.readonly_role_arn)

        for arn in arns:
            match = re.fullmatch(
                r"arn:(?:aws|aws-us-gov|aws-cn):iam::(?P<account>\d{12}):role/.+",
                arn,
            )
            if match is None or match.group("account") != self.aws_account_id:
                raise ValueError("Role ARN must be an IAM role in the specified AWS account.")
        return self


class AWSAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    team_id: UUID
    aws_account_id: str
    role_arn: str | None = None
    readonly_role_arn: str | None = None
    external_id: str
    default_region: str
    status: str
    connected_at: datetime
    last_verified_at: datetime | None = None


class DeploymentCreateRequest(BaseModel):
    repository_id: UUID
    architecture_version_id: UUID
    aws_account_id: UUID
    commit_sha: str | None = Field(None, max_length=40)
    trigger_type: Literal["MANUAL", "AUTO", "RETRY", "HEALING"] = "MANUAL"


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


class ApprovalDecisionRequest(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    reason: str | None = Field(None, max_length=500)


class InfrastructureResourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    resource_type: str
    resource_name: str
    aws_resource_id: str | None = None
    aws_arn: str | None = None
    region: str
    status: str


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
    created_by: UUID | None = None
    error_code: str | None = None
    error_message: str | None = None
    steps: list[DeploymentStepRead] = []
    approval: ApprovalRead | None = None
    live_endpoint: str | None = None
    resources: list[InfrastructureResourceRead] = []
