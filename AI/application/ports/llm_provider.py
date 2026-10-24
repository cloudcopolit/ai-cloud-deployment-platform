from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMRequest:
    system: str
    user: str
    expect_json: bool = False
    temperature: float = 0.0
    max_output_tokens: int = 4096

    def __post_init__(self) -> None:
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError(f"temperature must be between 0 and 2, got {self.temperature}")
        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    usage: TokenUsage
    finish_reason: str  # normalized: "stop", "length", "safety", "other"


class LLMProvider(Protocol):
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Return the model's response.

        Raises ProviderError or RateLimitError on failure. Implementations must
        never return partial output without marking it through finish_reason.
        A finish_reason of "length" means the output was truncated, and the
        agent should treat it as invalid.
        """
        ...