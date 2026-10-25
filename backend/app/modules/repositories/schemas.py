from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RepositoryConnect(BaseModel):
    """Connect by URL. Owner, name, id and default branch are resolved from GitHub, never
    taken from the client."""

    model_config = ConfigDict(extra="forbid")

    url: str = Field(..., min_length=3, max_length=500, examples=["https://github.com/owner/repo"])


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
    is_private: bool
    access_mode: Literal["GITHUB_APP", "TOKEN", "ANONYMOUS"]
    branch_count: int = 0
    branches_truncated: bool = False
    connected_at: datetime
    updated_at: datetime
    last_synced_at: datetime | None = None


class BranchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    repository_id: UUID
    name: str
    is_default: bool
    is_deployment_branch: bool


class DeploymentBranchUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_name: str = Field(..., min_length=1, max_length=255)


class CommitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    repository_id: UUID
    branch_id: UUID
    sha: str
    message: str
    author_name: str | None = None
    committed_at: datetime


class GitHubAccessRead(BaseModel):
    """What this CloudPilot deployment can reach on GitHub. Contains no secrets."""

    app_configured: bool
    app_installations: int | None
    app_install_url: str | None
    token_configured: bool
    rate_limit_remaining: int | None
    rate_limit_limit: int | None
    mode_for_public_repos: Literal["TOKEN", "ANONYMOUS", "GITHUB_APP"]
    webhook_enabled: bool
