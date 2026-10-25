from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

TERMINAL_STATUSES = ("SUCCESS", "BLOCKED", "FAILED", "TIMED_OUT", "CANCELLED")


class AnalysisCreate(BaseModel):
    """Which code to analyze. Defaults: the deployment branch and its head commit."""

    model_config = ConfigDict(extra="forbid")

    branch: str | None = Field(default=None, min_length=1, max_length=255)
    commit_sha: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")


class AnswersCreate(BaseModel):
    """Answers to a BLOCKED analysis's missing_info questions; starts a new analysis."""

    model_config = ConfigDict(extra="forbid")

    answers: dict[str, str] = Field(..., min_length=1, max_length=50)

    @field_validator("answers")
    @classmethod
    def _bounded(cls, value: dict[str, str]) -> dict[str, str]:
        for k, v in value.items():
            if not k or len(k) > 255 or len(v) > 255:
                raise ValueError("answer keys and values must be 1-255 characters")
        return {k: v.strip() for k, v in value.items()}


class AnalysisJobRead(BaseModel):
    id: UUID
    repository_id: UUID
    project_id: UUID
    commit_id: UUID
    commit_sha: str
    branch_name: str | None
    status: str
    terminal: bool
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    requested_by: UUID | None = None
    attempts: int
    cancel_requested: bool
    parent_analysis_id: UUID | None = None
    user_answers: dict[str, str] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    services_count: int = 0
    report: dict[str, Any] | None = None


class AgentTaskRead(BaseModel):
    id: UUID
    task_type: str
    status: str
    step_order: int
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    output: dict[str, Any] | None
    error_code: str | None
    error_message: str | None


class AgentRunRead(BaseModel):
    id: UUID
    agent_type: str
    status: str
    model: str | None
    usage: dict[str, Any] | None
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    input: dict[str, Any] | None
    output: dict[str, Any] | None
    error_code: str | None
    error_message: str | None
    tasks: list[AgentTaskRead]


class ActivityRead(BaseModel):
    """Everything the live agent view needs in one poll."""

    analysis_id: UUID
    status: str
    terminal: bool
    attempts: int
    cancel_requested: bool
    heartbeat_at: datetime | None
    runs: list[AgentRunRead]
