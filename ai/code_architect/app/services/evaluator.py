from __future__ import annotations

from app.config import settings
from app.schemas import ArchitectureAnalysis, DeveloperIntent, QualityReport


GOAL_TERMS = {
    "understand_architecture": (),
    "find_architecture_problems": ("problem", "issue", "risk", "bottleneck", "recommend"),
    "production_readiness": ("production", "deploy", "reliab", "security", "observab"),
    "scalability_review": ("scal", "performance", "latency", "throughput", "bottleneck"),
    "security_review": ("security", "secret", "credential", "auth", "vulnerab"),
    "migration_refactor": ("migrat", "refactor", "moderniz", "redesign", "transition"),
}


def evaluate_analysis(analysis: ArchitectureAnalysis, intent: DeveloperIntent) -> QualityReport:
    components = analysis.components
    evidence_coverage = (
        sum(bool(c.evidence) for c in components) / len(components)
        if components else 0.0
    )

    ids = {c.id for c in components}
    if analysis.connections:
        valid = sum(c.source in ids and c.target in ids for c in analysis.connections)
        connection_validity = valid / len(analysis.connections)
    else:
        connection_validity = 1.0 if components else 0.0

    searchable = " ".join([
        analysis.summary,
        *[r.title + " " + r.rationale for r in analysis.recommendations],
        *analysis.assumptions,
    ]).lower()

    goal_terms = GOAL_TERMS.get(intent.goal or "", ())
    if not goal_terms:
        goal_coverage = 1.0 if components else 0.0
    else:
        goal_coverage = min(1.0, sum(term in searchable for term in goal_terms) / max(1, min(3, len(goal_terms))))

    requested_concerns = intent.concerns
    if requested_concerns:
        concern_hits = sum(concern.lower() in searchable for concern in requested_concerns)
        goal_coverage = (goal_coverage + concern_hits / len(requested_concerns)) / 2

    recommendation_coverage = min(1.0, len(analysis.recommendations) / (1 if intent.depth == "quick" else 3))

    score = round(
        0.40 * evidence_coverage
        + 0.20 * connection_validity
        + 0.30 * goal_coverage
        + 0.10 * recommendation_coverage,
        3,
    )

    reasons: list[str] = []
    if evidence_coverage < 0.70:
        reasons.append("low component evidence coverage")
    if connection_validity < 1.0:
        reasons.append("one or more connections reference unknown components")
    if goal_coverage < 0.70:
        reasons.append("developer goal or concerns are not sufficiently covered")
    if recommendation_coverage < 0.67 and intent.depth in {"deep", "production"}:
        reasons.append("too few recommendations for requested analysis depth")

    return QualityReport(
        score=score,
        threshold=settings.quality_threshold,
        schema_valid=True,
        evidence_coverage=round(evidence_coverage, 3),
        connection_validity=round(connection_validity, 3),
        goal_coverage=round(goal_coverage, 3),
        recommendation_coverage=round(recommendation_coverage, 3),
        reasons=reasons,
    )
