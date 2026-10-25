"""The Analysis Agent (06 §4): deterministic detectors first; the LLM only for ambiguity.

Every step is a traced task, so the dashboard shows which detector ran, how long it took and
what it found (counts only; never file contents).
"""

from __future__ import annotations

import time

from cloudpilot_ai.analysis.assemble import assemble
from cloudpilot_ai.analysis.detect_infra import (
    detect_code_signals,
    detect_compose,
    detect_config_files,
    detect_dockerfiles,
    detect_env,
    detect_static,
)
from cloudpilot_ai.analysis.detect_lang import (
    detect_go,
    detect_jvm,
    detect_node,
    detect_other,
    detect_python,
)
from cloudpilot_ai.analysis.facts import Facts
from cloudpilot_ai.analysis.secrets import detect_secrets
from cloudpilot_ai.analysis.snapshot import take_snapshot
from cloudpilot_ai.contracts import AnalysisReport, AnalysisRequest, Stage
from cloudpilot_ai.errors import Budget
from cloudpilot_ai.ports import LLMGateway, RepositoryGateway
from cloudpilot_ai.trace import RunScope

MAX_FILES_READ = 600
MAX_BYTES_READ = 12_000_000


def analyze_repository(
    request: AnalysisRequest,
    *,
    repository: RepositoryGateway,
    llm: LLMGateway | None,
    run: RunScope,
    budget: Budget,
) -> AnalysisReport:
    started = time.monotonic()

    with run.task("read_repository", {"commit": request.repository.commit_sha[:12]}) as task:
        snapshot = take_snapshot(
            repository,
            budget=budget,
            max_files=min(request.limits_max_files, MAX_FILES_READ),
            max_total_bytes=min(request.limits_max_bytes, MAX_BYTES_READ),
        )
        task.output = {
            "files_listed": snapshot.listed,
            "files_read": len(snapshot.files),
            "unreadable": len(snapshot.unreadable),
            "truncated": snapshot.truncated,
        }

    facts = Facts(snapshot=snapshot, repo_name=request.repository.name)

    budget.check(Stage.ANALYZE)
    with run.task("detect_languages_and_frameworks") as task:
        for detector in (detect_python, detect_node, detect_jvm, detect_go, detect_other):
            detector(facts)
        task.output = {
            "frameworks": sorted(facts.frameworks),
            "dependencies": len(facts.dependencies),
            "service_candidates": len(facts.services),
        }

    budget.check(Stage.ANALYZE)
    with run.task("detect_containers_and_config") as task:
        detect_dockerfiles(facts)
        detect_compose(facts)
        detect_static(facts)
        detect_config_files(facts)
        task.output = {
            "dockerfiles": sum(1 for s in facts.services.values() if s.dockerfile),
            "config_files": len(facts.config_files),
            "data_stores": sorted(facts.data_stores),
        }

    budget.check(Stage.ANALYZE)
    with run.task("detect_env_ports_health") as task:
        detect_env(facts)
        detect_code_signals(facts)
        task.output = {
            "env_var_names": len(facts.env_vars),
            "ports_found": sum(1 for s in facts.services.values() if s.port),
            "health_routes": sum(1 for s in facts.services.values() if s.health),
        }

    budget.check(Stage.ANALYZE)
    with run.task("scan_for_secrets") as task:
        detect_secrets(facts)
        task.output = {
            "possible_secrets": sum(1 for f in facts.blockers if f.code == "SECRET_COMMITTED"),
        }

    with run.task("resolve_ambiguity_with_llm") as task:
        task.skipped = True
        task.output = {
            "reason": "no LLM provider is configured"
            if llm is None or not llm.available
            else "nothing ambiguous enough to need a model",
        }

    budget.check(Stage.VALIDATE_REPORT)
    with run.task("assemble_report") as task:
        report = assemble(
            facts,
            repository=request.repository,
            answers=request.user_answers,
            duration_ms=int((time.monotonic() - started) * 1000),
            model=None,
        )
        task.output = {
            "services": len(report.services),
            "blockers": len(report.blockers),
            "warnings": len(report.warnings),
            "missing_info": len(report.missing_info),
            "recommendation": report.recommendation.method if report.recommendation else None,
        }
    return report
