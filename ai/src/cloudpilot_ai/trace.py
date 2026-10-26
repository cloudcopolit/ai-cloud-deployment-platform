"""Turns agent work into run/task events for the live activity view (06 §7).

    with tracer.run("ANALYSIS", input_summary={...}) as run:
        with run.task("fetch_tree") as task:
            task.output = {"files": 120}

Errors inside a task mark the task FAILED and propagate. Unexpected exceptions become
INTERNAL_ERROR with a generic message: exception text may echo repository content, so it is
never forwarded.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from cloudpilot_ai.contracts import ErrorCode, ErrorInfo, JobStatus, Usage
from cloudpilot_ai.errors import AgentError, JobCancelled, JobTimedOut
from cloudpilot_ai.ports import AgentKind, EventSink


def as_agent_error(exc: BaseException, where: str) -> AgentError:
    if isinstance(exc, AgentError):
        return exc
    return AgentError.of(
        ErrorCode.INTERNAL_ERROR,
        f"Internal error during {where}.",
        exception=type(exc).__name__,
    )


def status_for(error: AgentError) -> JobStatus:
    if isinstance(error, JobCancelled):
        return JobStatus.CANCELLED
    if isinstance(error, JobTimedOut) or error.info.code in {
        ErrorCode.JOB_TIMEOUT,
        ErrorCode.STAGE_TIMEOUT,
    }:
        return JobStatus.TIMED_OUT
    return JobStatus.FAILED


class TaskScope:
    def __init__(self) -> None:
        self.output: dict[str, Any] | None = None
        self.skipped = False


class RunScope:
    def __init__(self, sink: EventSink, run_id: str) -> None:
        self._sink = sink
        self.run_id = run_id
        self.usage: Usage | None = None
        self.output: dict[str, Any] | None = None
        self.status: JobStatus = JobStatus.SUCCESS  # e.g. BLOCKED for the orchestrator run

    @contextmanager
    def task(
        self, task_type: str, input_summary: dict[str, Any] | None = None
    ) -> Iterator[TaskScope]:
        task_id = self._sink.task_started(self.run_id, task_type, input_summary=input_summary)
        scope = TaskScope()
        try:
            yield scope
        except Exception as exc:
            error = as_agent_error(exc, task_type)
            self._sink.task_finished(task_id, status="FAILED", error=error.info)
            if error is exc:
                raise
            raise error from exc
        self._sink.task_finished(
            task_id, status="SKIPPED" if scope.skipped else "SUCCESS", output_summary=scope.output
        )


class Tracer:
    def __init__(self, sink: EventSink) -> None:
        self.sink = sink

    @contextmanager
    def run(self, agent: AgentKind, input_summary: dict[str, Any]) -> Iterator[RunScope]:
        run_id = self.sink.run_started(agent, input_summary=input_summary)
        scope = RunScope(self.sink, run_id)
        try:
            yield scope
        except Exception as exc:
            error = as_agent_error(exc, agent.lower())
            self.sink.run_finished(
                run_id, status=status_for(error), usage=scope.usage, error=error.info
            )
            if error is exc:
                raise
            raise error from exc
        self.sink.run_finished(
            run_id, status=scope.status, usage=scope.usage, output_summary=scope.output
        )


def error_info(code: ErrorCode, message: str) -> ErrorInfo:
    return ErrorInfo(code=code, message=message)
