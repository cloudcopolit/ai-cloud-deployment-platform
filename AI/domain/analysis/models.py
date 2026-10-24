from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4


@dataclass(frozen=True)
class RepositoryRef:
    owner: str
    name: str
    commit_sha: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


@dataclass(frozen=True)
class LanguageStat:
    name: str
    bytes_of_code: int


@dataclass(frozen=True)
class Dependency:
    name: str
    ecosystem: str  # "npm", "pip", "maven", ...
    version: str | None = None


class ComponentType(StrEnum):
    STATIC = "static"
    SERVER = "server"
    WORKER = "worker"


class EnvScope(StrEnum):
    BUILD = "build"
    RUNTIME = "runtime"


class FactSource(StrEnum):
    USER = "user"
    SCANNER = "scanner"
    LLM = "llm"


class ValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class Evidence:
    field: str
    file: str
    lines: tuple[int, int] | None = None
    snippet: str = ""

    def __post_init__(self) -> None:
        if not self.file:
            raise ValueError(f"evidence for {self.field!r} must reference a file")
        if self.lines is not None:
            start, end = self.lines
            if start < 1 or end < start:
                raise ValueError(f"invalid line range {self.lines} for {self.file}")


@dataclass(frozen=True)
class EnvVarSpec:
    name: str
    required: bool = True
    scope: EnvScope = EnvScope.RUNTIME
    is_secret: bool = False

    def __post_init__(self) -> None:
        if not self.name or "=" in self.name:
            raise ValueError(
                "env_vars must contain only the variable name, never a value or '=' assignment"
            )


@dataclass(frozen=True)
class ServiceDependency:
    name: str  # e.g., "postgres", "redis", "s3", "sqs"
    kind: str = "service"  # "database", "cache", "queue", "storage", "service"
    required: bool = True
    evidence_file: str | None = None


@dataclass(frozen=True)
class ComponentSpec:
    name: str
    root_dir: str
    type: ComponentType
    language: str
    runtime_version: str | None = None
    pkg_mgr: str | None = None
    build_cmd: str | None = None
    start_cmd: str | None = None
    output_dir: str | None = None
    port: int | None = None
    health_path: str | None = None
    env_vars: tuple[EnvVarSpec, ...] = ()
    dependencies: tuple[ServiceDependency, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    field_confidence: dict[str, float] = field(default_factory=dict)

    def confidence_for(self, field_name: str) -> float:
        return self.field_confidence.get(field_name, 0.0)


@dataclass(frozen=True)
class ComponentRelationship:
    source_component: str
    target_component: str
    kind: str = "http_api"  # e.g., "http_api", "websocket", "shared_db", "queue"
    via_env_var: str | None = None
    evidence: Evidence | None = None


@dataclass(frozen=True)
class OpenQuestion:
    component: str
    field_path: str  # e.g., "api.port", "web.start_cmd"
    question: str
    reason: str = ""


@dataclass(frozen=True)
class UserFact:
    component: str
    field_path: str
    value: str
    source: FactSource = FactSource.USER


@dataclass(frozen=True)
class ValidationIssue:
    component: str
    field: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR


@dataclass(frozen=True)
class AnalysisManifest:
    repo: RepositoryRef
    id: UUID = field(default_factory=uuid4)
    version: int = 1
    components: tuple[ComponentSpec, ...] = ()
    relationships: tuple[ComponentRelationship, ...] = ()
    topology: str = "single_service"
    topology_confidence: float = 1.0
    open_questions: tuple[OpenQuestion, ...] = ()
    input_ids: tuple[str, ...] = ()
    produced_by: str = "analysis_agent"
    languages: tuple[LanguageStat, ...] = ()
    frameworks: tuple[str, ...] = ()
    dependencies: tuple[Dependency, ...] = ()
    entry_points: tuple[str, ...] = ()
    summary: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def has_open_questions(self) -> bool:
        return bool(self.open_questions)


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    manifest: AnalysisManifest
    issues: tuple[ValidationIssue, ...] = ()

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity is ValidationSeverity.ERROR)

    @property
    def error_messages(self) -> tuple[str, ...]:
        return tuple(f"[{i.component}.{i.field}] {i.message}" for i in self.errors)


# Alias for backward compatibility across the codebase where AnalysisReport is referenced.
AnalysisReport = AnalysisManifest
