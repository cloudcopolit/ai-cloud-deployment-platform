from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from AI.application.analysis.analyze_repository import AnalyzeRepository
from AI.application.ports.run_store import RunStore
from AI.orchestration.nodes import (
    make_analyze_node,
    make_fail_node,
    make_persist_node,
    route_on_error,
)
from AI.orchestration.state import WorkflowState


def build_orchestrator(
    *,
    analyze: AnalyzeRepository,
    store: RunStore,
    checkpointer: Any | None = None,
):
    graph = StateGraph(WorkflowState)
    graph.add_node("analyze", make_analyze_node(analyze))
    graph.add_node("persist", make_persist_node(store))
    graph.add_node("fail", make_fail_node(store))

    graph.add_edge(START, "analyze")
    graph.add_conditional_edges(
        "analyze", route_on_error("persist"), {"persist": "persist", "fail": "fail"}
    )
    graph.add_conditional_edges(
        "persist", route_on_error(END), {END: END, "fail": "fail"}
    )
    graph.add_edge("fail", END)

    return graph.compile(checkpointer=checkpointer)