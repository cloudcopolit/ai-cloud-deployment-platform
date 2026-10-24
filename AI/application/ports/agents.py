from __future__ import annotations

from typing import Protocol
from uuid import UUID

from AI.domain.analysis.blockers import Blocker
from AI.domain.analysis.models import (
    AnalysisManifest,
    RepositoryRef,
    UserFact,
    ValidationResult,
)
from AI.domain.aws_detection.models import AwsConfigStatus, AwsRequirementsResult
from AI.domain.shared.states import RunStatus


class RunStore(Protocol):
    async def set_status(
        self, run_id: UUID, status: RunStatus, error_code: str | None = None
    ) -> None: ...

    async def save_analysis(
        self, run_id: UUID, report: AnalysisManifest, blockers: tuple[Blocker, ...]
    ) -> None: ...


class RepositoryAnalyzer(Protocol):
    async def analyze(
        self,
        repo: RepositoryRef,
        *,
        validation_feedback: tuple[str, ...] = (),
        user_facts: tuple[UserFact, ...] = (),
    ) -> AnalysisManifest: ...


class ManifestValidator(Protocol):
    async def validate(
        self,
        manifest: AnalysisManifest,
        *,
        finalize_unresolved: bool = False,
    ) -> ValidationResult: ...


class AwsRequirementsDetector(Protocol):
    async def detect(
        self, report: AnalysisManifest, config: AwsConfigStatus
    ) -> AwsRequirementsResult: ...
