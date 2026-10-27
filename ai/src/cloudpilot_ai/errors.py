"""Exceptions that carry a contract ErrorInfo, plus the job budget (deadline + cancel)."""

from __future__ import annotations

import time
from collections.abc import Callable

from cloudpilot_ai.contracts import ErrorCode, ErrorInfo, Stage
from cloudpilot_ai.ports import CancelToken


class AgentError(Exception):
    """An expected failure with a safe, user-showable ErrorInfo."""

    def __init__(self, info: ErrorInfo) -> None:
        super().__init__(info.message)
        self.info = info

    @classmethod
    def of(
        cls,
        code: ErrorCode,
        message: str,
        *,
        stage: Stage | None = None,
        retryable: bool = False,
        **details: str | int | float | bool | None,
    ) -> AgentError:
        return cls(
            ErrorInfo(
                code=code,
                message=message[:500],
                stage=stage,
                retryable=retryable,
                details=details,
            )
        )


class JobCancelled(AgentError):
    pass


class JobTimedOut(AgentError):
    pass


class _NeverCancelled:
    def is_cancelled(self) -> bool:
        return False


class Budget:
    """Wall-clock deadline and cancellation for one job, checked between steps."""

    def __init__(
        self,
        *,
        seconds: float,
        cancel: CancelToken | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clock = clock
        self._deadline = clock() + seconds
        self._cancel = cancel or _NeverCancelled()
        self._aborted: AgentError | None = None

    def abort(self, error: AgentError) -> None:
        """Stop work that outlived its stage: its next check() raises ``error``."""
        self._aborted = error

    def remaining(self) -> float:
        return max(0.0, self._deadline - self._clock())

    def check(self, stage: Stage | None = None) -> None:
        if self._aborted is not None:
            raise self._aborted
        if self._cancel.is_cancelled():
            raise JobCancelled.of(ErrorCode.JOB_CANCELLED, "The job was cancelled.", stage=stage)
        if self._clock() >= self._deadline:
            raise JobTimedOut.of(ErrorCode.JOB_TIMEOUT, "The job ran out of time.", stage=stage)
