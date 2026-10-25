"""CloudPilot AI layer.

Import direction is one way: the backend imports this package; this package never
imports the backend and never touches the database (ADR-009).

Public API:
    run_analysis(...)       run one job through the orchestrator graph
    analyze_repository      the deterministic Analysis Agent
"""

from cloudpilot_ai.analysis import analyze_repository
from cloudpilot_ai.contracts import SCHEMA_VERSION
from cloudpilot_ai.orchestrator import JobOutcome, Policies, StagePolicy, run_analysis

__all__ = [
    "SCHEMA_VERSION",
    "JobOutcome",
    "Policies",
    "StagePolicy",
    "analyze_repository",
    "run_analysis",
]
