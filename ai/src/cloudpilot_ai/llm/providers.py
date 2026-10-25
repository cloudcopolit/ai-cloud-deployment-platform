"""LLM provider adapters. Each adapter discovers its models from the provider's list-models
endpoint and picks one by policy; no model name is hardcoded. An optional override
(LLM_MODEL_<PROVIDER>) is honored only if the provider actually lists that model.

Anthropic uses the official `anthropic` SDK (structured output through `messages.parse`).
OpenAI and xAI share the OpenAI-compatible REST API; Gemini uses its REST API.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import anthropic
import httpx
from pydantic import BaseModel

ErrorKind = Literal[
    "auth", "rate_limit", "timeout", "unavailable", "invalid_request", "refusal", "invalid_output"
]

TIMEOUT_S = 60.0


class ProviderError(Exception):
    def __init__(self, kind: ErrorKind, message: str) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class Completion:
    text: str | None  # raw JSON text (REST providers)
    parsed: BaseModel | None  # already validated (Anthropic structured output)
    input_tokens: int
    output_tokens: int
    latency_ms: int


class Provider(Protocol):
    name: str

    def list_models(self) -> list[str]: ...

    def choose_model(self, models: list[str], override: str | None) -> str | None: ...

    def complete(
        self, model: str, *, system: str, user: str, schema: type[BaseModel]
    ) -> Completion: ...


def _status_kind(status: int) -> ErrorKind:
    if status in (401, 403):
        return "auth"
    if status == 429:
        return "rate_limit"
    if status in (408, 504):
        return "timeout"
    if status >= 500:
        return "unavailable"
    return "invalid_request"


def _pick(
    models: list[str], override: str | None, prefer: list[str], avoid: list[str]
) -> str | None:
    """Override if listed; else the first model (input is newest-first) whose id matches the
    earliest preference fragment and no avoided fragment."""
    if override:
        return override if override in models else None
    usable = [m for m in models if not any(a in m.lower() for a in avoid)]
    for fragment in prefer:
        for model in usable:
            if fragment in model.lower():
                return model
    return usable[0] if usable else None


# ───────────────────────── Anthropic (official SDK) ─────────────────────────
class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, *, client: anthropic.Anthropic | None = None) -> None:
        self._client = client or anthropic.Anthropic(
            api_key=api_key, timeout=TIMEOUT_S, max_retries=1
        )
        self._created: dict[str, str] = {}

    def list_models(self) -> list[str]:
        try:
            listed = [
                m
                for m in self._client.models.list()  # auto-paginates
                # typed in the installed SDK: ModelCapabilities.structured_outputs.supported
                if m.capabilities is not None and m.capabilities.structured_outputs.supported
            ]
        except anthropic.AuthenticationError as exc:
            raise ProviderError("auth", "Anthropic rejected the API key.") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError("unavailable", "Anthropic API is not reachable.") from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(
                _status_kind(exc.status_code), "Anthropic list-models failed."
            ) from exc
        listed.sort(key=lambda m: str(m.created_at), reverse=True)
        return [m.id for m in listed]

    def choose_model(self, models: list[str], override: str | None) -> str | None:
        # Most capable current family first (Opus), as Anthropic recommends for general use.
        return _pick(models, override, prefer=["opus", "sonnet"], avoid=[])

    def complete(
        self, model: str, *, system: str, user: str, schema: type[BaseModel]
    ) -> Completion:
        started = time.monotonic()
        try:
            response = self._client.messages.parse(
                model=model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=schema,
            )
        except anthropic.AuthenticationError as exc:
            raise ProviderError("auth", "Anthropic rejected the API key.") from exc
        except anthropic.RateLimitError as exc:
            raise ProviderError("rate_limit", "Anthropic rate limit reached.") from exc
        except anthropic.APITimeoutError as exc:
            raise ProviderError("timeout", "Anthropic did not answer in time.") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError("unavailable", "Anthropic API is not reachable.") from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(
                _status_kind(exc.status_code), f"Anthropic returned HTTP {exc.status_code}."
            ) from exc
        except ValueError as exc:  # structured output that does not match the schema
            raise ProviderError(
                "invalid_output", "Anthropic output did not match the schema."
            ) from exc
        if response.stop_reason == "refusal":
            raise ProviderError("refusal", "Anthropic declined the request.")
        if response.parsed_output is None:
            raise ProviderError(
                "invalid_output", f"Anthropic stopped early ({response.stop_reason})."
            )
        return Completion(
            text=None,
            parsed=response.parsed_output,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=int((time.monotonic() - started) * 1000),
        )


# ───────────────────────── OpenAI-compatible (OpenAI, xAI) ─────────────────────────
class OpenAICompatibleProvider:
    def __init__(
        self,
        name: str,
        api_key: str,
        base_url: str,
        *,
        prefer: list[str],
        avoid: list[str],
        model_prefix: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.name = name
        self._prefer, self._avoid, self._prefix = prefer, avoid, model_prefix
        self._http = httpx.Client(
            base_url=base_url,
            timeout=TIMEOUT_S,
            transport=transport,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise ProviderError("timeout", f"{self.name} did not answer in time.") from exc
        except httpx.TransportError as exc:
            raise ProviderError("unavailable", f"{self.name} API is not reachable.") from exc
        if response.status_code >= 400:
            raise ProviderError(
                _status_kind(response.status_code),
                f"{self.name} returned HTTP {response.status_code}.",
            )
        return response

    def list_models(self) -> list[str]:
        data = self._request("GET", "/models").json().get("data", [])
        models = [
            m for m in data if isinstance(m, dict) and str(m.get("id", "")).startswith(self._prefix)
        ]
        models.sort(key=lambda m: m.get("created") or 0, reverse=True)
        return [str(m["id"]) for m in models]

    def choose_model(self, models: list[str], override: str | None) -> str | None:
        return _pick(models, override, self._prefer, self._avoid)

    def complete(
        self, model: str, *, system: str, user: str, schema: type[BaseModel]
    ) -> Completion:
        started = time.monotonic()
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system + "\nReply with one JSON object only."},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        data = self._request("POST", "/chat/completions", json=body).json()
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("invalid_output", f"{self.name} returned no message.") from exc
        usage = data.get("usage") or {}
        return Completion(
            text=text,
            parsed=None,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            latency_ms=int((time.monotonic() - started) * 1000),
        )


def openai_provider(
    api_key: str, transport: httpx.BaseTransport | None = None
) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        "openai",
        api_key,
        "https://api.openai.com/v1",
        prefer=["gpt-"],
        avoid=[
            "audio",
            "realtime",
            "transcribe",
            "tts",
            "image",
            "search",
            "instruct",
            "embedding",
            "moderation",
            "codex",
        ],
        model_prefix="gpt-",
        transport=transport,
    )


def xai_provider(
    api_key: str, transport: httpx.BaseTransport | None = None
) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        "xai",
        api_key,
        "https://api.x.ai/v1",
        prefer=["grok"],
        avoid=["image", "vision", "imagine"],
        model_prefix="grok",
        transport=transport,
    )


# ───────────────────────── Gemini ─────────────────────────
class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, *, transport: httpx.BaseTransport | None = None) -> None:
        self._http = httpx.Client(
            base_url="https://generativelanguage.googleapis.com/v1beta",
            timeout=TIMEOUT_S,
            transport=transport,
            headers={"x-goog-api-key": api_key},
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise ProviderError("timeout", "Gemini did not answer in time.") from exc
        except httpx.TransportError as exc:
            raise ProviderError("unavailable", "Gemini API is not reachable.") from exc
        if response.status_code >= 400:
            raise ProviderError(
                _status_kind(response.status_code), f"Gemini returned HTTP {response.status_code}."
            )
        return response

    def list_models(self) -> list[str]:
        models = self._request("GET", "/models", params={"pageSize": 200}).json().get("models", [])
        names = [
            str(m["name"]).removeprefix("models/")
            for m in models
            if isinstance(m, dict)
            and "generateContent" in (m.get("supportedGenerationMethods") or [])
            and "gemini" in str(m.get("name", ""))
        ]

        def version(name: str) -> tuple[float, int]:
            match = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
            # stable before preview/experimental at the same version
            return (
                float(match.group(1)) if match else 0.0,
                0 if re.search(r"preview|exp", name) else 1,
            )

        return sorted(names, key=version, reverse=True)

    def choose_model(self, models: list[str], override: str | None) -> str | None:
        return _pick(
            models,
            override,
            prefer=["pro", "flash"],
            avoid=["embedding", "tts", "image", "live", "audio", "lite", "vision"],
        )

    def complete(
        self, model: str, *, system: str, user: str, schema: type[BaseModel]
    ) -> Completion:
        started = time.monotonic()
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        data = self._request("POST", f"/models/{model}:generateContent", json=body).json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise ProviderError("refusal", "Gemini returned no candidate (blocked or empty).")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(str(p.get("text", "")) for p in parts if isinstance(p, dict))
        usage = data.get("usageMetadata") or {}
        return Completion(
            text=text,
            parsed=None,
            input_tokens=int(usage.get("promptTokenCount") or 0),
            output_tokens=int(usage.get("candidatesTokenCount") or 0),
            latency_ms=int((time.monotonic() - started) * 1000),
        )


def parse_json(text: str | None, schema: type[BaseModel]) -> BaseModel:
    """Model output is untrusted: it must be a JSON object that validates, nothing else."""
    if not text:
        raise ProviderError("invalid_output", "Empty model output.")
    candidate = text.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", candidate, re.S)
    if fenced:
        candidate = fenced.group(1)
    try:
        return schema.model_validate(json.loads(candidate))
    except (ValueError, TypeError) as exc:
        raise ProviderError(
            "invalid_output", f"Output failed validation: {type(exc).__name__}."
        ) from exc
