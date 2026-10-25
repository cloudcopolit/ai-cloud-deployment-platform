"""CloudPilot AI contracts (DRAFT v1.0) - Pydantic v2, Python 3.12.

Shared by the backend and the AI layer. One definition, two consumers.
Explained in ai-contracts.md. Verified by the contract tests and self-check
(`python ai_contracts.py`).

Rules encoded here:
- strict: unknown fields rejected, assignment validated
- every detection carries evidence metadata + confidence; source excerpts are not part of reports
- NO secret values anywhere (env var NAMES only)
- an AgentResult is exactly one of result / error
- ArchitecturePlan.requires_human_approval is Literal[True]: an LLM cannot output False
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

SCHEMA_VERSION = "1.0"


class Strict(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )


Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
ShortStr = Annotated[str, StringConstraints(max_length=255)]
Sha = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]
Region = Annotated[str, StringConstraints(pattern=r"^[a-z]{2}(-[a-z]+)+-\d$")]


# ───────────────────────── enums ─────────────────────────
class Severity(StrEnum):
    BLOCKER = "BLOCKER"
    WARNING = "WARNING"
    INFO = "INFO"


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"


class ErrorCode(StrEnum):
    REPOSITORY_NOT_FOUND = "REPOSITORY_NOT_FOUND"
    GITHUB_UNAUTHORIZED = "GITHUB_UNAUTHORIZED"
    GITHUB_RATE_LIMITED = "GITHUB_RATE_LIMITED"
    REPOSITORY_TOO_LARGE = "REPOSITORY_TOO_LARGE"
    UNSUPPORTED_STACK = "UNSUPPORTED_STACK"
    REQUIRED_INFO_MISSING = "REQUIRED_INFO_MISSING"
    LLM_TIMEOUT = "LLM_TIMEOUT"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    LLM_INVALID_OUTPUT = "LLM_INVALID_OUTPUT"
    SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"
    AWS_DISCOVERY_FAILED = "AWS_DISCOVERY_FAILED"
    STAGE_TIMEOUT = "STAGE_TIMEOUT"
    JOB_TIMEOUT = "JOB_TIMEOUT"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class Stage(StrEnum):
    FETCH_REPOSITORY = "FETCH_REPOSITORY"
    ANALYZE = "ANALYZE"
    DISCOVER_INFRA = "DISCOVER_INFRA"
    VALIDATE_REPORT = "VALIDATE_REPORT"
    EVALUATE = "EVALUATE"
    ARCHITECT = "ARCHITECT"
    VALIDATE_PLAN = "VALIDATE_PLAN"
    PERSIST = "PERSIST"


class ServiceType(StrEnum):
    API = "api"
    WEB = "web"
    WORKER = "worker"
    CRON = "cron"
    DATABASE = "database"
    OTHER = "other"


class ComponentType(StrEnum):
    ECS_SERVICE = "ecs_service"
    LAMBDA = "lambda"
    ALB = "alb"
    RDS = "rds"
    ELASTICACHE = "elasticache"
    S3 = "s3"
    CLOUDFRONT = "cloudfront"
    ECR = "ecr"
    SECRETS_MANAGER = "secrets_manager"
    VPC = "vpc"
    ROUTE53 = "route53"
    CLOUDWATCH = "cloudwatch"
    SQS = "sqs"
    OTHER = "other"


class Impact(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# ───────────────────────── errors ─────────────────────────
class ErrorInfo(Strict):
    code: ErrorCode
    message: Annotated[str, StringConstraints(max_length=500)]  # safe to show and to log
    stage: Stage | None = None
    retryable: bool = False
    details: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict
    )  # scalars only
    correlation_id: str | None = None


T = TypeVar("T", bound=BaseModel)


class AgentResult(Strict, Generic[T]):
    """Exactly one of result / error."""

    ok: bool
    result: T | None = None
    error: ErrorInfo | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> AgentResult[T]:
        if self.ok and (self.result is None or self.error is not None):
            raise ValueError("ok=True requires result and no error")
        if not self.ok and (self.error is None or self.result is not None):
            raise ValueError("ok=False requires error and no result")
        return self


# ───────────────────────── evidence ─────────────────────────
class Evidence(Strict):
    file_path: Annotated[str, StringConstraints(max_length=1024)]
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    detector: ShortStr
    content_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

    @model_validator(mode="after")
    def _lines(self) -> Evidence:
        if self.line_start and self.line_end and self.line_end < self.line_start:
            raise ValueError("line_end < line_start")
        return self


class Detection(Strict):
    confidence: Confidence
    evidence: Annotated[list[Evidence], Field(max_length=10)] = Field(default_factory=list)


# ───────────────────────── request ─────────────────────────
class RepositoryRef(Strict):
    owner: ShortStr
    name: ShortStr
    branch: ShortStr
    commit_sha: Sha


class AnalysisRequest(Strict):
    """Orchestrator -> Analysis Agent. Never contains tokens: only opaque refs resolved inside the Communication Module."""

    job_id: UUID
    correlation_id: str
    repository: RepositoryRef
    github_installation_ref: str  # opaque
    sub_path: str | None = None
    user_answers: dict[str, str] = Field(default_factory=dict)  # answers to earlier missing_info
    limits_max_files: int = Field(default=2000, ge=1)
    limits_max_bytes: int = Field(default=20_000_000, ge=1)


# ───────────────────────── AnalysisReport ─────────────────────────
class Language(Detection):
    name: ShortStr
    version: ShortStr | None = None
    share_percent: float | None = Field(default=None, ge=0, le=100)


class Framework(Detection):
    name: ShortStr
    version: ShortStr | None = None
    kind: Literal["backend", "frontend", "fullstack", "worker", "test", "other"] = "other"


class DetectedService(Detection):
    name: ShortStr
    service_type: ServiceType
    language: ShortStr | None = None
    framework: ShortStr | None = None
    path: Annotated[str, StringConstraints(max_length=1024)] = "."
    port: int | None = Field(default=None, ge=1, le=65535)
    has_dockerfile: bool = False
    health_endpoint: ShortStr | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class Dependency(Strict):
    ecosystem: Literal[
        "pypi", "npm", "maven", "gradle", "go", "cargo", "nuget", "rubygems", "composer", "other"
    ]
    name: ShortStr
    version_spec: ShortStr | None = None
    dev_only: bool = False
    manifest_path: Annotated[str, StringConstraints(max_length=1024)]


class ConfigFile(Detection):
    path: Annotated[str, StringConstraints(max_length=1024)]
    kind: Literal[
        "dockerfile", "compose", "ci", "terraform", "env_example", "k8s", "build", "other"
    ]


class EntryPoint(Detection):
    path: Annotated[str, StringConstraints(max_length=1024)]
    command: ShortStr | None = None  # recorded, NEVER executed


class DataStore(Detection):
    engine: Literal[
        "postgresql", "mysql", "mongodb", "redis", "sqlite", "dynamodb", "s3", "sqs", "other"
    ]
    inferred_from: ShortStr


class EnvVar(Strict):
    name: Annotated[
        str, StringConstraints(pattern=r"^[A-Z_][A-Z0-9_]*$", max_length=128)
    ]  # NAME only, never a value
    required: bool = True
    referenced_in: ShortStr | None = None


class Finding(Strict):
    code: Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]*$", max_length=64)]
    severity: Severity
    message: Annotated[str, StringConstraints(max_length=500)]
    evidence: Annotated[list[Evidence], Field(max_length=10)] = Field(default_factory=list)
    suggested_action: Annotated[str, StringConstraints(max_length=500)] | None = None


class MissingInfo(Strict):
    key: ShortStr
    question: Annotated[str, StringConstraints(max_length=500)]
    required: bool = True


class UnsupportedTechnology(Strict):
    name: ShortStr
    reason: Annotated[str, StringConstraints(max_length=500)]


class AnalysisMeta(Strict):
    analyzer_version: ShortStr
    files_scanned: int = Field(ge=0)
    files_skipped: int = Field(ge=0)
    truncated: bool = False
    duration_ms: int = Field(ge=0)
    model: ShortStr | None = None


class AnalysisReport(Strict):
    schema_version: Literal["1.0"] = "1.0"
    repository: RepositoryRef
    summary: Annotated[str, StringConstraints(max_length=1000)]
    languages: Annotated[list[Language], Field(max_length=50)] = Field(default_factory=list)
    frameworks: Annotated[list[Framework], Field(max_length=100)] = Field(default_factory=list)
    services: Annotated[list[DetectedService], Field(max_length=50)] = Field(default_factory=list)
    dependencies: Annotated[list[Dependency], Field(max_length=2000)] = Field(default_factory=list)
    config_files: Annotated[list[ConfigFile], Field(max_length=200)] = Field(default_factory=list)
    entry_points: Annotated[list[EntryPoint], Field(max_length=100)] = Field(default_factory=list)
    data_stores: Annotated[list[DataStore], Field(max_length=50)] = Field(default_factory=list)
    env_vars: Annotated[list[EnvVar], Field(max_length=500)] = Field(default_factory=list)
    blockers: Annotated[list[Finding], Field(max_length=100)] = Field(default_factory=list)
    warnings: Annotated[list[Finding], Field(max_length=200)] = Field(default_factory=list)
    missing_info: Annotated[list[MissingInfo], Field(max_length=50)] = Field(default_factory=list)
    unsupported: Annotated[list[UnsupportedTechnology], Field(max_length=50)] = Field(
        default_factory=list
    )
    overall_confidence: Confidence
    meta: AnalysisMeta

    @model_validator(mode="after")
    def _severity_buckets(self) -> AnalysisReport:
        if any(b.severity != Severity.BLOCKER for b in self.blockers):
            raise ValueError("blockers[] may only contain severity=BLOCKER")
        if any(w.severity == Severity.BLOCKER for w in self.warnings):
            raise ValueError("warnings[] must not contain severity=BLOCKER")
        return self

    @property
    def is_deployable(self) -> bool:
        """Orchestrator gate: no blockers, no unsupported tech, no REQUIRED info missing."""
        return not (self.blockers or self.unsupported or any(m.required for m in self.missing_info))


# ───────────────────────── ArchitecturePlan ─────────────────────────
class Component(Strict):
    id: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]
    type: ComponentType
    serves_service: ShortStr | None = None
    config: dict[str, str | int | float | bool | list[str] | None] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    rationale: Annotated[
        str, StringConstraints(min_length=1, max_length=500)
    ]  # every component must justify itself


class Assumption(Strict):
    statement: Annotated[str, StringConstraints(max_length=500)]
    impact: Impact
    confirmed_by_user: bool = False


class SecurityDesign(Strict):
    network_isolation: Annotated[str, StringConstraints(max_length=500)]
    encryption_at_rest: bool
    encryption_in_transit: bool
    secrets_strategy: Annotated[str, StringConstraints(max_length=500)]
    least_privilege_notes: Annotated[str, StringConstraints(max_length=1000)] | None = None
    public_endpoints: list[ShortStr] = Field(default_factory=list)


class CostLine(Strict):
    component_id: str
    monthly_usd: float = Field(ge=0)
    basis: Annotated[str, StringConstraints(max_length=300)]


class CostEstimate(Strict):
    currency: Literal["USD"] = "USD"
    monthly_total: float = Field(ge=0)
    lines: Annotated[list[CostLine], Field(max_length=200)] = Field(default_factory=list)
    pricing_as_of: str  # ISO date
    confidence: Confidence

    @model_validator(mode="after")
    def _sum(self) -> CostEstimate:
        if abs(sum(line.monthly_usd for line in self.lines) - self.monthly_total) > 0.01:
            raise ValueError("monthly_total must equal the sum of lines")
        return self


class ArchitecturePlan(Strict):
    schema_version: Literal["1.0"] = "1.0"
    source_analysis_id: UUID
    region: Region
    components: Annotated[list[Component], Field(min_length=1, max_length=100)]
    assumptions: list[Assumption] = Field(default_factory=list)
    security: SecurityDesign
    cost: CostEstimate
    risks: list[Finding] = Field(default_factory=list)
    requires_human_approval: Literal[True] = True  # an LLM can never output False

    @model_validator(mode="after")
    def _graph(self) -> ArchitecturePlan:
        ids = [c.id for c in self.components]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate component ids")
        known = set(ids)
        for c in self.components:
            missing = [d for d in c.depends_on if d not in known]
            if missing:
                raise ValueError(f"component {c.id} depends on unknown {missing}")
        for line in self.cost.lines:
            if line.component_id not in known:
                raise ValueError(f"cost line for unknown component {line.component_id}")
        return self


if __name__ == "__main__":  # self-check: python ai_contracts.py
    import pydantic

    print("pydantic", pydantic.VERSION)
    sha = "c3d4e5f60718293a4b5c6d7e8f90123456789012"
    repo = RepositoryRef(owner="acme", name="demo-shop", branch="main", commit_sha=sha)
    meta = AnalysisMeta(
        analyzer_version="0.1.0", files_scanned=84, files_skipped=210, duration_ms=8120
    )
    ok = AnalysisReport(
        repository=repo, summary="FastAPI + PostgreSQL", overall_confidence=0.9, meta=meta
    )
    assert ok.is_deployable
    blocked = AnalysisReport(
        repository=repo,
        summary="x",
        overall_confidence=0.5,
        meta=meta,
        blockers=[Finding(code="NO_LISTEN_PORT", severity=Severity.BLOCKER, message="no port")],
    )
    assert not blocked.is_deployable
    for bad in (
        lambda: AnalysisReport(repository=repo, summary="x", overall_confidence=1.5, meta=meta),
        lambda: AnalysisReport.model_validate(
            {
                "repository": repo,
                "summary": "x",
                "overall_confidence": 0.5,
                "meta": meta,
                "nope": 1,
            }
        ),
        lambda: AgentResult[AnalysisReport](ok=True),
        lambda: EnvVar(name="lower_case"),
    ):
        try:
            bad()
        except Exception as e:
            assert isinstance(e, pydantic.ValidationError | ValueError)
        else:
            raise SystemExit("expected validation failure")
    plan = ArchitecturePlan(
        source_analysis_id=UUID("00000000-0000-0000-0000-000000000001"),
        region="eu-central-1",
        components=[
            Component(id="api", type=ComponentType.ECS_SERVICE, rationale="runs the API container")
        ],
        security=SecurityDesign(
            network_isolation="private subnets",
            encryption_at_rest=True,
            encryption_in_transit=True,
            secrets_strategy="Secrets Manager",
        ),
        cost=CostEstimate(
            monthly_total=30.0,
            lines=[CostLine(component_id="api", monthly_usd=30.0, basis="0.5 vCPU")],
            pricing_as_of="2026-10-01",
            confidence=0.6,
        ),
    )
    try:
        ArchitecturePlan.model_validate({**plan.model_dump(), "requires_human_approval": False})
    except pydantic.ValidationError:
        pass
    else:
        raise SystemExit("requires_human_approval=False must be rejected")
    print(AgentResult[AnalysisReport](ok=True, result=ok).model_dump_json()[:80], "...")
    print("contracts OK")
