"""The orchestrator as a LangGraph StateGraph (ADR-014, 06 §3.4).

Nodes are thin: they call the Communication Module, validate contracts and decide what runs
next. There is no repository-inspection logic here (enforced by test_orchestrator_has_no_
repository_logic). Pipeline:

    start ┬ analyze_repo ┬ validate_combine ─ evaluate ┬ save_blocked
          └ discover_infra┘        │                   ├ architect ─ validate_plan ─ save_success
                                   └─ save_failure ◄───┴────────────┘
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from cloudpilot_ai.contracts import (
    AnalysisReport,
    AnalysisRequest,
    ArchitecturePlan,
    ErrorCode,
    ErrorInfo,
    JobStatus,
    Stage,
)
from cloudpilot_ai.errors import AgentError
from cloudpilot_ai.orchestrator.comm import CommunicationModule
from cloudpilot_ai.trace import as_agent_error, status_for

Outcome = Literal["SUCCESS", "BLOCKED", "FAILED", "TIMED_OUT", "CANCELLED"]


class JobState(TypedDict, total=False):
    request: AnalysisRequest
    region: str
    report: AnalysisReport | None
    infra: dict[str, Any] | None
    plan: ArchitecturePlan | None
    fatal: AgentError | None
    warnings: Annotated[list[ErrorInfo], operator.add]
    outcome: Outcome


def _revalidate(model: Any, cls: type[Any], stage: Stage) -> Any:
    """Contracts are re-validated at the orchestrator boundary; invalid output is an error,
    never silently repaired (06 §2)."""
    try:
        return cls.model_validate(model.model_dump(mode="python"))
    except ValidationError as exc:
        errors = exc.errors()
        loc = errors[0]["loc"] if errors else ()
        raise AgentError.of(
            ErrorCode.SCHEMA_VALIDATION_FAILED,
            f"{cls.__name__} failed contract validation.",
            stage=stage,
            field=".".join(str(p) for p in loc) or None,
            reason=errors[0]["type"] if errors else None,
        ) from None


def build_graph(comm: CommunicationModule, *, source_analysis_id: UUID) -> Any:
    def start(state: JobState) -> JobState:
        comm.budget.check(Stage.FETCH_REPOSITORY)
        comm.tracer.sink.job_started()
        return {}

    def analyze_repo(state: JobState) -> JobState:
        try:
            return {"report": comm.analyze(state["request"])}
        except Exception as exc:
            return {"fatal": as_agent_error(exc, "analysis")}

    def discover_infra(state: JobState) -> JobState:
        infra, warning = comm.discover()
        return {"infra": infra, "warnings": [warning] if warning else []}

    def validate_combine(state: JobState) -> JobState:
        if state.get("fatal"):
            return {}
        try:
            comm.budget.check(Stage.VALIDATE_REPORT)
            report = _revalidate(state["report"], AnalysisReport, Stage.VALIDATE_REPORT)
        except AgentError as exc:
            return {"fatal": exc}
        return {"report": report}

    def evaluate(state: JobState) -> JobState:
        report = state["report"]
        assert report is not None  # noqa: S101 - guaranteed by the routing above
        if not report.is_deployable:
            return {"outcome": "BLOCKED"}
        return {"outcome": "SUCCESS"}

    def save_blocked(state: JobState) -> JobState:
        report = state["report"]
        assert report is not None  # noqa: S101
        comm.tracer.sink.report_ready(report)
        return {"outcome": "BLOCKED"}

    def architect(state: JobState) -> JobState:
        report = state["report"]
        assert report is not None  # noqa: S101
        try:
            plan = comm.architect(
                report, source_analysis_id=source_analysis_id, region=state["region"]
            )
            return {"plan": plan}
        except Exception as exc:
            return {"fatal": as_agent_error(exc, "architecture")}

    def validate_plan(state: JobState) -> JobState:
        if state.get("fatal"):
            return {}
        try:
            plan = _revalidate(state["plan"], ArchitecturePlan, Stage.VALIDATE_PLAN)
        except AgentError as exc:
            return {"fatal": exc}
        return {"plan": plan}

    def save_success(state: JobState) -> JobState:
        report, plan = state["report"], state.get("plan")
        assert report is not None  # noqa: S101
        comm.tracer.sink.report_ready(report)
        if plan is not None:
            comm.tracer.sink.plan_ready(plan)
        return {"outcome": "SUCCESS"}

    def save_failure(state: JobState) -> JobState:
        fatal = state.get("fatal")
        if state.get("report") is not None:  # keep partial results (e.g. architecture failed)
            comm.tracer.sink.report_ready(state["report"])  # type: ignore[arg-type]
        status = status_for(fatal) if fatal else JobStatus.FAILED
        return {"outcome": status.value}  # type: ignore[typeddict-item]

    def after_validate(state: JobState) -> str:
        return "fail" if state.get("fatal") else "ok"

    def after_evaluate(state: JobState) -> str:
        if state["outcome"] == "BLOCKED":
            return "blocked"
        return "architect" if comm.has_architect else "done"

    graph = StateGraph(JobState)
    for name, node in (
        ("start", start),
        ("analyze_repo", analyze_repo),
        ("discover_infra", discover_infra),
        ("validate_combine", validate_combine),
        ("evaluate", evaluate),
        ("save_blocked", save_blocked),
        ("architect", architect),
        ("validate_plan", validate_plan),
        ("save_success", save_success),
        ("save_failure", save_failure),
    ):
        graph.add_node(name, node)

    graph.add_edge(START, "start")
    graph.add_edge("start", "analyze_repo")
    graph.add_edge("start", "discover_infra")  # parallel fan-out (06 §3.2 step 2)
    graph.add_edge(["analyze_repo", "discover_infra"], "validate_combine")  # fan-in
    graph.add_conditional_edges(
        "validate_combine", after_validate, {"ok": "evaluate", "fail": "save_failure"}
    )
    graph.add_conditional_edges(
        "evaluate",
        after_evaluate,
        {"blocked": "save_blocked", "architect": "architect", "done": "save_success"},
    )
    graph.add_edge("architect", "validate_plan")
    graph.add_conditional_edges(
        "validate_plan", after_validate, {"ok": "save_success", "fail": "save_failure"}
    )
    for terminal in ("save_blocked", "save_success", "save_failure"):
        graph.add_edge(terminal, END)
    return graph.compile()
