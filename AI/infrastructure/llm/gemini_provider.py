from __future__ import annotations

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from AI.application.ports.llm_provider import LLMRequest, LLMResponse, TokenUsage
from AI.domain.shared.errors import ProviderError, RateLimitError

_FINISH_MAP = {"STOP": "stop", "MAX_TOKENS": "length", "SAFETY": "safety"}


class GeminiProvider:
    def __init__(self, *, api_key: str, model: str, timeout_seconds: float) -> None:
        self._model = model
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),  # SDK expects ms
        )

    async def complete(self, request: LLMRequest) -> LLMResponse:
        config = types.GenerateContentConfig(
            system_instruction=request.system,
            temperature=request.temperature,
            max_output_tokens=request.max_output_tokens,
            response_mime_type="application/json" if request.expect_json else "text/plain",
        )
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=request.user,
                config=config,
            )
        except genai_errors.APIError as exc:
            if exc.code == 429:
                raise RateLimitError(f"Gemini rate limit: {exc.message}") from exc
            raise ProviderError(f"Gemini API error {exc.code}", retryable=exc.code >= 500) from exc

        candidate = response.candidates[0] if response.candidates else None
        raw_finish = str(candidate.finish_reason) if candidate and candidate.finish_reason else "OTHER"
        usage = response.usage_metadata

        return LLMResponse(
            text=response.text or "",
            model=self._model,
            usage=TokenUsage(
                input_tokens=(usage.prompt_token_count if usage else 0) or 0,
                output_tokens=(usage.candidates_token_count if usage else 0) or 0,
            ),
            finish_reason=_FINISH_MAP.get(raw_finish.split(".")[-1], "other"),
        )