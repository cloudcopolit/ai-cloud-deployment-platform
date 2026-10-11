"""Structured data models for proposed application architectures."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ArchitectureComponent:
    """A component proposed for the application's architecture."""

    name: str
    responsibility: str
    technology: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Component name must not be empty")
        if not self.responsibility.strip():
            raise ValueError("Component responsibility must not be empty")


@dataclass(frozen=True, slots=True)
class ArchitectureProposal:
    """A proposed architecture with components, flows, and open questions."""

    project_name: str
    summary: str
    components: tuple[ArchitectureComponent, ...] = field(default_factory=tuple)
    interactions: tuple[str, ...] = field(default_factory=tuple)
    deployment_requirements: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    open_questions: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.project_name.strip():
            raise ValueError("Project name must not be empty")
        if not self.summary.strip():
            raise ValueError("Architecture summary must not be empty")
