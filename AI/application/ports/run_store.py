from __future__ import annotations

from typing import Protocol
from uuid import UUID

from AI.domain.analysis.blockers import Blocker
from AI.domain.analysis.models import AnalysisManifest
from AI.domain.aws_detection.models import AwsRequirementsResult
from AI.domain.shared.states import RunStatus


class RunStore(Protocol):
    async def set_status(
        self, run_id: UUID, status: RunStatus, error_code: str | None = None
    ) -> None: ...

    async def save_analysis(
        self, run_id: UUID, report: AnalysisManifest, blockers: tuple[Blocker, ...]
    ) -> None: ...

    async def save_results(
        self, run_id: UUID, report: AnalysisManifest, aws: AwsRequirementsResult
    ) -> None: ...
