"""Orchestrate AI agents for cloud deployment analysis."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from agents.architecture.agent import ArchitectureAgent
from agents.architecture.models import ArchitectureProposal
from agents.code_analyzer import (
    AnalysisReport,
    CodeAnalyzerAgent,
    RepositoryAnalysis,
)
from workflows.repository import RepoSnapshot

ValidationStatus = Literal["not_run", "passed", "failed", "error"]
PipelineStage = Literal["analysis", "architecture"]


@dataclass(frozen=True, slots=True)
class OrchestrationResult:
    """Structured result returned by the orchestration pipeline."""

    analysis: AnalysisReport | None
    validation_status: ValidationStatus = "not_run"
    repository_analysis: RepositoryAnalysis | None = None
    architecture_proposal: ArchitectureProposal | None = None
    failed_stage: PipelineStage | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        """Ensure failure metadata is internally consistent."""
        if self.failed_stage is None and self.error is not None:
            raise ValueError("An error requires a failed pipeline stage")

        if self.failed_stage is not None and not self.error:
            raise ValueError("A failed pipeline stage requires an error")

        if self.failed_stage == "analysis" and self.repository_analysis is not None:
            raise ValueError("Failed analysis cannot contain repository analysis")

        if self.failed_stage == "architecture" and self.repository_analysis is None:
            raise ValueError(
                "Architecture failure requires successful repository analysis"
            )

        if self.failed_stage is not None and self.architecture_proposal is not None:
            raise ValueError(
                "A failed pipeline cannot contain an architecture proposal"
            )

    @property
    def success(self) -> bool:
        """Return whether the orchestration pipeline completed without an exception."""
        return self.failed_stage is None


class Orchestrator:
    """Coordinate analysis and optional architecture design."""

    def __init__(
        self,
        code_analyzer: CodeAnalyzerAgent | None = None,
        architecture_agent: ArchitectureAgent | None = None,
    ) -> None:
        self._code_analyzer = code_analyzer or CodeAnalyzerAgent()
        self._architecture_agent = architecture_agent

    def run(self, sources: Mapping[str, str]) -> OrchestrationResult:
        """Analyze Python sources using the existing interface."""
        analysis = self._code_analyzer.run(sources)

        return OrchestrationResult(
            analysis=analysis,
            validation_status="not_run",
        )

    def run_repository(
        self,
        snapshot: RepoSnapshot,
        *,
        root_name: str = "",
        requirements: str = "",
    ) -> OrchestrationResult:
        """Analyze a repository and optionally propose its architecture."""
        try:
            repository_analysis = self._code_analyzer.analyze_repository(
                snapshot,
                root_name=root_name,
            )
        except Exception as exc:
            return OrchestrationResult(
                analysis=None,
                validation_status="not_run",
                failed_stage="analysis",
                error=self._error_message(exc),
            )

        if self._architecture_agent is None:
            return OrchestrationResult(
                analysis=repository_analysis.python_analysis,
                validation_status="not_run",
                repository_analysis=repository_analysis,
            )

        try:
            architecture_proposal = self._architecture_agent.run(
                repository_analysis,
                requirements=requirements,
            )
        except Exception as exc:
            return OrchestrationResult(
                analysis=repository_analysis.python_analysis,
                validation_status="not_run",
                repository_analysis=repository_analysis,
                failed_stage="architecture",
                error=self._error_message(exc),
            )

        return OrchestrationResult(
            analysis=repository_analysis.python_analysis,
            validation_status="not_run",
            repository_analysis=repository_analysis,
            architecture_proposal=architecture_proposal,
        )

    @staticmethod
    def _error_message(exc: Exception) -> str:
        """Return a concise error message without a traceback."""
        message = str(exc).strip()
        return f"{type(exc).__name__}: {message}" if message else type(exc).__name__
