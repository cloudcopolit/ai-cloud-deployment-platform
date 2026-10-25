from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RepositoryConnect(BaseModel):
    url: str = Field(..., max_length=500)
    github_repository_id: str | None = Field(default=None, max_length=50)
    owner: str | None = Field(default=None, max_length=255)
    name: str | None = Field(default=None, max_length=255)
    default_branch: str = Field("main", max_length=255)


class RepositoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    github_repository_id: str
    owner: str
    name: str
    url: str
    default_branch: str
    deployment_branch: str | None = None
    connected_at: datetime
    updated_at: datetime


class BranchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    repository_id: UUID
    name: str
    is_default: bool
    is_deployment_branch: bool


class DeploymentBranchUpdate(BaseModel):
    branch_name: str = Field(..., max_length=255)


class CommitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    repository_id: UUID
    branch_id: UUID
    sha: str
    message: str
    author_name: str | None = None
    author_email: str | None = None
    committed_at: datetime


class AvailableRepository(BaseModel):
    id: str
    name: str
    full_name: str
    description: str | None = None
    default_branch: str = "main"
    url: str
    language: str | None = None
    is_template: bool = False
