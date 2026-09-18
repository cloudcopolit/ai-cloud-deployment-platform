from __future__ import annotations

from app.schemas import DeveloperIntent


def build_analysis_prompt(intent: DeveloperIntent, repo_text: str, schema_json: str) -> str:
    focus = ", ".join(intent.focus) or "not specified"
    concerns = ", ".join(intent.concerns) or "not specified"

    return f"""DEVELOPER INTENT
Goal: {intent.goal}
Depth: {intent.depth}
Focus: {focus}
Expected scale: {intent.scale or 'not specified'}
Deployment target: {intent.deployment_target or 'not specified'}
Concerns: {concerns}
Cost preference: {intent.cost_preference}
Additional context: {intent.additional_context or 'none'}

TASK
Analyze the CURRENT repository architecture using repository evidence.
Prioritize the developer's stated objective and requested depth.
Clearly distinguish repository evidence from inference and assumptions.
Do not invent components merely because they would be useful.
For recommendations, explain the architectural issue, likely impact, and smallest practical improvement.

Return JSON matching this schema exactly:
{schema_json}

REPOSITORY SNAPSHOT:
{repo_text}
"""
