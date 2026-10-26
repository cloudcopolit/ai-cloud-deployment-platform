"""deploy slice: deployment job + plan fields, hash-bound approvals, AWS onboarding evidence,
append-only audit log, rate-limit buckets (ADR-027..032)

Revision ID: 7d2e4f6a8b10
Revises: 6c1f0d2a9b3e
Create Date: 2026-10-26 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "7d2e4f6a8b10"
down_revision: str | Sequence[str] | None = "6c1f0d2a9b3e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_DEPLOYMENT_STATUSES = (
    "'QUEUED','PLANNING','AWAITING_APPROVAL','BLOCKED','APPLY_QUEUED','APPLYING','VERIFYING',"
    "'SUCCESS','FAILED','TIMED_OUT','CANCELLED','DESTROY_QUEUED','DESTROYING','DESTROYED',"
    "'DESTROY_FAILED'"
)
OLD_DEPLOYMENT_STATUSES = "'QUEUED','RUNNING','SUCCESS','FAILED','CANCELLED'"
NEW_APPROVAL_STATUSES = "'PENDING','APPROVED','REJECTED','EXPIRED','SUPERSEDED','CONSUMED'"
OLD_APPROVAL_STATUSES = "'PENDING','APPROVED','REJECTED','EXPIRED'"

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    # ── deployments: wider status set, plan fields, runner job control ──
    op.drop_constraint(op.f("ck_deployments_ck_deployments_status"), "deployments", type_="check")
    op.alter_column(
        "deployments",
        "status",
        type_=sa.String(24),
        existing_type=sa.String(16),
        existing_nullable=False,
    )
    op.create_check_constraint(
        op.f("ck_deployments_ck_deployments_status"),
        "deployments",
        f"status IN ({NEW_DEPLOYMENT_STATUSES})",
    )
    op.add_column("deployments", sa.Column("image_uri", sa.Text(), nullable=True))
    op.add_column(
        "deployments",
        sa.Column("config", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.add_column("deployments", sa.Column("plan_hash", sa.String(64), nullable=True))
    for name in (
        "plan_summary",
        "cost_estimate",
        "policy_results",
        "outputs",
        "health",
        "destroy_check",
    ):
        op.add_column("deployments", sa.Column(name, JSONB, nullable=True))
    op.add_column(
        "deployments",
        sa.Column("sessions", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
    )
    op.add_column(
        "deployments",
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column("deployments", sa.Column("locked_by", sa.String(64), nullable=True))
    op.add_column(
        "deployments", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "deployments", sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True)
    )

    # ── approvals bound to one plan hash ──
    op.drop_constraint(op.f("ck_approvals_ck_approvals_status"), "approvals", type_="check")
    op.create_check_constraint(
        op.f("ck_approvals_ck_approvals_status"),
        "approvals",
        f"status IN ({NEW_APPROVAL_STATUSES})",
    )
    op.add_column("approvals", sa.Column("plan_hash", sa.String(64), nullable=True))
    op.add_column("approvals", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("approvals", sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True))

    # ── AWS onboarding and verification evidence ──
    op.add_column("aws_accounts", sa.Column("state_bucket", sa.String(63), nullable=True))
    op.add_column("aws_accounts", sa.Column("boundary_arn", sa.Text(), nullable=True))
    op.add_column("aws_accounts", sa.Column("onboarding_stack", sa.String(128), nullable=True))
    op.add_column("aws_accounts", sa.Column("verified_identity_arn", sa.Text(), nullable=True))
    op.add_column("aws_accounts", sa.Column("external_id_enforced", sa.Boolean(), nullable=True))
    op.add_column("aws_accounts", sa.Column("verification_message", sa.Text(), nullable=True))

    # ── append-only audit log ──
    op.create_table(
        "audit_logs",
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(48), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.String(64), nullable=True),
        sa.Column("plan_hash", sa.String(64), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("details", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=True),
        sa.Column("entry_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["team_id"], ["teams.id"], name=op.f("fk_audit_logs_team_id_teams"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_audit_logs_actor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(
        "ix_audit_logs_team_created", "audit_logs", ["team_id", "created_at"], unique=False
    )
    op.create_index(op.f("ix_audit_logs_target_id"), "audit_logs", ["target_id"], unique=False)
    op.execute(
        """
        CREATE FUNCTION cloudpilot_audit_logs_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_logs_append_only
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION cloudpilot_audit_logs_append_only();
        """
    )

    # ── rate limits ──
    op.create_table(
        "rate_limit_buckets",
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.PrimaryKeyConstraint("key", "window_start", name=op.f("pk_rate_limit_buckets")),
    )


def downgrade() -> None:
    op.drop_table("rate_limit_buckets")
    op.execute("DROP TRIGGER IF EXISTS audit_logs_append_only ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS cloudpilot_audit_logs_append_only()")
    op.drop_index(op.f("ix_audit_logs_target_id"), table_name="audit_logs")
    op.drop_index("ix_audit_logs_team_created", table_name="audit_logs")
    op.drop_table("audit_logs")

    for name in (
        "verification_message",
        "external_id_enforced",
        "verified_identity_arn",
        "onboarding_stack",
        "boundary_arn",
        "state_bucket",
    ):
        op.drop_column("aws_accounts", name)

    for name in ("consumed_at", "expires_at", "plan_hash"):
        op.drop_column("approvals", name)
    op.drop_constraint(op.f("ck_approvals_ck_approvals_status"), "approvals", type_="check")
    op.execute("UPDATE approvals SET status = 'EXPIRED' WHERE status IN ('SUPERSEDED', 'CONSUMED')")
    op.create_check_constraint(
        op.f("ck_approvals_ck_approvals_status"),
        "approvals",
        f"status IN ({OLD_APPROVAL_STATUSES})",
    )

    for name in (
        "deadline_at",
        "heartbeat_at",
        "locked_by",
        "attempts",
        "sessions",
        "destroy_check",
        "health",
        "outputs",
        "policy_results",
        "cost_estimate",
        "plan_summary",
        "plan_hash",
        "config",
        "image_uri",
    ):
        op.drop_column("deployments", name)
    op.drop_constraint(op.f("ck_deployments_ck_deployments_status"), "deployments", type_="check")
    # statuses the old schema cannot express are folded into the closest old one
    op.execute(
        "UPDATE deployments SET status = CASE "
        "WHEN status IN ('SUCCESS','DESTROYED') THEN 'SUCCESS' "
        "WHEN status IN ('CANCELLED') THEN 'CANCELLED' "
        "WHEN status IN ('QUEUED') THEN 'QUEUED' "
        "WHEN status IN ('PLANNING','APPLYING','VERIFYING','DESTROYING','APPLY_QUEUED',"
        "'DESTROY_QUEUED','AWAITING_APPROVAL') THEN 'RUNNING' "
        "ELSE 'FAILED' END"
    )
    op.alter_column(
        "deployments",
        "status",
        type_=sa.String(16),
        existing_type=sa.String(24),
        existing_nullable=False,
    )
    op.create_check_constraint(
        op.f("ck_deployments_ck_deployments_status"),
        "deployments",
        f"status IN ({OLD_DEPLOYMENT_STATUSES})",
    )
