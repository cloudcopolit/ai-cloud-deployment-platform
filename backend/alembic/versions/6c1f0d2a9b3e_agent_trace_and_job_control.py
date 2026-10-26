"""agent trace (agent_runs, agent_tasks) and analysis job control (M3, ADR-008/012)

Revision ID: 6c1f0d2a9b3e
Revises: 001ba641ce53
Create Date: 2026-10-25 16:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "6c1f0d2a9b3e"
down_revision: str | Sequence[str] | None = "001ba641ce53"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOB_STATUSES = "'QUEUED','RUNNING','SUCCESS','BLOCKED','FAILED','TIMED_OUT','CANCELLED'"


def upgrade() -> None:
    # ── job control on the analysis job itself ──
    op.add_column("repository_analyses", sa.Column("branch_name", sa.String(255), nullable=True))
    op.add_column("repository_analyses", sa.Column("parent_analysis_id", sa.Uuid(), nullable=True))
    op.add_column(
        "repository_analyses",
        sa.Column(
            "user_answers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("repository_analyses", sa.Column("idempotency_key", sa.String(64), nullable=True))
    op.add_column(
        "repository_analyses",
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column("repository_analyses", sa.Column("locked_by", sa.String(64), nullable=True))
    op.add_column(
        "repository_analyses",
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "repository_analyses",
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "repository_analyses",
        sa.Column(
            "cancel_requested", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    op.add_column(
        "repository_analyses",
        sa.Column(
            "warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        op.f("fk_repository_analyses_parent_analysis_id_repository_analyses"),
        "repository_analyses",
        "repository_analyses",
        ["parent_analysis_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_repository_analyses_status_created_at",
        "repository_analyses",
        ["status", "created_at"],
    )
    op.create_index(
        "uq_repository_analyses_requested_by_idempotency_key",
        "repository_analyses",
        ["requested_by", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    # ── agent trace ──
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=True),
        sa.Column("deployment_id", sa.Uuid(), nullable=True),
        sa.Column("incident_id", sa.Uuid(), nullable=True),
        sa.Column("agent_type", sa.String(24), nullable=False),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "agent_type IN ('ORCHESTRATOR','ANALYSIS','ARCHITECTURE','DIAGNOSIS','HEALING')",
            name=op.f("ck_agent_runs_agent_type_valid"),
        ),
        sa.CheckConstraint(f"status IN ({JOB_STATUSES})", name=op.f("ck_agent_runs_status_valid")),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_agent_runs_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["repository_analyses.id"],
            name=op.f("fk_agent_runs_analysis_id_repository_analyses"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_runs")),
    )
    op.create_index(op.f("ix_agent_runs_project_id"), "agent_runs", ["project_id"])
    op.create_index(
        "ix_agent_runs_analysis_id_created_at", "agent_runs", ["analysis_id", "created_at"]
    )

    op.create_table(
        "agent_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_run_id", sa.Uuid(), nullable=False),
        sa.Column("task_type", sa.String(48), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("input_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('QUEUED','RUNNING','SUCCESS','FAILED','SKIPPED')",
            name=op.f("ck_agent_tasks_status_valid"),
        ),
        sa.CheckConstraint("step_order > 0", name=op.f("ck_agent_tasks_step_order_positive")),
        sa.ForeignKeyConstraint(
            ["agent_run_id"],
            ["agent_runs.id"],
            name=op.f("fk_agent_tasks_agent_run_id_agent_runs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_tasks")),
        sa.UniqueConstraint("agent_run_id", "step_order", name=op.f("uq_agent_tasks_agent_run_id")),
    )
    op.create_index(op.f("ix_agent_tasks_agent_run_id"), "agent_tasks", ["agent_run_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_tasks_agent_run_id"), table_name="agent_tasks")
    op.drop_table("agent_tasks")
    op.drop_index("ix_agent_runs_analysis_id_created_at", table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_project_id"), table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index(
        "uq_repository_analyses_requested_by_idempotency_key", table_name="repository_analyses"
    )
    op.drop_index("ix_repository_analyses_status_created_at", table_name="repository_analyses")
    op.drop_constraint(
        op.f("fk_repository_analyses_parent_analysis_id_repository_analyses"),
        "repository_analyses",
        type_="foreignkey",
    )
    for column in (
        "warnings",
        "cancel_requested",
        "deadline_at",
        "heartbeat_at",
        "locked_by",
        "attempts",
        "idempotency_key",
        "user_answers",
        "parent_analysis_id",
        "branch_name",
    ):
        op.drop_column("repository_analyses", column)
