"""Builds the AI layer's LLM gateway from settings. Keys go from settings straight into the
gateway; nothing here logs or returns them."""

from __future__ import annotations

import threading
import time

from cloudpilot_ai.llm import GatewayConfig, MultiProviderGateway, ProviderStatus

from app.core.config import settings

PROVIDERS = ("anthropic", "openai", "gemini", "xai")
STATUS_TTL_S = 600


def _price(value: str | None) -> tuple[float, float] | None:
    if not value:
        return None
    try:
        given, out = (float(x) for x in value.split(",", 1))
    except ValueError:
        return None
    return (given, out) if given >= 0 and out >= 0 else None


def gateway_config() -> GatewayConfig:
    prices = {p: price for p in PROVIDERS if (price := _price(getattr(settings, f"llm_price_{p}")))}
    return GatewayConfig(
        priority=GatewayConfig.parse_priority(settings.llm_provider_priority),
        keys={p: getattr(settings, f"{p}_api_key") or None for p in PROVIDERS},
        model_overrides={p: getattr(settings, f"llm_model_{p}") or None for p in PROVIDERS},
        prices=prices,
        max_calls_per_job=settings.llm_max_calls_per_job,
        max_tokens_per_job=settings.llm_max_tokens_per_job,
    )


def build_gateway() -> MultiProviderGateway:
    """A fresh gateway per job, so budgets and usage are per job."""
    return MultiProviderGateway(gateway_config())


_status: tuple[float, list[ProviderStatus]] | None = None
_status_lock = threading.Lock()


def provider_status(*, refresh: bool = False) -> list[ProviderStatus]:
    """Provider table (cached): configured or MOCKED-ONLY, reachable, models listed, choice."""
    global _status
    with _status_lock:
        if not refresh and _status and _status[0] > time.monotonic():
            return _status[1]
        rows = build_gateway().health()
        _status = (time.monotonic() + STATUS_TTL_S, rows)
        return rows
