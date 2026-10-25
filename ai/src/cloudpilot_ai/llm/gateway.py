"""Multi-provider LLM gateway (implements ports.LLMGateway).

- Providers are tried in LLM_PROVIDER_PRIORITY order; a provider error (auth, rate limit,
  timeout, outage, refusal) falls through to the next one.
- Every prompt is redacted here, at the boundary, before it leaves the process.
- Output must validate against the caller's schema; one repair attempt, then LLM_INVALID_OUTPUT.
- A per-job budget caps calls and tokens. Usage (never prompts) is accounted for the trace.
- A provider without an API key is never called; health reports it as MOCKED-ONLY.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError

from cloudpilot_ai.analysis.secrets import redact
from cloudpilot_ai.contracts import ErrorCode, Stage, Usage
from cloudpilot_ai.errors import AgentError
from cloudpilot_ai.llm.providers import (
    AnthropicProvider,
    GeminiProvider,
    Provider,
    ProviderError,
    openai_provider,
    parse_json,
    xai_provider,
)
from cloudpilot_ai.ports import LLMResponse

KNOWN_PROVIDERS = ("anthropic", "openai", "gemini", "xai")
MAX_PROMPT_CHARS = 24_000
MODEL_CACHE_S = 600

FACTORIES: dict[str, Callable[[str], Provider]] = {
    "anthropic": lambda key: AnthropicProvider(key),
    "openai": lambda key: openai_provider(key),
    "gemini": lambda key: GeminiProvider(key),
    "xai": lambda key: xai_provider(key),
}


@dataclass(frozen=True)
class GatewayConfig:
    priority: list[str]
    keys: Mapping[str, str | None]  # provider -> API key (values never logged or returned)
    model_overrides: Mapping[str, str | None] = field(default_factory=dict)
    prices: Mapping[str, tuple[float, float]] = field(default_factory=dict)  # $ per 1M in/out
    max_calls_per_job: int = 6
    max_tokens_per_job: int = 60_000

    @staticmethod
    def parse_priority(value: str | None) -> list[str]:
        names = [p.strip().lower() for p in (value or "").split(",") if p.strip()]
        ordered = [p for p in names if p in KNOWN_PROVIDERS]
        return ordered or list(KNOWN_PROVIDERS)


@dataclass
class ProviderStatus:
    """One row of the provider table. Safe to show: no keys, no prompts."""

    provider: str
    mode: str  # REAL | MOCKED-ONLY
    configured: bool
    reachable: bool | None = None
    models_listed: int | None = None
    chosen_model: str | None = None
    latency_ms: int | None = None
    error: str | None = None


class MultiProviderGateway:
    def __init__(
        self,
        config: GatewayConfig,
        *,
        factories: Mapping[str, Callable[[str], Provider]] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._factories = factories or FACTORIES
        self._clock = clock
        self._providers: dict[str, Provider] = {}
        self._models: dict[str, tuple[str | None, float]] = {}
        self._lock = threading.Lock()
        self._usage = Usage()
        self.last_provider: str | None = None

    # ───────────────────────── configuration ─────────────────────────
    @property
    def configured(self) -> list[str]:
        return [p for p in self._config.priority if self._config.keys.get(p)]

    @property
    def available(self) -> bool:
        return bool(self.configured)

    def _provider(self, name: str) -> Provider:
        if name not in self._providers:
            key = self._config.keys.get(name)
            if not key:
                raise ProviderError("auth", f"{name} has no API key.")
            self._providers[name] = self._factories[name](key)
        return self._providers[name]

    def _model(self, name: str) -> str:
        cached = self._models.get(name)
        if cached and cached[1] > self._clock():
            if cached[0] is None:
                raise ProviderError("invalid_request", f"{name} lists no usable model.")
            return cached[0]
        provider = self._provider(name)
        chosen = provider.choose_model(
            provider.list_models(), self._config.model_overrides.get(name)
        )
        self._models[name] = (chosen, self._clock() + MODEL_CACHE_S)
        if chosen is None:
            raise ProviderError("invalid_request", f"{name} lists no usable model.")
        return chosen

    # ───────────────────────── budget + usage ─────────────────────────
    def usage(self) -> Usage:
        with self._lock:
            return self._usage.model_copy()

    def _check_budget(self) -> None:
        u = self._usage
        if u.calls >= self._config.max_calls_per_job or (
            u.input_tokens + u.output_tokens >= self._config.max_tokens_per_job
        ):
            raise AgentError.of(
                ErrorCode.LLM_UNAVAILABLE,
                "The language-model budget for this job is used up.",
                stage=Stage.ANALYZE,
                calls=u.calls,
                tokens=u.input_tokens + u.output_tokens,
            )

    def _record(
        self, provider: str, model: str, input_tokens: int, output_tokens: int, latency_ms: int
    ) -> None:
        with self._lock:
            u = self._usage
            cost = u.cost_usd
            price = self._config.prices.get(provider)
            if price is not None:
                cost = (
                    (cost or 0.0) + input_tokens / 1e6 * price[0] + output_tokens / 1e6 * price[1]
                )
            self._usage = Usage(
                provider=provider,
                model=model,
                calls=u.calls + 1,
                input_tokens=u.input_tokens + input_tokens,
                output_tokens=u.output_tokens + output_tokens,
                cost_usd=round(cost, 6) if cost is not None else None,
                latency_ms=u.latency_ms + latency_ms,
            )

    # ───────────────────────── completion ─────────────────────────
    def complete_json(
        self, *, task: str, system: str, user: str, schema: type[BaseModel]
    ) -> LLMResponse:
        if not self.available:
            raise AgentError.of(
                ErrorCode.LLM_UNAVAILABLE, "No language-model provider is configured."
            )
        system_text = redact(system)
        user_text = redact(user)[:MAX_PROMPT_CHARS]
        failures: list[str] = []
        for name in self.configured:
            try:
                model = self._model(name)
            except ProviderError as exc:
                failures.append(f"{name}:{exc.kind}")
                continue
            prompt = user_text
            for attempt in (1, 2):  # second attempt = the one repair (06 §3.5)
                self._check_budget()
                try:
                    completion = self._provider(name).complete(
                        model, system=system_text, user=prompt, schema=schema
                    )
                except ProviderError as exc:
                    failures.append(f"{name}:{exc.kind}")
                    if exc.kind == "invalid_output" and attempt == 1:
                        prompt = user_text + REPAIR_NOTE
                        continue
                    if exc.kind == "invalid_output":
                        raise AgentError.of(
                            ErrorCode.LLM_INVALID_OUTPUT,
                            f"{name} output failed validation after one repair attempt.",
                            stage=Stage.VALIDATE_REPORT,
                        ) from None
                    break  # next provider
                self._record(
                    name,
                    model,
                    completion.input_tokens,
                    completion.output_tokens,
                    completion.latency_ms,
                )
                try:
                    data = completion.parsed or parse_json(completion.text, schema)
                    data = schema.model_validate(data.model_dump())
                except (ProviderError, ValidationError):
                    failures.append(f"{name}:invalid_output")
                    if attempt == 1:
                        prompt = user_text + REPAIR_NOTE
                        continue
                    raise AgentError.of(
                        ErrorCode.LLM_INVALID_OUTPUT,
                        f"{name} output failed validation after one repair attempt.",
                        stage=Stage.VALIDATE_REPORT,
                    ) from None
                self.last_provider = name
                return LLMResponse(data=data, usage=self.usage())
        raise AgentError.of(
            ErrorCode.LLM_UNAVAILABLE,
            "Every configured language-model provider failed.",
            stage=Stage.ANALYZE,
            retryable=True,
            attempts=";".join(failures)[:255],
        )

    # ───────────────────────── health ─────────────────────────
    def health(self) -> list[ProviderStatus]:
        rows = []
        for name in self._config.priority:
            if not self._config.keys.get(name):
                rows.append(
                    ProviderStatus(
                        name, "MOCKED-ONLY", configured=False, error="no API key configured"
                    )
                )
                continue
            started = self._clock()
            try:
                provider = self._provider(name)
                models = provider.list_models()
                chosen = provider.choose_model(models, self._config.model_overrides.get(name))
                rows.append(
                    ProviderStatus(
                        name,
                        "REAL",
                        configured=True,
                        reachable=True,
                        models_listed=len(models),
                        chosen_model=chosen,
                        latency_ms=int((self._clock() - started) * 1000),
                        error=None if chosen else "no usable model listed",
                    )
                )
            except ProviderError as exc:
                rows.append(
                    ProviderStatus(
                        name, "REAL", configured=True, reachable=False, error=f"{exc.kind}: {exc}"
                    )
                )
        return rows


REPAIR_NOTE = (
    "\n\nYour previous answer was not valid JSON for the required schema. Return only one JSON "
    "object with exactly the required fields."
)
