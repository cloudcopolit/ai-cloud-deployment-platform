from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TeamMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    name: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    role: str
    joined_at: datetime


class TeamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    role: str
    created_at: datetime
    member_count: int = 1
    project_count: int = 0
    plan_code: str = "FREE"


class TeamCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class TeamUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
