from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from AI.application.analysis.analyze_repository import AnalysisOutcome, AnalyzeRepository
from AI.application.ports.agents import ManifestValidator
from AI.application.ports.run_store import RunStore
from AI.domain.analysis.blockers import evaluate_blockers
from AI.domain.shared.states import RunStatus
from AI.orchestration.state import WorkflowState

logger = logging.getLogger(__name__)

MAX_VALIDATION_RETRIES = 2

Node = Callable[[WorkflowState], Awaitable[dict[str, Any]]]


def guarded(node: Node, error_code: str) -> Node:
    """Convert an exception into an error_code so the graph can route to 'fail'.

    Only the exception type is logged. Messages can contain request details.
    """

    async def wrapper(state: WorkflowState) -> dict[str, Any]:
        try:
            return await node(state)
        except Exception as exc:
            logger.error(
                "node failed run_id=%s error=%s", state.get("run_id"), type(exc).__name__
            )
            return {"error_code": error_code}

    return wrapper


def make_analyze_node(analyze: AnalyzeRepository) -> Node:
    async def analyze_node(state: WorkflowState) -> dict[str, Any]:
        outcome = await analyze.execute(
            state["repo"],
            validation_feedback=state.get("validation_feedback", ()),
            user_facts=state.get("user_facts", ()),
        )
        return {"outcome": outcome}

    return guarded(analyze_node, "analysis_failed")


def make_validate_node(
    validator: ManifestValidator | None,
    *,
    max_retries: int = MAX_VALIDATION_RETRIES,
) -> Node:
    async def validate_node(state: WorkflowState) -> dict[str, Any]:
        if validator is None:
            return {}

        outcome = state["outcome"]
        retries = state.get("retry_count", 0)

        result = await validator.validate(outcome.report, finalize_unresolved=False)
        if result.is_valid:
            return {
                "validation_result": result,
                "validation_feedback": (),
                "outcome": AnalysisOutcome(
                    report=result.manifest,
                    blockers=evaluate_blockers(result.manifest),
                ),
            }

        if retries < max_retries:
            return {
                "validation_result": result,
                "validation_feedback": result.error_messages,
                "retry_count": retries + 1,
            }

        # Retries exhausted: demote invalid fields to OpenQuestions (confidence 0) instead of guessing
        finalized = await validator.validate(outcome.report, finalize_unresolved=True)
        return {
            "validation_result": finalized,
            "validation_feedback": (),
            "outcome": AnalysisOutcome(
                report=finalized.manifest,
                blockers=evaluate_blockers(finalized.manifest),
            ),
        }

    return guarded(validate_node, "validation_failed")


def make_persist_node(store: RunStore) -> Node:
    async def persist_node(state: WorkflowState) -> dict[str, Any]:
        outcome = state["outcome"]
        await store.save_analysis(state["run_id"], outcome.report, outcome.blockers)
        if outcome.is_blocked:
            status = RunStatus.BLOCKED
        elif outcome.report.has_open_questions:
            status = RunStatus.AWAITING_INPUT
        else:
            status = RunStatus.SUCCEEDED
        await store.set_status(state["run_id"], status)
        return {}

    return guarded(persist_node, "persist_failed")


def make_fail_node(store: RunStore) -> Node:
    async def fail_node(state: WorkflowState) -> dict[str, Any]:
        await store.set_status(state["run_id"], RunStatus.FAILED, state.get("error_code"))
        return {}

    return fail_node


def route_on_error(next_step: str) -> Callable[[WorkflowState], str]:
    def route(state: WorkflowState) -> str:
        return "fail" if state.get("error_code") else next_step

    return route


def route_after_validate(state: WorkflowState) -> str:
    if state.get("error_code"):
        return "fail"
    if state.get("validation_feedback"):
        return "analyze"
    return "persist"
