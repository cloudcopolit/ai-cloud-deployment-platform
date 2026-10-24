from typing import Protocol
from uuid import UUID

from AI.domain.analysis.models import AnalysisReport
from AI.domain.aws_detection.models import AwsRequirementsResult
from AI.domain.shared.states import RunStatus


class RunStore(Protocol):
    async def set_status(
        self, run_id: UUID, status: RunStatus, error_code: str | None = None
    ) -> None: ...

    async def save_results(
        self, run_id: UUID, report: AnalysisReport, aws: AwsRequirementsResult
    ) -> None: ...