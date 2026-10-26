"""Test doubles for the AI layer: a recording EventSink, in-memory repositories, report
builders. No network, no LLM."""

from __future__ import annotations

import hashlib
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from cloudpilot_ai.contracts import (
    AnalysisMeta,
    AnalysisReport,
    AnalysisRequest,
    ArchitecturePlan,
    ErrorInfo,
    JobStatus,
    RepositoryRef,
    Usage,
)
from cloudpilot_ai.ports import FileEntry, FileListing

SHA = "c3d4e5f60718293a4b5c6d7e8f90123456789012"


def request(**overrides: Any) -> AnalysisRequest:
    values: dict[str, Any] = {
        "job_id": uuid.UUID(int=7),
        "correlation_id": "corr-1",
        "repository": RepositoryRef(owner="acme", name="shop", branch="main", commit_sha=SHA),
        "github_installation_ref": "repository:test",
    }
    return AnalysisRequest(**(values | overrides))


def report(**overrides: Any) -> AnalysisReport:
    values: dict[str, Any] = {
        "repository": RepositoryRef(owner="acme", name="shop", branch="main", commit_sha=SHA),
        "summary": "test report",
        "overall_confidence": 0.9,
        "meta": AnalysisMeta(analyzer_version="t", files_scanned=1, files_skipped=0, duration_ms=1),
    }
    return AnalysisReport(**(values | overrides))


@dataclass
class Event:
    kind: str
    args: dict[str, Any] = field(default_factory=dict)


class RecordingSink:
    def __init__(self) -> None:
        self.events: list[Event] = []
        self._ids = 0
        self._lock = threading.Lock()
        self.reports: list[AnalysisReport] = []
        self.plans: list[ArchitecturePlan] = []

    def _id(self, prefix: str) -> str:
        with self._lock:
            self._ids += 1
            return f"{prefix}-{self._ids}"

    def job_started(self) -> None:
        self.events.append(Event("job_started"))

    def run_started(self, agent: str, *, input_summary: dict[str, Any]) -> str:
        run_id = self._id("run")
        self.events.append(Event("run_started", {"id": run_id, "agent": agent, **input_summary}))
        return run_id

    def task_started(
        self, run_id: str, task_type: str, *, input_summary: dict[str, Any] | None = None
    ) -> str:
        task_id = self._id("task")
        self.events.append(Event("task_started", {"id": task_id, "run": run_id, "type": task_type}))
        return task_id

    def task_finished(
        self,
        task_id: str,
        *,
        status: str,
        output_summary: dict[str, Any] | None = None,
        error: ErrorInfo | None = None,
    ) -> None:
        self.events.append(
            Event("task_finished", {"id": task_id, "status": status, "error": error})
        )

    def run_finished(
        self,
        run_id: str,
        *,
        status: JobStatus,
        usage: Usage | None = None,
        output_summary: dict[str, Any] | None = None,
        error: ErrorInfo | None = None,
    ) -> None:
        self.events.append(
            Event("run_finished", {"id": run_id, "status": status, "error": error, "usage": usage})
        )

    def report_ready(self, report: AnalysisReport) -> None:
        self.reports.append(report)
        self.events.append(Event("report_ready"))

    def plan_ready(self, plan: ArchitecturePlan) -> None:
        self.plans.append(plan)
        self.events.append(Event("plan_ready"))

    def runs(self) -> dict[str, tuple[str, JobStatus | None]]:
        started = {e.args["id"]: e.args["agent"] for e in self.events if e.kind == "run_started"}
        finished = {e.args["id"]: e.args["status"] for e in self.events if e.kind == "run_finished"}
        return {rid: (agent, finished.get(rid)) for rid, agent in started.items()}


class MemoryRepo:
    """RepositoryGateway over a dict of path -> text."""

    def __init__(self, files: dict[str, str], *, truncated: bool = False) -> None:
        self.files = files
        self.truncated = truncated
        self.reads: list[str] = []

    def list_files(self) -> FileListing:
        return FileListing(
            entries=[
                FileEntry(path=p, size=len(c.encode())) for p, c in sorted(self.files.items())
            ],
            truncated=self.truncated,
        )

    def read_file(self, path: str, max_bytes: int) -> bytes:
        self.reads.append(path)
        data = self.files[path].encode()
        if len(data) > max_bytes:
            raise ValueError("too large")
        return data


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class Flag:
    def __init__(self) -> None:
        self.value = False

    def is_cancelled(self) -> bool:
        return self.value
