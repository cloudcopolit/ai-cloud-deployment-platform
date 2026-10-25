"""The backend side of the persistence hook (06 §7): orchestrator events -> database rows.

Each event is its own short transaction so the dashboard sees progress while the job runs.
Only summaries reach the database: the AI layer never sends secrets or file contents, and
summaries are size-bounded here as a second line of defence.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from cloudpilot_ai.contracts import (
    AnalysisReport,
    ArchitecturePlan,
    ErrorInfo,
    JobStatus,
    Usage,
)
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import AgentRun, AgentTask, RepositoryAnalysis, Service

MAX_SUMMARY_BYTES = 8_000


def _bounded(summary: dict[str, Any] | None) -> dict[str, Any] | None:
    if summary is None:
        return None
    text = json.dumps(summary, default=str)
    if len(text) <= MAX_SUMMARY_BYTES:
        return json.loads(text)
    return {"truncated": True, "keys": sorted(summary)[:50]}


def _now() -> datetime:
    return datetime.now(UTC)


class DbEventSink:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        analysis_id: uuid.UUID,
        project_id: uuid.UUID,
        on_plan: Callable[[Session, ArchitecturePlan], None] | None = None,
    ) -> None:
        self._sessions = session_factory
        self.analysis_id = analysis_id
        self.project_id = project_id
        self._on_plan = on_plan

    def job_started(self) -> None:
        pass  # the queue already marked the job RUNNING when it was claimed

    def run_started(self, agent: str, *, input_summary: dict[str, Any]) -> str:
        with self._sessions() as db:
            run = AgentRun(
                project_id=self.project_id,
                analysis_id=self.analysis_id,
                agent_type=agent,
                status="RUNNING",
                started_at=_now(),
                input_data=_bounded(input_summary),
            )
            db.add(run)
            db.commit()
            return str(run.id)

    def task_started(
        self, run_id: str, task_type: str, *, input_summary: dict[str, Any] | None = None
    ) -> str:
        with self._sessions() as db:
            order = (
                db.scalar(
                    select(func.max(AgentTask.step_order)).where(
                        AgentTask.agent_run_id == uuid.UUID(run_id)
                    )
                )
                or 0
            ) + 1
            task = AgentTask(
                agent_run_id=uuid.UUID(run_id),
                task_type=task_type[:48],
                status="RUNNING",
                step_order=order,
                started_at=_now(),
                input_data=_bounded(input_summary),
            )
            db.add(task)
            db.commit()
            return str(task.id)

    def task_finished(
        self,
        task_id: str,
        *,
        status: str,
        output_summary: dict[str, Any] | None = None,
        error: ErrorInfo | None = None,
    ) -> None:
        with self._sessions() as db:
            task = db.get(AgentTask, uuid.UUID(task_id))
            if task is None:
                return
            task.status = status
            task.completed_at = _now()
            task.output_data = _bounded(output_summary)
            if error is not None:
                task.error_code = error.code.value
                task.error_message = error.message
            db.commit()

    def run_finished(
        self,
        run_id: str,
        *,
        status: JobStatus,
        usage: Usage | None = None,
        output_summary: dict[str, Any] | None = None,
        error: ErrorInfo | None = None,
    ) -> None:
        with self._sessions() as db:
            run = db.get(AgentRun, uuid.UUID(run_id))
            if run is None:
                return
            run.status = status.value
            run.completed_at = _now()
            run.output_data = _bounded(output_summary)
            if usage is not None:
                run.usage = usage.model_dump(mode="json")
                run.model = usage.model
            if error is not None:
                run.error_code = error.code.value
                run.error_message = error.message
            db.commit()

    def report_ready(self, report: AnalysisReport) -> None:
        with self._sessions() as db:
            analysis = db.get(RepositoryAnalysis, self.analysis_id)
            if analysis is None:
                return
            analysis.analysis_data = report.model_dump(mode="json")
            analysis.report_schema_version = report.schema_version
            # services is the normalized, queryable copy of report.services (ADR-006)
            db.execute(delete(Service).where(Service.analysis_id == self.analysis_id))
            for s in report.services:
                db.add(
                    Service(
                        analysis_id=self.analysis_id,
                        name=s.name,
                        service_type=s.service_type.value,
                        language=s.language,
                        framework=s.framework,
                        path=s.path,
                        port=s.port,
                        metadata_={
                            **{k: v for k, v in s.metadata.items() if v is not None},
                            "has_dockerfile": s.has_dockerfile,
                            "health_endpoint": s.health_endpoint,
                            "confidence": s.confidence,
                        },
                    )
                )
            db.commit()

    def plan_ready(self, plan: ArchitecturePlan) -> None:
        if self._on_plan is None:
            return
        with self._sessions() as db:
            self._on_plan(db, plan)
            db.commit()
