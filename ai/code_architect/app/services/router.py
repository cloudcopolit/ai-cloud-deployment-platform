from __future__ import annotations

from dataclasses import dataclass
import re

from app.config import settings
from app.schemas import DeveloperIntent


@dataclass(frozen=True)
class RouteDecision:
    tier: str
    model: str
    complexity_score: int
    threshold: int
    reasons: list[str]


INFRA_MARKERS = (
    "docker-compose", "dockerfile", "terraform", ".tf", "kubernetes", "k8s",
    "helm", "serverless", "github/workflows", ".github/workflows",
)

DATA_MARKERS = (
    "schema", "migration", "sql", "postgres", "mysql", "mongodb", "redis",
    "kafka", "rabbitmq", "celery",
)


def estimate_complexity(repo_text: str, intent: DeveloperIntent) -> tuple[int, list[str]]:
    text = repo_text.lower()
    score = 0
    reasons: list[str] = []

    repo_chars = len(repo_text)
    file_count = repo_text.count("\n## FILE: ")

    if repo_chars >= 120_000:
        score += 3
        reasons.append("large repository snapshot")
    elif repo_chars >= 60_000:
        score += 2
        reasons.append("medium-large repository snapshot")
    elif repo_chars >= 25_000:
        score += 1
        reasons.append("non-trivial repository snapshot")

    if file_count >= 60:
        score += 2
        reasons.append("many analyzed files")
    elif file_count >= 30:
        score += 1
        reasons.append("multiple analyzed files")

    infrastructure_hits = sum(marker in text for marker in INFRA_MARKERS)
    if infrastructure_hits >= 3:
        score += 2
        reasons.append("multiple infrastructure technologies detected")
    elif infrastructure_hits:
        score += 1
        reasons.append("infrastructure configuration detected")

    if sum(marker in text for marker in DATA_MARKERS) >= 4:
        score += 1
        reasons.append("multiple data or messaging technologies detected")

    if intent.depth == "deep":
        score += 1
        reasons.append("deep analysis requested")
    elif intent.depth == "production":
        score += 2
        reasons.append("production-readiness analysis requested")

    if intent.goal in {"migration_refactor", "production_readiness"}:
        score += 1
        reasons.append("complex architecture goal")

    high_weight_concerns = {"security", "reliability", "scalability", "performance", "deployment"}
    concern_hits = len(high_weight_concerns.intersection(intent.concerns))
    if concern_hits >= 3:
        score += 2
        reasons.append("multiple high-complexity concerns")
    elif concern_hits:
        score += 1
        reasons.append("high-complexity concern requested")

    if intent.scale == "large_or_distributed":
        score += 2
        reasons.append("large/distributed target scale")

    if intent.cost_preference == "maximum_quality":
        score += 2
        reasons.append("maximum-quality preference")
    elif intent.cost_preference == "minimize_cost":
        score = max(0, score - 1)
        reasons.append("cost-minimization preference")

    return score, reasons


def choose_initial_model(repo_text: str, intent: DeveloperIntent, mode: str = "auto") -> RouteDecision:
    score, reasons = estimate_complexity(repo_text, intent)
    mode = mode if mode in {"auto", "cheap", "strong"} else "auto"

    if mode == "cheap":
        return RouteDecision("cheap", settings.cheap_model, score, settings.routing_threshold,
                             ["cheap tier forced for baseline/testing", *reasons])
    if mode == "strong":
        return RouteDecision("strong", settings.strong_model, score, settings.routing_threshold,
                             ["strong tier forced for baseline/testing", *reasons])

    direct_strong = score >= settings.routing_threshold
    return RouteDecision(
        "strong" if direct_strong else "cheap",
        settings.strong_model if direct_strong else settings.cheap_model,
        score,
        settings.routing_threshold,
        reasons or ["task appears suitable for cheap-first analysis"],
    )
