from typing import Literal
from pydantic import BaseModel, Field


ComponentType = Literal[
    "frontend",
    "backend",
    "database",
    "cache",
    "queue",
    "storage",
    "external_service",
    "infrastructure",
    "unknown",
]


class Component(BaseModel):
    id: str = Field(description="Short stable identifier, e.g. frontend or orders-api")
    name: str
    type: ComponentType
    technology: str = "Unknown"
    description: str
    evidence: list[str] = Field(
        default_factory=list,
        description="Repository files or facts that support this component",
    )


class Connection(BaseModel):
    source: str
    target: str
    protocol: str = "unknown"
    description: str = ""


class Recommendation(BaseModel):
    title: str
    priority: Literal["low", "medium", "high"]
    rationale: str


class ArchitectureAnalysis(BaseModel):
    project_name: str
    summary: str
    detected_stack: list[str]
    components: list[Component]
    connections: list[Connection]
    recommendations: list[Recommendation]
    assumptions: list[str] = Field(default_factory=list)
    mermaid: str = ""
