"""The Architect: turns an AnalysisReport into an ArchitecturePlan.

Deterministic patterns first (ADR-023): a report that fits an automated archetype gets a plan
priced from the AWS price table and marked `automated`. Anything else falls back to the
prototype template, marked not automated, with the reasons it did not fit.
"""

from __future__ import annotations

from uuid import UUID

from cloudpilot_ai.architecture import container_postgres
from cloudpilot_ai.architecture.pricing import PriceTableMissing, load_prices
from cloudpilot_ai.contracts import AnalysisReport, ArchitecturePlan, Finding, Severity
from cloudpilot_ai.prototype.architect import run_architecture_agent

__all__ = ["design_architecture"]


def design_architecture(
    report: AnalysisReport, *, source_analysis_id: UUID, region: str = "us-east-1"
) -> ArchitecturePlan:
    fit = container_postgres.eligibility(report)
    reasons = list(fit.reasons)
    if fit.ok and fit.service is not None:
        try:
            prices = load_prices(region)
        except PriceTableMissing:
            reasons.append(f"there is no price table for {region} yet")
        else:
            return container_postgres.design(
                report, fit.service, source_analysis_id=source_analysis_id, prices=prices
            )
    plan = run_architecture_agent(
        report=report, source_analysis_id=source_analysis_id, region=region
    )
    note = Finding(
        code="NOT_AUTOMATED",
        severity=Severity.WARNING,
        message=(
            "Template proposal with illustrative costs; CloudPilot cannot deploy it yet because "
            + "; ".join(reasons)[:400]
            + "."
        ),
        suggested_action="Automated today: one HTTP service with a Dockerfile plus PostgreSQL.",
    )
    return plan.model_copy(
        update={"automated": False, "archetype": None, "risks": [note, *plan.risks]}
    )
