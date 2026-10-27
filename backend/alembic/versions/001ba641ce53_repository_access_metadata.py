"""repository access metadata (ADR-021)

How CloudPilot reached a repository (GitHub App / token / anonymous), whether it is private,
when it was last synced, and the commit-history index from 04 §9.

Revision ID: 001ba641ce53
Revises: 9f907e2152cb
Create Date: 2026-10-25 15:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001ba641ce53"
down_revision: str | Sequence[str] | None = "9f907e2152cb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "repositories",
        sa.Column("is_private", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "repositories",
        sa.Column(
            "access_mode",
            sa.String(length=16),
            server_default=sa.text("'ANONYMOUS'"),
            nullable=False,
        ),
    )
    op.add_column(
        "repositories",
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_repositories_access_mode_valid"),
        "repositories",
        "access_mode IN ('GITHUB_APP','TOKEN','ANONYMOUS')",
    )
    op.create_index(
        "ix_commits_repository_id_committed_at",
        "commits",
        ["repository_id", "committed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_commits_repository_id_committed_at", table_name="commits")
    op.drop_constraint(op.f("ck_repositories_access_mode_valid"), "repositories", type_="check")
    op.drop_column("repositories", "last_synced_at")
    op.drop_column("repositories", "access_mode")
    op.drop_column("repositories", "is_private")
