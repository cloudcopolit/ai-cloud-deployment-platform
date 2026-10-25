import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.type import UUIDPrimaryKeyMixin

JOB_STATUSES = "'QUEUED','RUNNING','SUCCESS','BLOCKED','FAILED','TIMED_OUT','CANCELLED'"


class AgentRun(UUIDPrimaryKeyMixin, Base):
    """One execution of one AI agent inside a job: the trace behind the live activity view."""

    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(
            "agent_type IN ('ORCHESTRATOR','ANALYSIS','ARCHITECTURE','DIAGNOSIS','HEALING')",
            name="agent_type_valid",
        ),
        CheckConstraint(f"status IN ({JOB_STATUSES})", name="status_valid"),
        Index("ix_agent_runs_analysis_id_created_at", "analysis_id", "created_at"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("repository_analyses.id", ondelete="RESTRICT")
    )
    # ADR-012: plain columns now; the FK constraints arrive with their tables.
    deployment_id: Mapped[uuid.UUID | None] = mapped_column()
    incident_id: Mapped[uuid.UUID | None] = mapped_column()
    agent_type: Mapped[str] = mapped_column(String(24))
    model: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="QUEUED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_data: Mapped[dict | None] = mapped_column(JSONB)  # redacted, no secrets
    output_data: Mapped[dict | None] = mapped_column(JSONB)
    usage: Mapped[dict | None] = mapped_column(JSONB)  # provider, model, tokens, cost, latency
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)


class AgentTask(UUIDPrimaryKeyMixin, Base):
    """An ordered step inside an agent run (fetch tree, detect, validate, …)."""

    __tablename__ = "agent_tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('QUEUED','RUNNING','SUCCESS','FAILED','SKIPPED')", name="status_valid"
        ),
        CheckConstraint("step_order > 0", name="step_order_positive"),
        UniqueConstraint("agent_run_id", "step_order"),
    )

    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="RESTRICT"), index=True
    )
    task_type: Mapped[str] = mapped_column(String(48))
    status: Mapped[str] = mapped_column(String(16), default="QUEUED")
    step_order: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    input_data: Mapped[dict | None] = mapped_column(JSONB)
    output_data: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
