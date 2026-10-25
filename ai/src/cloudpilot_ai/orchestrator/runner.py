"""Public entry point: run one analysis job through the graph."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from cloudpilot_ai.contracts import (
    AnalysisReport,
    AnalysisRequest,
    ArchitecturePlan,
    ErrorInfo,
    JobStatus,
    Usage,
)
from cloudpilot_ai.errors import AgentError, Budget
from cloudpilot_ai.orchestrator.comm import (
    AnalysisAgent,
    ArchitectureAgent,
    CommunicationModule,
    Policies,
)
from cloudpilot_ai.orchestrator.graph import build_graph
from cloudpilot_ai.ports import (
    AgentKind,
    CancelToken,
    EventSink,
    InfraDiscovery,
    LLMGateway,
    RepositoryGateway,
    TaskStatus,
)
from cloudpilot_ai.trace import Tracer, as_agent_error, status_for


@dataclass
class JobOutcome:
    status: JobStatus
    report: AnalysisReport | None = None
    plan: ArchitecturePlan | None = None
    error: ErrorInfo | None = None
    warnings: list[ErrorInfo] = field(default_factory=list)


class _ClosingSink:
    """Serializes events (parallel graph branches, agent threads) and drops anything that
    arrives after the job finished, e.g. from an agent thread abandoned by a stage timeout."""

    def __init__(self, inner: EventSink) -> None:
        self._inner = inner
        self._lock = threading.Lock()
        self._closed = False

    def close(self) -> None:
        with self._lock:
            self._closed = True

    def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            if self._closed:
                return "dropped"
            return getattr(self._inner, method)(*args, **kwargs)

    def job_started(self) -> None:
        self._call("job_started")

    def run_started(self, agent: AgentKind, *, input_summary: dict[str, Any]) -> str:
        return str(self._call("run_started", agent, input_summary=input_summary))

    def task_started(
        self, run_id: str, task_type: str, *, input_summary: dict[str, Any] | None = None
    ) -> str:
        return str(self._call("task_started", run_id, task_type, input_summary=input_summary))

    def task_finished(
        self,
        task_id: str,
        *,
        status: TaskStatus,
        output_summary: dict[str, Any] | None = None,
        error: ErrorInfo | None = None,
    ) -> None:
        self._call(
            "task_finished", task_id, status=status, output_summary=output_summary, error=error
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
        self._call(
            "run_finished",
            run_id,
            status=status,
            usage=usage,
            output_summary=output_summary,
            error=error,
        )

    def report_ready(self, report: AnalysisReport) -> None:
        self._call("report_ready", report)

    def plan_ready(self, plan: ArchitecturePlan) -> None:
        self._call("plan_ready", plan)


def run_analysis(
    request: AnalysisRequest,
    *,
    repository: RepositoryGateway,
    sink: EventSink,
    analysis_agent: AnalysisAgent,
    architecture_agent: ArchitectureAgent | None = None,
    llm: LLMGateway | None = None,
    infra: InfraDiscovery | None = None,
    cancel: CancelToken | None = None,
    timeout_s: float = 600,
    region: str = "us-east-1",
    policies: Policies | None = None,
) -> JobOutcome:
    """Run the analysis pipeline (and the architecture agent when one is given).

    Never raises for job-level failures: they come back as a JobOutcome with an ErrorInfo.
    """
    guarded = _ClosingSink(sink)
    tracer = Tracer(guarded)
    budget = Budget(seconds=timeout_s, cancel=cancel)
    comm = CommunicationModule(
        tracer=tracer,
        budget=budget,
        repository=repository,
        analysis_agent=analysis_agent,
        architecture_agent=architecture_agent,
        llm=llm,
        infra=infra,
        policies=policies,
    )
    graph = build_graph(comm, source_analysis_id=request.job_id)
    final: dict[str, Any] = {}
    orchestrator_error: AgentError | None = None
    try:
        with tracer.run(
            "ORCHESTRATOR",
            {
                "job_id": str(request.job_id),
                "architect": comm.has_architect,
                "timeout_s": timeout_s,
            },
        ) as run:
            final = graph.invoke({"request": request, "region": region, "warnings": []})
            fatal = final.get("fatal")
            if isinstance(fatal, AgentError):
                raise fatal  # marks the ORCHESTRATOR run with the job's failure status
            run.output = {"outcome": final.get("outcome")}
            run.status = JobStatus(final["outcome"])
    except Exception as exc:
        orchestrator_error = as_agent_error(exc, "orchestration")
    finally:
        guarded.close()

    warnings = list(final.get("warnings") or [])
    if orchestrator_error is not None:
        return JobOutcome(
            status=status_for(orchestrator_error),
            report=final.get("report"),
            error=orchestrator_error.info,
            warnings=warnings,
        )
    return JobOutcome(
        status=JobStatus(final["outcome"]),
        report=final.get("report"),
        plan=final.get("plan"),
        warnings=warnings,
    )
