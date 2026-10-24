from uuid import UUID

from AI.domain.analysis.blockers import Blocker
from AI.domain.analysis.models import AnalysisReport, RepositoryRef
from AI.domain.shared.errors import AnalysisFailedError
from AI.domain.shared.states import RunStatus


def make_repo() -> RepositoryRef:
    return RepositoryRef(owner="acme", name="api", commit_sha="abc123")


def make_report(
    repo: RepositoryRef | None = None,
    *,
    languages: bool = True,
    entry_points: bool = True,
) -> AnalysisReport:
    from AI.domain.analysis.models import LanguageStat

    return AnalysisReport(
        repo=repo or make_repo(),
        languages=(LanguageStat("Python", 1200),) if languages else (),
        frameworks=("fastapi",),
        dependencies=(),
        entry_points=("main.py",) if entry_points else (),
        summary="A small FastAPI service.",
    )


class FakeAnalyzer:
    def __init__(self, report: AnalysisReport | None = None, error: Exception | None = None):
        self._report = report
        self._error = error

    async def analyze(self, repo: RepositoryRef) -> AnalysisReport:
        if self._error is not None:
            raise self._error
        return self._report or make_report(repo)


class FakeStore:
    def __init__(self) -> None:
        self.statuses: list[tuple[RunStatus, str | None]] = []
        self.saved: list[tuple[UUID, AnalysisReport, tuple[Blocker, ...]]] = []

    async def set_status(self, run_id, status, error_code=None) -> None:
        self.statuses.append((status, error_code))

    async def save_analysis(self, run_id, report, blockers) -> None:
        self.saved.append((run_id, report, blockers))