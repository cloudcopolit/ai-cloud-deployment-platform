from __future__ import annotations

from dataclasses import dataclass

from AI.application.ports.agents import RepositoryAnalyzer
from AI.domain.analysis.blockers import Blocker, evaluate_blockers
from AI.domain.analysis.models import AnalysisManifest, RepositoryRef, UserFact
from AI.domain.shared.errors import AnalysisFailedError


@dataclass(frozen=True)
class AnalysisOutcome:
    report: AnalysisManifest
    blockers: tuple[Blocker, ...]

    @property
    def is_blocked(self) -> bool:
        return bool(self.blockers)


class AnalyzeRepository:
    def __init__(self, analyzer: RepositoryAnalyzer) -> None:
        self._analyzer = analyzer

    async def execute(
        self,
        repo: RepositoryRef,
        *,
        validation_feedback: tuple[str, ...] = (),
        user_facts: tuple[UserFact, ...] = (),
    ) -> AnalysisOutcome:
        try:
            report = await self._analyzer.analyze(
                repo,
                validation_feedback=validation_feedback,
                user_facts=user_facts,
            )
        except TypeError:
            # Backward compatibility for simple analyzers/fakes that only accept `repo`
            report = await self._analyzer.analyze(repo)

        # Guard against an agent returning a report for a different repo or commit.
        if report.repo != repo:
            raise AnalysisFailedError(
                f"report is for {report.repo.full_name}@{report.repo.commit_sha}, "
                f"expected {repo.full_name}@{repo.commit_sha}"
            )

        return AnalysisOutcome(report=report, blockers=evaluate_blockers(report))
