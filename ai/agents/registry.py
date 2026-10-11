"""Registry for constructing LLM-backed agents."""

from collections.abc import Callable

from agents.base import BaseAgent
from llm.client import LLMClient

AgentFactory = Callable[[LLMClient], BaseAgent]

_REGISTRY: dict[str, AgentFactory] = {}


def register(name: str) -> Callable[[AgentFactory], AgentFactory]:
    """Register an agent factory under a unique, non-empty name."""
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("Agent name must not be empty")

    def decorator(factory: AgentFactory) -> AgentFactory:
        if normalized_name in _REGISTRY:
            raise ValueError(f"Agent '{normalized_name}' is already registered")
        _REGISTRY[normalized_name] = factory
        return factory

    return decorator


def available_agents() -> tuple[str, ...]:
    """Return registered agent names in sorted order."""
    import agents.support_agent  # noqa: F401

    return tuple(sorted(_REGISTRY))


def get_agent(name: str, llm: LLMClient) -> BaseAgent:
    """Construct a registered agent using the supplied LLM client."""
    import agents.support_agent  # noqa: F401

    normalized_name = name.strip()
    if normalized_name not in _REGISTRY:
        raise KeyError(
            f"Unknown agent '{normalized_name}'. Available: {sorted(_REGISTRY)}"
        )

    return _REGISTRY[normalized_name](llm)
