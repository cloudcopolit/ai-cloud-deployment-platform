from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from AI.application.analysis.redactor import redact_secrets

MAX_PAYLOAD_VALUE_CHARS = 256
MAX_LOG_SIZE = 500


class MessageRoutingError(Exception):
    """Raised when a message breaks a routing rule (move to domain/shared/errors.py if preferred)."""


class AgentRole(StrEnum):
    ORCHESTRATOR = "orchestrator"
    ANALYSIS = "analysis"
    VALIDATOR = "validator"
    AWS_DETECTION = "aws_detection"
    ARCHITECT = "architect"
    IAC = "iac"
    TESTER = "tester"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"
    SELF_HEALING = "self_healing"


class MessageKind(StrEnum):
    ANALYSIS_REQUEST = "analysis_request"
    ANALYSIS_COMPLETED = "analysis_completed"
    AWS_DETECTION_REQUEST = "aws_detection_request"
    AWS_DETECTION_COMPLETED = "aws_detection_completed"
    FAILURE = "failure"


@dataclass(frozen=True)
class AgentMessage:
    """Immutable envelope. The payload carries IDs and short references only, never file content."""

    run_id: UUID
    sender: AgentRole
    recipient: AgentRole
    kind: MessageKind
    payload: tuple[tuple[str, str], ...] = ()
    in_reply_to: UUID | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        for key, value in self.payload:
            if not key:
                raise ValueError("payload keys must not be empty")
            if len(value) > MAX_PAYLOAD_VALUE_CHARS:
                raise ValueError(
                    f"payload value for {key!r} is too long; pass an ID or reference, not content"
                )
            if redact_secrets(value) != value:
                raise ValueError(f"payload value for {key!r} looks like a secret")

    @classmethod
    def create(
        cls,
        *,
        run_id: UUID,
        sender: AgentRole,
        recipient: AgentRole,
        kind: MessageKind,
        payload: Mapping[str, str] | None = None,
        in_reply_to: UUID | None = None,
    ) -> AgentMessage:
        items = tuple(sorted((payload or {}).items()))
        return cls(
            run_id=run_id,
            sender=sender,
            recipient=recipient,
            kind=kind,
            payload=items,
            in_reply_to=in_reply_to,
        )

    def get(self, key: str, default: str = "") -> str:
        for k, v in self.payload:
            if k == key:
                return v
        return default


Handler = Callable[[AgentMessage], Awaitable[AgentMessage | None]]


class MessageRouter:
    """In-process router that enforces CloudPilot's rule: agents never talk to each other directly.

    Every message must have the orchestrator as sender or recipient. Agents read and write
    versioned records; the orchestrator decides what happens next.
    """

    def __init__(self, *, max_log_size: int = MAX_LOG_SIZE) -> None:
        self._handlers: dict[AgentRole, Handler] = {}
        self._log: list[AgentMessage] = []
        self._max_log_size = max_log_size

    def register(self, role: AgentRole, handler: Handler) -> None:
        if role in self._handlers:
            raise MessageRoutingError(f"A handler is already registered for '{role.value}'")
        self._handlers[role] = handler

    def has_handler(self, role: AgentRole) -> bool:
        return role in self._handlers

    @property
    def log(self) -> tuple[AgentMessage, ...]:
        return tuple(self._log)

    async def send(self, message: AgentMessage) -> AgentMessage | None:
        self._check_route(message)
        handler = self._handlers.get(message.recipient)
        if handler is None:
            raise MessageRoutingError(f"No handler registered for '{message.recipient.value}'")

        self._record(message)
        reply = await handler(message)
        if reply is not None:
            self._check_reply(message, reply)
            self._record(reply)
        return reply

    # -- rules ---------------------------------------------------------------

    @staticmethod
    def _check_route(message: AgentMessage) -> None:
        if message.sender is message.recipient:
            raise MessageRoutingError("A sender cannot message itself")
        if AgentRole.ORCHESTRATOR not in (message.sender, message.recipient):
            raise MessageRoutingError(
                f"Direct agent-to-agent message '{message.sender.value}' -> "
                f"'{message.recipient.value}' is not allowed; route through the orchestrator"
            )

    @staticmethod
    def _check_reply(request: AgentMessage, reply: AgentMessage) -> None:
        if (
            reply.run_id != request.run_id
            or reply.sender is not request.recipient
            or reply.recipient is not request.sender
            or reply.in_reply_to != request.id
        ):
            raise MessageRoutingError("Reply does not match the request it answers")

    def _record(self, message: AgentMessage) -> None:
        self._log.append(message)
        overflow = len(self._log) - self._max_log_size
        if overflow > 0:
            del self._log[:overflow]
