"""Agent interface for deterministic repository and Python code analysis."""

from collections.abc import Mapping

from agents.code_analyzer.analyzer import (
    AnalysisReport,
    analyze_python_sources,
)
from agents.code_analyzer.repository_analyzer import (
    RepositoryAnalysis,
    analyze_repository,
)
from workflows.repository import RepoSnapshot


class CodeAnalyzerAgent:
    """Analyze repository metadata and Python source without execution."""

    def run(self, sources: Mapping[str, str]) -> AnalysisReport:
        """Analyze Python source files; preserve the existing interface."""
        return analyze_python_sources(sources)

    def analyze_repository(
        self,
        snapshot: RepoSnapshot,
        *,
        root_name: str = "",
    ) -> RepositoryAnalysis:
        """Analyze repository structure, metadata, dependencies, and Python."""
        return analyze_repository(snapshot, root_name=root_name)
