from typing import Protocol


class LLMClient(Protocol):
    def complete(self, *, system: str, user: str) -> str: ...


class FakeLLM:
    """Deterministic client for tests and local dev (no network/keys)."""

    def complete(self, *, system: str, user: str) -> str:
        return f"[fake] {user}"
