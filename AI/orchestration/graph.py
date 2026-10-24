from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from AI.application.analysis.analyze_repository import AnalyzeRepository
from AI.application.ports.agents import ManifestValidator
from AI.application.ports.run_store import RunStore
from AI.orchestration.nodes import (
    MAX_VALIDATION_RETRIES,
    make_analyze_node,
    make_fail_node,
    make_persist_node,
    make_validate_node,
    route_after_validate,
    route_on_error,
)
from AI.orchestration.state import WorkflowState


def build_orchestrator(
    *,
    analyze: AnalyzeRepository,
    store: RunStore,
    validator: ManifestValidator | None = None,
    max_validation_retries: int = MAX_VALIDATION_RETRIES,
    checkpointer: Any | None = None,
) -> Any:
    graph = StateGraph(WorkflowState)
    graph.add_node("analyze", make_analyze_node(analyze))
    graph.add_node(
        "validate",
        make_validate_node(validator, max_retries=max_validation_retries),
    )
    graph.add_node("persist", make_persist_node(store))
    graph.add_node("fail", make_fail_node(store))

    graph.add_edge(START, "analyze")
    graph.add_conditional_edges(
        "analyze",
        route_on_error("validate"),
        {"validate": "validate", "fail": "fail"},
    )
    graph.add_conditional_edges(
        "validate",
        route_after_validate,
        {"analyze": "analyze", "persist": "persist", "fail": "fail"},
    )
    graph.add_conditional_edges(
        "persist", route_on_error(END), {END: END, "fail": "fail"}
    )
    graph.add_edge("fail", END)

    return graph.compile(checkpointer=checkpointer)
