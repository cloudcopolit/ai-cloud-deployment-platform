"""Shared contracts for CloudPilot AI workflow execution."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TaskStatus(StrEnum):
    """Lifecycle states for an AI workflow task."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(slots=True)
class TaskState:
    """Track the state and data associated with a workflow task."""

    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id must not be empty")


@dataclass(frozen=True, slots=True)
class AgentResult:
    """Standardized result returned by an AI agent."""

    agent_name: str
    success: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def __post_init__(self) -> None:
        if not self.agent_name.strip():
            raise ValueError("agent_name must not be empty")
        if self.success and self.error is not None:
            raise ValueError("A successful result cannot contain an error")
        if not self.success and not self.error:
            raise ValueError("A failed result must include an error")
