from AI.application.ports.llm_provider import LLMProvider
from AI.core.config import Settings
from AI.infrastructure.llm.gemini_provider import GeminiProvider


def build_llm(settings: Settings) -> LLMProvider:
    return GeminiProvider(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.gemini_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )