from __future__ import annotations

from dataclasses import dataclass

from app.application.ports.agents import RepositoryAnalyzer
from app.domain.analysis.blockers import Blocker, evaluate_blockers
from app.domain.analysis.models import AnalysisReport, RepositoryRef
from app.domain.shared.errors import AnalysisFailedError


@dataclass(frozen=True)
class AnalysisOutcome:
    report: AnalysisReport
    blockers: tuple[Blocker, ...]

    @property
    def is_blocked(self) -> bool:
        return bool(self.blockers)


class AnalyzeRepository:
    def __init__(self, analyzer: RepositoryAnalyzer) -> None:
        self._analyzer = analyzer

    async def execute(self, repo: RepositoryRef) -> AnalysisOutcome:
        report = await self._analyzer.analyze(repo)

        # Guard against an agent returning a report for a different repo or commit.
        if report.repo != repo:
            raise AnalysisFailedError(
                f"report is for {report.repo.full_name}@{report.repo.commit_sha}, "
                f"expected {repo.full_name}@{repo.commit_sha}"
            )

        return AnalysisOutcome(report=report, blockers=evaluate_blockers(report))