from typing import TypedDict
from uuid import UUID

from AI.application.analysis.analyze_repository import AnalysisOutcome
from AI.domain.analysis.models import (
    AnalysisManifest,
    RepositoryRef,
    UserFact,
    ValidationResult,
)


class WorkflowState(TypedDict, total=False):
    run_id: UUID
    repo: RepositoryRef
    user_facts: tuple[UserFact, ...]
    validation_feedback: tuple[str, ...]
    validation_result: ValidationResult
    retry_count: int
    outcome: AnalysisOutcome
    error_code: str | None
