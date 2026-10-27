import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.type import UUIDPrimaryKeyMixin

# ADR-032. QUEUED / APPLY_QUEUED / DESTROY_QUEUED are claimable by the deploy runner.
DEPLOYMENT_STATUSES = (
    "QUEUED",
    "PLANNING",
    "AWAITING_APPROVAL",
    "BLOCKED",
    "APPLY_QUEUED",
    "APPLYING",
    "VERIFYING",
    "SUCCESS",
    "FAILED",
    "TIMED_OUT",
    "CANCELLED",
    "DESTROY_QUEUED",
    "DESTROYING",
    "DESTROYED",
    "DESTROY_FAILED",
)
DEPLOYMENT_STATUSES_SQL = ",".join(f"'{s}'" for s in DEPLOYMENT_STATUSES)


class Deployment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "deployments"
    __table_args__ = (
        CheckConstraint(f"status IN ({DEPLOYMENT_STATUSES_SQL})", name="ck_deployments_status"),
        CheckConstraint(
            "trigger_type IN ('MANUAL','AUTO','RETRY','HEALING')",
            name="ck_deployments_trigger_type",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="RESTRICT"), index=True
    )
    commit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("commits.id", ondelete="RESTRICT"), index=True
    )
    architecture_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("architecture_versions.id", ondelete="RESTRICT"), index=True
    )
    aws_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aws_accounts.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(24), default="QUEUED", index=True)
    trigger_type: Mapped[str] = mapped_column(String(16), default="MANUAL")
    # what to deploy (ADR-025) and how (ingress CIDRs, OpenTofu variables snapshot)
    image_uri: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    # plan (ADR-029/033): CloudPilot keeps hash, summary, cost and checks; the plan file
    # itself stays in the customer's bucket
    plan_hash: Mapped[str | None] = mapped_column(String(64))
    plan_summary: Mapped[dict | None] = mapped_column(JSONB)
    cost_estimate: Mapped[dict | None] = mapped_column(JSONB)
    policy_results: Mapped[list | None] = mapped_column(JSONB)
    outputs: Mapped[dict | None] = mapped_column(JSONB)
    health: Mapped[dict | None] = mapped_column(JSONB)
    destroy_check: Mapped[dict | None] = mapped_column(JSONB)
    # CloudTrail session names used by this deployment's jobs
    sessions: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    # runner job control (same pattern as analysis jobs, ADR-008)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    locked_by: Mapped[str | None] = mapped_column(String(64))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )


class DeploymentStep(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "deployment_steps"
    __table_args__ = (
        CheckConstraint("step_order > 0", name="ck_deployment_steps_step_order"),
        CheckConstraint(
            "status IN ('QUEUED','RUNNING','SUCCESS','FAILED','SKIPPED')",
            name="ck_deployment_steps_status",
        ),
        UniqueConstraint(
            "deployment_id", "step_order", name="uq_deployment_steps_deployment_id_step_order"
        ),
    )

    deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deployments.id", ondelete="RESTRICT"), index=True
    )
    step_type: Mapped[str] = mapped_column(String(32))
    step_order: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="QUEUED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    input_data: Mapped[dict | None] = mapped_column(JSONB)
    output_data: Mapped[dict | None] = mapped_column(JSONB)


class InfrastructureResource(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "infrastructure_resources"
    __table_args__ = (
        CheckConstraint(
            "status IN ('CREATING','ACTIVE','FAILED','DESTROYED')",
            name="ck_infrastructure_resources_status",
        ),
    )

    deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deployments.id", ondelete="RESTRICT"), index=True
    )
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_name: Mapped[str] = mapped_column(String(255))
    aws_resource_id: Mapped[str | None] = mapped_column(String(255))
    aws_arn: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
