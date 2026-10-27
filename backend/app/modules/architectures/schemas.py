from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ArchitectureGenerateRequest(BaseModel):
    region: str = Field(default="us-east-1", max_length=32)
    name: str | None = Field(default=None, max_length=255)


class ArchitectureVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    architecture_id: UUID
    version_number: int
    source_analysis_id: UUID | None = None
    status: str
    architecture_data: dict
    created_by: UUID | None = None
    created_at: datetime
    monthly_cost: float = 0.0


class ArchitectureRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    status: str
    created_at: datetime
    updated_at: datetime
    versions_count: int = 0
    latest_version: ArchitectureVersionRead | None = None
