from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from AI.domain.analysis.models import RepositoryRef



@dataclass(frozen=True)
class AwsRequirement:
    service: str                      # "S3", "Lambda", "DynamoDB", ...
    reason: str
    evidence_files: tuple[str, ...]
    confidence: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be between 0 and 1, got {self.confidence}")
        if not self.evidence_files:
            raise ValueError(f"requirement for {self.service!r} needs at least one evidence file")


@dataclass(frozen=True)
class AwsRequirementsResult:
    repo: RepositoryRef
    requirements: tuple[AwsRequirement, ...]
    config: AwsConfigStatus
    unresolved: tuple[str, ...] = field(default_factory=tuple)
    clarifications: tuple[str, ...] = field(default_factory=tuple)
class AwsConfigKind(StrEnum):
    IAC_TEMPLATE = "iac_template"                    # CDK, SAM, Serverless, Terraform, CloudFormation
    SDK_CLIENT = "sdk_client"                        # boto3, @aws-sdk/*
    CREDENTIALS_REFERENCE = "credentials_reference"  # AWS_PROFILE, AWS_ACCESS_KEY_ID env usage
    REGION_SETTING = "region_setting"                # AWS_REGION, region_name=...
    HARDCODED_CREDENTIALS = "hardcoded_credentials"  # security issue, value never stored


@dataclass(frozen=True)
class AwsConfigFinding:
    kind: AwsConfigKind
    file: str
    detail: str  # human-readable, must never contain a secret value


@dataclass(frozen=True)
class AwsConfigStatus:
    findings: tuple[AwsConfigFinding, ...] = ()

    def has(self, kind: AwsConfigKind) -> bool:
        return any(f.kind is kind for f in self.findings)

    @property
    def has_hardcoded_credentials(self) -> bool:
        return self.has(AwsConfigKind.HARDCODED_CREDENTIALS)

    def gaps(self, required_services: tuple[str, ...]) -> tuple[str, ...]:
        """Describe config that the required services imply but the repo lacks."""
        gaps: list[str] = []
        if required_services and not (self.has(AwsConfigKind.SDK_CLIENT) or self.has(AwsConfigKind.IAC_TEMPLATE)):
            gaps.append("Code needs AWS services but has no SDK usage or infrastructure template")
        if required_services and not self.has(AwsConfigKind.REGION_SETTING):
            gaps.append("No AWS region is configured")
        if self.has_hardcoded_credentials:
            gaps.append("Hardcoded AWS credentials found; rotate them and move them to environment or a secrets manager")
        return tuple(gaps)


@dataclass(frozen=True)
class AwsRequirement:
    service: str
    reason: str
    evidence_files: tuple[str, ...]
    confidence: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be between 0 and 1, got {self.confidence}")
        if not self.evidence_files:
            raise ValueError(f"requirement for {self.service!r} needs at least one evidence file")


@dataclass(frozen=True)
class AwsRequirementsResult:
    repo: RepositoryRef
    requirements: tuple[AwsRequirement, ...]
    config: AwsConfigStatus
    unresolved: tuple[str, ...] = field(default_factory=tuple)

    @property
    def config_gaps(self) -> tuple[str, ...]:
        return self.config.gaps(tuple(r.service for r in self.requirements))