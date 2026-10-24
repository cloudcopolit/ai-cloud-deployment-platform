from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from AI.application.analysis.analyze_repository import AnalyzeRepository
from AI.application.ports.run_store import RunStore
from AI.domain.shared.states import RunStatus
from AI.orchestration.state import WorkflowState

logger = logging.getLogger(__name__)

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
        return {"outcome": await analyze.execute(state["repo"])}

    return guarded(analyze_node, "analysis_failed")


def make_persist_node(store: RunStore) -> Node:
    async def persist_node(state: WorkflowState) -> dict[str, Any]:
        outcome = state["outcome"]
        await store.save_analysis(state["run_id"], outcome.report, outcome.blockers)
        status = RunStatus.BLOCKED if outcome.is_blocked else RunStatus.SUCCEEDED
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