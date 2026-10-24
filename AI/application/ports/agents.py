from typing import Protocol

from AI.domain.analysis.models import AnalysisReport, RepositoryRef
from AI.domain.aws_detection.models import AwsConfigStatus, AwsRequirementsResult

from uuid import UUID

from AI.domain.analysis.blockers import Blocker
from AI.domain.analysis.models import AnalysisReport
from AI.domain.shared.states import RunStatus


class RunStore(Protocol):
    async def set_status(
        self, run_id: UUID, status: RunStatus, error_code: str | None = None
    ) -> None: ...

    async def save_analysis(
        self, run_id: UUID, report: AnalysisReport, blockers: tuple[Blocker, ...]
    ) -> None: ...
class RepositoryAnalyzer(Protocol):
    async def analyze(self, repo: RepositoryRef) -> AnalysisReport: ...


class AwsRequirementsDetector(Protocol):
    async def detect(
        self, report: AnalysisReport, config: AwsConfigStatus
    ) -> AwsRequirementsResult: ...