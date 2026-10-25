"""Orchestrator paths with fake agents (10 §5): no repository logic, no LLM, no network."""

from __future__ import annotations

import ast
import pathlib
import time
from uuid import UUID

import pytest
from cloudpilot_ai.contracts import (
    ArchitecturePlan,
    Component,
    ComponentType,
    CostEstimate,
    CostLine,
    ErrorCode,
    Finding,
    JobStatus,
    MissingInfo,
    SecurityDesign,
    Severity,
)
from cloudpilot_ai.errors import AgentError
from cloudpilot_ai.orchestrator import Policies, StagePolicy, run_analysis

from tests.fakes import Flag, MemoryRepo, RecordingSink, report, request


def plan(source: UUID) -> ArchitecturePlan:
    return ArchitecturePlan(
        source_analysis_id=source,
        region="us-east-1",
        components=[Component(id="api", type=ComponentType.ECS_SERVICE, rationale="runs it")],
        security=SecurityDesign(
            network_isolation="private",
            encryption_at_rest=True,
            encryption_in_transit=True,
            secrets_strategy="Secrets Manager",
        ),
        cost=CostEstimate(
            monthly_total=1.0,
            lines=[CostLine(component_id="api", monthly_usd=1.0, basis="x")],
            pricing_as_of="2026-10-01",
            confidence=0.5,
        ),
    )


def ok_agent(result=None):
    def agent(req, *, repository, llm, run, budget):
        with run.task("detect") as task:
            task.output = {"files": 1}
        return result or report()

    return agent


def architect_ok(rep, *, source_analysis_id, region, llm, run, budget):
    return plan(source_analysis_id)


REPO = MemoryRepo({"README.md": "hi"})


def test_success_without_architect_saves_report_only() -> None:
    sink = RecordingSink()
    outcome = run_analysis(request(), repository=REPO, sink=sink, analysis_agent=ok_agent())
    assert outcome.status is JobStatus.SUCCESS
    assert outcome.plan is None
    assert len(sink.reports) == 1
    assert sink.plans == []
    agents = sorted(a for a, _ in sink.runs().values())
    assert agents == ["ANALYSIS", "ORCHESTRATOR"]
    assert all(status is JobStatus.SUCCESS for _, status in sink.runs().values())
    assert sink.events[0].kind == "run_started"  # orchestrator run opens first
    assert any(e.kind == "job_started" for e in sink.events)


def test_success_with_architect_saves_report_and_plan() -> None:
    sink = RecordingSink()
    outcome = run_analysis(
        request(),
        repository=REPO,
        sink=sink,
        analysis_agent=ok_agent(),
        architecture_agent=architect_ok,
    )
    assert outcome.status is JobStatus.SUCCESS
    assert outcome.plan is not None
    assert outcome.plan.requires_human_approval is True
    assert outcome.plan.source_analysis_id == request().job_id
    assert len(sink.plans) == 1


@pytest.mark.parametrize(
    "blocked",
    [
        {"blockers": [Finding(code="NO_LISTEN_PORT", severity=Severity.BLOCKER, message="x")]},
        {"missing_info": [MissingInfo(key="port:api", question="Which port?")]},
    ],
)
def test_blocked_is_a_normal_outcome_and_skips_the_architect(blocked) -> None:
    sink = RecordingSink()
    calls = []

    def architect(*args, **kwargs):  # must never run
        calls.append(1)
        raise AssertionError

    outcome = run_analysis(
        request(),
        repository=REPO,
        sink=sink,
        analysis_agent=ok_agent(report(**blocked)),
        architecture_agent=architect,
    )
    assert outcome.status is JobStatus.BLOCKED
    assert outcome.error is None
    assert calls == []
    assert len(sink.reports) == 1
    orchestrator = [s for a, s in sink.runs().values() if a == "ORCHESTRATOR"]
    assert orchestrator == [JobStatus.BLOCKED]


def test_non_retryable_agent_error_fails_once() -> None:
    sink = RecordingSink()
    attempts = []

    def agent(req, *, repository, llm, run, budget):
        attempts.append(1)
        raise AgentError.of(ErrorCode.REPOSITORY_NOT_FOUND, "gone")

    outcome = run_analysis(request(), repository=REPO, sink=sink, analysis_agent=agent)
    assert outcome.status is JobStatus.FAILED
    assert outcome.error is not None
    assert outcome.error.code is ErrorCode.REPOSITORY_NOT_FOUND
    assert len(attempts) == 1
    assert sink.reports == []


def test_retryable_error_is_retried_then_succeeds() -> None:
    sink = RecordingSink()
    attempts = []

    def agent(req, *, repository, llm, run, budget):
        attempts.append(1)
        if len(attempts) == 1:
            raise AgentError.of(ErrorCode.LLM_UNAVAILABLE, "down", retryable=True)
        return report()

    outcome = run_analysis(request(), repository=REPO, sink=sink, analysis_agent=agent)
    assert outcome.status is JobStatus.SUCCESS
    assert len(attempts) == 2
    statuses = sorted(str(s) for a, s in sink.runs().values() if a == "ANALYSIS")
    assert statuses == ["FAILED", "SUCCESS"]  # both attempts are visible in the trace


def test_retries_are_bounded() -> None:
    attempts = []

    def agent(req, *, repository, llm, run, budget):
        attempts.append(1)
        raise AgentError.of(ErrorCode.LLM_TIMEOUT, "slow", retryable=True)

    outcome = run_analysis(request(), repository=REPO, sink=RecordingSink(), analysis_agent=agent)
    assert outcome.status is JobStatus.FAILED
    assert len(attempts) == 2  # 1 + 1 retry (06 §3.5)


def test_unexpected_exception_becomes_internal_error_without_leaking_text() -> None:
    def agent(req, *, repository, llm, run, budget):
        raise RuntimeError("password=hunter2 from a repo file")

    outcome = run_analysis(request(), repository=REPO, sink=RecordingSink(), analysis_agent=agent)
    assert outcome.status is JobStatus.FAILED
    assert outcome.error is not None
    assert outcome.error.code is ErrorCode.INTERNAL_ERROR
    assert "hunter2" not in outcome.error.model_dump_json()


def test_invalid_agent_output_is_a_contract_failure_not_repaired() -> None:
    bad = report()
    object.__setattr__(bad, "overall_confidence", 7.0)  # bypasses validate_assignment

    outcome = run_analysis(
        request(), repository=REPO, sink=RecordingSink(), analysis_agent=ok_agent(bad)
    )
    assert outcome.status is JobStatus.FAILED
    assert outcome.error is not None
    assert outcome.error.code is ErrorCode.SCHEMA_VALIDATION_FAILED
    assert outcome.error.details["field"] == "overall_confidence"


def test_stage_timeout_times_out_the_job() -> None:
    def slow(req, *, repository, llm, run, budget):
        time.sleep(1.0)
        budget.check()  # the abandoned thread stops here
        return report()

    sink = RecordingSink()
    outcome = run_analysis(
        request(),
        repository=REPO,
        sink=sink,
        analysis_agent=slow,
        policies=Policies(analysis=StagePolicy(timeout_s=0.1, retries=1)),
    )
    assert outcome.status is JobStatus.TIMED_OUT
    assert outcome.error is not None
    assert outcome.error.code is ErrorCode.STAGE_TIMEOUT
    time.sleep(1.1)
    assert sink.reports == []  # late work is dropped after the job closed


def test_job_timeout() -> None:
    outcome = run_analysis(
        request(), repository=REPO, sink=RecordingSink(), analysis_agent=ok_agent(), timeout_s=0
    )
    assert outcome.status is JobStatus.TIMED_OUT
    assert outcome.error is not None
    assert outcome.error.code is ErrorCode.JOB_TIMEOUT


def test_cancel_stops_the_job() -> None:
    flag = Flag()

    def agent(req, *, repository, llm, run, budget):
        flag.value = True  # user pressed cancel while the agent ran
        budget.check()
        return report()

    outcome = run_analysis(
        request(), repository=REPO, sink=RecordingSink(), analysis_agent=agent, cancel=flag
    )
    assert outcome.status is JobStatus.CANCELLED
    assert outcome.error is not None
    assert outcome.error.code is ErrorCode.JOB_CANCELLED


def test_discovery_failure_is_a_warning_not_a_failure() -> None:
    class BrokenDiscovery:
        def discover(self):
            raise AgentError.of(ErrorCode.AWS_DISCOVERY_FAILED, "denied")

    outcome = run_analysis(
        request(),
        repository=REPO,
        sink=RecordingSink(),
        analysis_agent=ok_agent(),
        infra=BrokenDiscovery(),
    )
    assert outcome.status is JobStatus.SUCCESS
    assert [w.code for w in outcome.warnings] == [ErrorCode.AWS_DISCOVERY_FAILED]


def test_architecture_failure_keeps_the_report() -> None:
    def architect(rep, *, source_analysis_id, region, llm, run, budget):
        raise AgentError.of(ErrorCode.LLM_INVALID_OUTPUT, "bad plan")

    sink = RecordingSink()
    outcome = run_analysis(
        request(),
        repository=REPO,
        sink=sink,
        analysis_agent=ok_agent(),
        architecture_agent=architect,
    )
    assert outcome.status is JobStatus.FAILED
    assert outcome.report is not None
    assert len(sink.reports) == 1
    assert sink.plans == []


def test_persistence_failure_fails_the_job() -> None:
    class FailingSink(RecordingSink):
        def report_ready(self, report):
            raise ConnectionError("db down")

    outcome = run_analysis(
        request(), repository=REPO, sink=FailingSink(), analysis_agent=ok_agent()
    )
    assert outcome.status is JobStatus.FAILED
    assert outcome.error is not None
    assert outcome.error.code is ErrorCode.INTERNAL_ERROR


def test_orchestrator_has_no_repository_logic() -> None:
    """A1.5: the orchestrator only routes. It never reads files or parses manifests."""
    root = pathlib.Path(__file__).resolve().parents[1] / "src" / "cloudpilot_ai" / "orchestrator"
    forbidden_calls = {"read_file", "list_files", "open", "loads", "safe_load"}
    forbidden_imports = ("cloudpilot_ai.analysis", "json", "yaml", "tomllib", "re")
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                assert name not in forbidden_calls, f"{path.name} calls {name}"
            if isinstance(node, ast.ImportFrom | ast.Import):
                names = (
                    [node.module]
                    if isinstance(node, ast.ImportFrom)
                    else [a.name for a in node.names]
                )
                for n in names:
                    assert not (n or "").startswith(forbidden_imports), f"{path.name} imports {n}"
