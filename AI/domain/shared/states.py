from enum import StrEnum


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_INPUT = "awaiting_input"
    BLOCKED = "blocked"          # analysis finished, but blockers prevent deployment
    SUCCEEDED = "succeeded"
    FAILED = "failed"