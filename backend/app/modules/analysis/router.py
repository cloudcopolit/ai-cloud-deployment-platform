from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response, status

from app.core.dependencies import DbSession
from app.integrations.github_app import GitHubClient, get_github_client
from app.modules.analysis import service
from app.modules.analysis.schemas import (
    ActivityRead,
    AnalysisCreate,
    AnalysisJobRead,
    AnswersCreate,
)
from app.modules.auth.dependencies import CurrentUser

router = APIRouter(tags=["analysis"])

GitHub = Annotated[GitHubClient, Depends(get_github_client)]
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=64)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def _accepted(response: Response, job: AnalysisJobRead) -> AnalysisJobRead:
    response.headers["Location"] = f"/analyses/{job.id}"
    return job


@router.post(
    "/repositories/{repo_id}/analyses",
    response_model=AnalysisJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_repository_analysis(
    repo_id: UUID,
    db: DbSession,
    user: CurrentUser,
    github: GitHub,
    response: Response,
    idempotency_key: IdempotencyKey = None,
    data: AnalysisCreate | None = None,
) -> AnalysisJobRead:
    """Queue an analysis (202). The worker runs it; poll GET /analyses/{id}."""
    job = service.create_analysis_job(
        db, github, repo_id, user, data or AnalysisCreate(), idempotency_key
    )
    return _accepted(response, job)


@router.get("/analyses/{analysis_id}", response_model=AnalysisJobRead)
def get_analysis_by_id(analysis_id: UUID, db: DbSession, user: CurrentUser) -> AnalysisJobRead:
    return service.get_analysis_details(db, analysis_id, user)


@router.get("/analyses/{analysis_id}/activity", response_model=ActivityRead)
def get_analysis_activity(analysis_id: UUID, db: DbSession, user: CurrentUser) -> ActivityRead:
    """Agent runs and their tasks, for the live activity view (poll every 1-2 s)."""
    return service.get_activity(db, analysis_id, user)


@router.get("/analyses/{analysis_id}/services")
def get_analysis_services(
    analysis_id: UUID, db: DbSession, user: CurrentUser
) -> list[dict[str, Any]]:
    return service.list_services(db, analysis_id, user)


@router.post(
    "/analyses/{analysis_id}/cancel",
    response_model=AnalysisJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def cancel_analysis(analysis_id: UUID, db: DbSession, user: CurrentUser) -> AnalysisJobRead:
    return service.cancel_analysis(db, analysis_id, user)


@router.post(
    "/analyses/{analysis_id}/answers",
    response_model=AnalysisJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def answer_analysis(
    analysis_id: UUID, data: AnswersCreate, db: DbSession, user: CurrentUser, response: Response
) -> AnalysisJobRead:
    """Answer a BLOCKED analysis's questions; queues a new analysis of the same commit."""
    return _accepted(response, service.answer_and_rerun(db, analysis_id, user, data))


@router.get("/repositories/{repo_id}/analyses", response_model=list[AnalysisJobRead])
def list_repository_analyses(
    repo_id: UUID, db: DbSession, user: CurrentUser, limit: Limit = 20, offset: Offset = 0
) -> list[AnalysisJobRead]:
    return service.list_repository_analyses(db, repo_id, user, limit, offset)


@router.get("/projects/{project_id}/analyses", response_model=list[AnalysisJobRead])
def list_project_analyses(
    project_id: UUID, db: DbSession, user: CurrentUser, limit: Limit = 20, offset: Offset = 0
) -> list[AnalysisJobRead]:
    return service.list_project_analyses(db, project_id, user, limit, offset)
