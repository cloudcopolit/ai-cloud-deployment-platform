from typing import Literal

from pydantic import BaseModel

ClarificationId = Literal["target_environment", "aws_region", "deployment_status"]


class RequirementOut(BaseModel):
    service: str
    reason: str
    evidence_files: list[str]
    confidence: float


class AwsOut(BaseModel):
    requirements: list[RequirementOut]
    unresolved: list[str]
    clarifications: list[ClarificationId]
