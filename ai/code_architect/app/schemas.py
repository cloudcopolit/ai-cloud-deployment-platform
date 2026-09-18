from typing import Literal
from pydantic import BaseModel, Field


ComponentType = Literal[
    "frontend", "backend", "database", "cache", "queue", "storage",
    "external_service", "infrastructure", "unknown",
]


class Component(BaseModel):
    id: str = Field(description="Short stable identifier, e.g. frontend or orders-api")
    name: str
    type: ComponentType
    technology: str = "Unknown"
    description: str
    evidence: list[str] = Field(default_factory=list)


class Connection(BaseModel):
    source: str
    target: str
    protocol: str = "unknown"
    description: str = ""


class Recommendation(BaseModel):
    title: str
    priority: Literal["low", "medium", "high"]
    rationale: str


class DeveloperIntent(BaseModel):
    goal: str | None = None
    depth: str | None = None
    focus: list[str] = Field(default_factory=list)
    scale: str | None = None
    deployment_target: str | None = None
    concerns: list[str] = Field(default_factory=list)
    cost_preference: Literal["minimize_cost", "balanced", "maximum_quality"] = "balanced"
    additional_context: str = ""


class ClarificationQuestion(BaseModel):
    field: str
    label: str
    type: Literal["single", "multi"] = "single"
    options: list[str]
    allow_other: bool = True


class IntakeResponse(BaseModel):
    complete: bool
    intent: DeveloperIntent
    missing_fields: list[str] = Field(default_factory=list)
    questions: list[ClarificationQuestion] = Field(default_factory=list)


class QualityReport(BaseModel):
    score: float
    threshold: float
    schema_valid: bool = True
    evidence_coverage: float = 0.0
    connection_validity: float = 0.0
    goal_coverage: float = 0.0
    recommendation_coverage: float = 0.0
    reasons: list[str] = Field(default_factory=list)


class RoutingInfo(BaseModel):
    mode: Literal["auto", "cheap", "strong"] = "auto"
    initial_route: Literal["cheap", "strong"]
    initial_model: str
    final_tier: Literal["cheap", "strong"]
    final_model: str
    pre_route_score: int = 0
    pre_route_threshold: int = 0
    pre_route_reasons: list[str] = Field(default_factory=list)
    cheap_attempted: bool = False
    escalated: bool = False
    escalation_reasons: list[str] = Field(default_factory=list)
    quality: QualityReport | None = None


class ArchitectureAnalysis(BaseModel):
    project_name: str
    summary: str
    detected_stack: list[str]
    components: list[Component]
    connections: list[Connection]
    recommendations: list[Recommendation]
    assumptions: list[str] = Field(default_factory=list)
    mermaid: str = ""
    routing: RoutingInfo | None = None
    intent: DeveloperIntent | None = None
