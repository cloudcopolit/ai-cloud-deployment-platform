from uuid import UUID

from fastapi import APIRouter, status

from app.core.dependencies import DbSession
from app.modules.architectures import service
from app.modules.architectures.schemas import (
    ArchitectureGenerateRequest,
    ArchitectureRead,
    ArchitectureVersionRead,
)
from app.modules.auth.dependencies import CurrentUser

router = APIRouter(tags=["architectures"])


@router.post(
    "/analyses/{analysis_id}/architectures",
    response_model=ArchitectureVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def generate_architecture_from_analysis(
    analysis_id: UUID,
    db: DbSession,
    user: CurrentUser,
    data: ArchitectureGenerateRequest | None = None,
) -> ArchitectureVersionRead:
    payload = data or ArchitectureGenerateRequest()
    return service.generate_architecture_proposal(db, analysis_id, user, payload)


@router.get(
    "/projects/{project_id}/architectures",
    response_model=list[ArchitectureRead],
)
def get_project_architectures(
    project_id: UUID, db: DbSession, user: CurrentUser
) -> list[ArchitectureRead]:
    return service.list_project_architectures(db, project_id, user)


@router.get(
    "/architectures/{architecture_id}/versions/{version_number}",
    response_model=ArchitectureVersionRead,
)
def get_architecture_version_detail(
    architecture_id: UUID,
    version_number: int,
    db: DbSession,
    user: CurrentUser,
) -> ArchitectureVersionRead:
    return service.get_architecture_version(db, architecture_id, version_number, user)
