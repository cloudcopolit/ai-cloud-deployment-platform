from __future__ import annotations

import re
from app.schemas import ClarificationQuestion, DeveloperIntent, IntakeResponse


GOAL_PATTERNS = [
    ("production_readiness", r"\b(production|production-ready|production readiness)\b"),
    ("migration_refactor", r"\b(migrat|refactor|moderniz|redesign|re-architect|rearchitect)\w*\b"),
    ("security_review", r"\b(security|secure|threat|vulnerab)\w*\b"),
    ("scalability_review", r"\b(scalab|performance|latency|throughput|bottleneck|capacity)\w*\b"),
    ("find_architecture_problems", r"\b(problem|issue|bottleneck|smell|technical debt|weakness)\w*\b"),
    ("understand_architecture", r"\b(understand|overview|identify|map|current architecture|main components)\b"),
]

DEPTH_PATTERNS = [
    ("production", r"\bproduction[- ]readiness\b"),
    ("deep", r"\b(deep|detailed|thorough|comprehensive|in-depth)\b"),
    ("quick", r"\b(quick|brief|short|high-level)\b"),
    ("standard", r"\bstandard\b"),
]

CONCERNS = {
    "security": r"\b(security|secure|threat|vulnerab)\w*\b",
    "reliability": r"\b(reliab|resilien|fault|failure|availability|slo|sla)\w*\b",
    "performance": r"\b(performance|latency|throughput|bottleneck|capacity)\w*\b",
    "scalability": r"\bscalab\w*\b",
    "deployment": r"\b(deploy|docker|kubernetes|k8s|terraform|ci/cd|pipeline)\w*\b",
    "maintainability": r"\b(maintainab|technical debt|modular|coupling|cohesion)\w*\b",
    "cost": r"\b(cost|cheap|budget|expense)\w*\b",
    "database": r"\b(database|postgres|mysql|mongo|sql|redis)\w*\b",
    "api": r"\b(api|rest|graphql|endpoint)\w*\b",
}

FOCUS = {
    "frontend": r"\b(frontend|front-end|react|vue|angular|ui)\b",
    "backend": r"\b(backend|back-end|server|api)\b",
    "database": r"\b(database|db|postgres|mysql|mongo|sql)\b",
    "infrastructure": r"\b(infrastructure|devops|docker|kubernetes|k8s|terraform|cloud)\b",
    "entire_system": r"\b(entire system|whole system|everything|all components)\b",
}

DEPLOYMENTS = {
    "aws": r"\baws\b",
    "azure": r"\bazure\b",
    "gcp": r"\b(gcp|google cloud)\b",
    "kubernetes": r"\b(kubernetes|k8s)\b",
    "on_premise": r"\b(on[- ]prem|on premise|local deployment)\b",
}


def _first_match(text: str, patterns: list[tuple[str, str]]) -> str | None:
    for value, pattern in patterns:
        if re.search(pattern, text, flags=re.I):
            return value
    return None


def extract_intent(prompt: str) -> DeveloperIntent:
    text = (prompt or "").strip()
    lower = text.lower()

    concerns = [name for name, pattern in CONCERNS.items() if re.search(pattern, lower, re.I)]
    focus = [name for name, pattern in FOCUS.items() if re.search(pattern, lower, re.I)]
    deployment = next((name for name, pattern in DEPLOYMENTS.items() if re.search(pattern, lower, re.I)), None)

    scale = None
    if re.search(r"\b(high[- ]scale|distributed|millions?|100k|large production)\b", lower):
        scale = "large_or_distributed"
    elif re.search(r"\bmedium production\b", lower):
        scale = "medium_production"
    elif re.search(r"\b(small app|small application|small production)\b", lower):
        scale = "small"
    elif re.search(r"\b(prototype|demo|university project|student project)\b", lower):
        scale = "prototype"

    cost_preference = "balanced"
    if re.search(r"\b(minimi[sz]e cost|least cost|cheapest|low cost|save tokens)\b", lower):
        cost_preference = "minimize_cost"
    elif re.search(r"\b(maximum quality|best quality|quality first|strongest model)\b", lower):
        cost_preference = "maximum_quality"

    return DeveloperIntent(
        goal=_first_match(lower, GOAL_PATTERNS),
        depth=_first_match(lower, DEPTH_PATTERNS),
        focus=focus,
        scale=scale,
        deployment_target=deployment,
        concerns=concerns,
        cost_preference=cost_preference,
        additional_context=text,
    )


def merge_intent(base: DeveloperIntent, updates: dict) -> DeveloperIntent:
    data = base.model_dump()
    for key, value in updates.items():
        if key not in data or value in (None, "", []):
            continue
        if key in {"focus", "concerns"}:
            values = value if isinstance(value, list) else [value]
            data[key] = sorted(set(data.get(key, []) + values))
        else:
            data[key] = value
    return DeveloperIntent.model_validate(data)


def missing_required_fields(intent: DeveloperIntent) -> list[str]:
    missing = []
    if not intent.goal:
        missing.append("goal")
    if not intent.depth:
        missing.append("depth")
    return missing


def clarification_questions(fields: list[str]) -> list[ClarificationQuestion]:
    questions: list[ClarificationQuestion] = []
    if "goal" in fields:
        questions.append(ClarificationQuestion(
            field="goal",
            label="What is your main goal?",
            options=[
                "understand_architecture",
                "find_architecture_problems",
                "production_readiness",
                "scalability_review",
                "security_review",
                "migration_refactor",
            ],
        ))
    if "depth" in fields:
        questions.append(ClarificationQuestion(
            field="depth",
            label="How detailed should the analysis be?",
            options=["quick", "standard", "deep", "production"],
        ))
    return questions


def build_intake(prompt: str, updates: dict | None = None) -> IntakeResponse:
    intent = extract_intent(prompt)
    if updates:
        intent = merge_intent(intent, updates)
    missing = missing_required_fields(intent)
    return IntakeResponse(
        complete=not missing,
        intent=intent,
        missing_fields=missing,
        questions=clarification_questions(missing),
    )
