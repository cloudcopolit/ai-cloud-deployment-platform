from typing import TypedDict
from uuid import UUID

from AI.application.analysis.analyze_repository import AnalysisOutcome
from AI.domain.analysis.models import RepositoryRef


class WorkflowState(TypedDict, total=False):
    run_id: UUID
    repo: RepositoryRef
    outcome: AnalysisOutcome
    error_code: str | None