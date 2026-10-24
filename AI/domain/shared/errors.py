class DomainError(Exception):
    """Base class for errors the application layer is expected to handle."""


class RepositoryAccessError(DomainError):
    """The repository does not exist, or the token cannot read it."""


class AnalysisFailedError(DomainError):
    """An agent could not produce a valid result after its retries."""


class ProviderError(DomainError):
    """A call to an external model provider failed.

    `retryable` tells the caller whether trying again might succeed.
    Timeouts and 5xx responses are retryable. Invalid requests are not.
    """

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class RateLimitError(ProviderError):
    """The provider rejected the call because of quota or rate limits."""

    def __init__(self, message: str = "LLM rate limit reached", *, retry_after_seconds: float | None = None) -> None:
        super().__init__(message, retryable=True)
        self.retry_after_seconds = retry_after_seconds


class InvalidModelOutputError(DomainError):
    """The model returned text that could not be parsed into the expected shape."""