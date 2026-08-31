from __future__ import annotations

import json
import re

from openai import OpenAI

from app.config import settings
from app.schemas import ArchitectureAnalysis
from app.services.mermaid import architecture_to_mermaid


SYSTEM_PROMPT = """You are a senior software architect analyzing an uploaded codebase.

Your job:
1. Infer the CURRENT software architecture from repository evidence.
2. Distinguish repository evidence from assumptions.
3. Identify frontend, backend, databases, storage, queues, external services,
   infrastructure, and meaningful connections.
4. Give concise, actionable architecture recommendations.
5. Never invent a component merely because it would be a good design choice.
6. Put uncertain claims in assumptions.
7. Component IDs must be unique and connections must reference those IDs.
8. Return JSON only. Do not generate Mermaid; the server creates Mermaid deterministically.
"""


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def analyze_repository(repo_text: str, user_prompt: str) -> ArchitectureAnalysis:
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is missing. Create a free OpenRouter key, "
            "copy .env.example to .env, and add the key."
        )

    client = OpenAI(
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
    )

    schema = ArchitectureAnalysis.model_json_schema()
    schema["properties"].pop("mermaid", None)
    if "required" in schema and "mermaid" in schema["required"]:
        schema["required"].remove("mermaid")

    prompt = f"""USER GOAL / EXTRA INSTRUCTIONS:
{user_prompt or "Analyze the current architecture and suggest practical improvements."}

Return an object matching this JSON Schema:
{json.dumps(schema, ensure_ascii=False)}

REPOSITORY SNAPSHOT:
{repo_text}
"""

    response = client.chat.completions.create(
        model=settings.openrouter_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or ""
    data = json.loads(_strip_code_fence(raw))
    analysis = ArchitectureAnalysis.model_validate(data)
    analysis.mermaid = architecture_to_mermaid(analysis)
    return analysis
