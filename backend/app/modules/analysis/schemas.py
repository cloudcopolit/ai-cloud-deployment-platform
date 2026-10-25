from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AnalysisCreate(BaseModel):
    commit_sha: str | None = Field(None, max_length=40)


class AnalysisJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    repository_id: UUID
    commit_id: UUID
    commit_sha: str
    status: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    requested_by: UUID | None = None
    error_code: str | None = None
    error_message: str | None = None
    services_count: int = 0
    report: dict | None = None
