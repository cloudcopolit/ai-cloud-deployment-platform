"""Ports: everything the AI layer needs from the outside world, as interfaces.

The backend implements them (GitHub access, persistence) or configures the ones that live
here (the LLM gateway). Agents and the orchestrator depend only on these Protocols, which is
what keeps the package stateless and testable with fakes (ADR-009, 06 §6).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import BaseModel

from cloudpilot_ai.contracts import (
    AnalysisReport,
    ArchitecturePlan,
    ErrorInfo,
    JobStatus,
    Usage,
)

AgentKind = Literal["ORCHESTRATOR", "ANALYSIS", "ARCHITECTURE"]
TaskStatus = Literal["SUCCESS", "FAILED", "SKIPPED"]


# ───────────────────────── repository access ─────────────────────────
@dataclass(frozen=True)
class FileEntry:
    path: str
    size: int


@dataclass(frozen=True)
class FileListing:
    entries: list[FileEntry]
    truncated: bool  # the host could not list everything


class RepositoryGateway(Protocol):
    """Read-only access to ONE repository at ONE commit. Implementations resolve credentials
    themselves; the AI layer never sees a token."""

    def list_files(self) -> FileListing: ...

    def read_file(self, path: str, max_bytes: int) -> bytes: ...


# ───────────────────────── LLM ─────────────────────────
@dataclass(frozen=True)
class LLMResponse:
    data: BaseModel  # validated against the schema the caller asked for
    usage: Usage


class LLMGateway(Protocol):
    """Structured-output completion behind provider fallback, budgets and redaction."""

    @property
    def available(self) -> bool:
        """False when no provider has credentials (every call would be mocked)."""
        ...

    def complete_json(
        self,
        *,
        task: str,
        system: str,
        user: str,
        schema: type[BaseModel],
    ) -> LLMResponse: ...


# ───────────────────────── AWS discovery (Q-5: deferred) ─────────────────────────
class InfraDiscovery(Protocol):
    def discover(self) -> dict[str, Any] | None: ...


# ───────────────────────── persistence hook (06 §7) ─────────────────────────
class EventSink(Protocol):
    """State changes the backend persists. Payloads are summaries: never secrets, tokens or
    repository content."""

    def job_started(self) -> None: ...

    def run_started(self, agent: AgentKind, *, input_summary: dict[str, Any]) -> str: ...

    def task_started(
        self, run_id: str, task_type: str, *, input_summary: dict[str, Any] | None = None
    ) -> str: ...

    def task_finished(
        self,
        task_id: str,
        *,
        status: TaskStatus,
        output_summary: dict[str, Any] | None = None,
        error: ErrorInfo | None = None,
    ) -> None: ...

    def run_finished(
        self,
        run_id: str,
        *,
        status: JobStatus,
        usage: Usage | None = None,
        output_summary: dict[str, Any] | None = None,
        error: ErrorInfo | None = None,
    ) -> None: ...

    def report_ready(self, report: AnalysisReport) -> None: ...

    def plan_ready(self, plan: ArchitecturePlan) -> None: ...


class CancelToken(Protocol):
    def is_cancelled(self) -> bool: ...
