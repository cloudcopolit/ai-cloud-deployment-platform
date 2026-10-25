from uuid import UUID

from fastapi import APIRouter, status

from app.core.dependencies import DbSession
from app.modules.analysis import service
from app.modules.analysis.schemas import AnalysisCreate, AnalysisJobRead
from app.modules.auth.dependencies import CurrentUser

router = APIRouter(tags=["analysis"])


@router.post(
    "/repositories/{repo_id}/analyses",
    response_model=AnalysisJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_repository_analysis(
    repo_id: UUID,
    db: DbSession,
    user: CurrentUser,
    data: AnalysisCreate | None = None,
) -> AnalysisJobRead:
    payload = data or AnalysisCreate()
    return service.create_analysis_job(db, repo_id, user, payload)


@router.get("/analyses/{analysis_id}", response_model=AnalysisJobRead)
def get_analysis_by_id(analysis_id: UUID, db: DbSession, user: CurrentUser) -> AnalysisJobRead:
    return service.get_analysis_details(db, analysis_id, user)


@router.get("/repositories/{repo_id}/analyses", response_model=list[AnalysisJobRead])
def list_repository_analyses(
    repo_id: UUID, db: DbSession, user: CurrentUser
) -> list[AnalysisJobRead]:
    return service.list_repository_analyses(db, repo_id, user)


@router.get("/projects/{project_id}/analyses", response_model=list[AnalysisJobRead])
def list_project_analyses(
    project_id: UUID, db: DbSession, user: CurrentUser
) -> list[AnalysisJobRead]:
    return service.list_project_analyses(db, project_id, user)
