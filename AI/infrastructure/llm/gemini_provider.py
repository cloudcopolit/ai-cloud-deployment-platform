from __future__ import annotations

import asyncio

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from AI.application.ports.llm_provider import LLMRequest, LLMResponse, TokenUsage
from AI.domain.shared.errors import ProviderError, RateLimitError

_FINISH_MAP = {"STOP": "stop", "MAX_TOKENS": "length", "SAFETY": "safety"}

_FALLBACK_MODELS = (
    "gemini-3.5-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-4-argon",
    "gemini-3.8-flash",
)


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

        models_to_try = [self._model] + [m for m in _FALLBACK_MODELS if m != self._model]
        last_exc: genai_errors.APIError | None = None

        for candidate_model in models_to_try:
            try:
                response = await self._client.aio.models.generate_content(
                    model=candidate_model,
                    contents=request.user,
                    config=config,
                )
                used_model = candidate_model
                break
            except genai_errors.APIError as exc:
                last_exc = exc
                if exc.code == 429:
                    raise RateLimitError(f"Gemini rate limit: {exc.message}") from exc
                if exc.code in (500, 502, 503, 504, 404):
                    await asyncio.sleep(0.5)
                    continue
                raise ProviderError(
                    f"Gemini API error {exc.code}", retryable=exc.code >= 500
                ) from exc
        else:
            code = last_exc.code if last_exc else 503
            raise ProviderError(f"Gemini API error {code}", retryable=code >= 500) from last_exc

        candidate = response.candidates[0] if response.candidates else None
        raw_finish = (
            str(candidate.finish_reason) if candidate and candidate.finish_reason else "OTHER"
        )
        usage = response.usage_metadata

        return LLMResponse(
            text=response.text or "",
            model=used_model,
            usage=TokenUsage(
                input_tokens=(usage.prompt_token_count if usage else 0) or 0,
                output_tokens=(usage.candidates_token_count if usage else 0) or 0,
            ),
            finish_reason=_FINISH_MAP.get(raw_finish.split(".")[-1], "other"),
        )
