import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.type import UUIDPrimaryKeyMixin


class AWSAccount(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "aws_accounts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING_VERIFICATION','ACTIVE','VERIFICATION_FAILED','DISCONNECTED')",
            name="ck_aws_accounts_status",
        ),
    )

    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="RESTRICT"), index=True
    )
    aws_account_id: Mapped[str] = mapped_column(String(12))
    role_arn: Mapped[str | None] = mapped_column(Text)
    readonly_role_arn: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str] = mapped_column(String(64), unique=True)
    default_region: Mapped[str] = mapped_column(String(32), default="us-east-1")
    status: Mapped[str] = mapped_column(String(24), default="PENDING_VERIFICATION")
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # onboarding (ADR-027) and the last verification's evidence (ADR-028)
    state_bucket: Mapped[str | None] = mapped_column(String(63))
    boundary_arn: Mapped[str | None] = mapped_column(Text)
    onboarding_stack: Mapped[str | None] = mapped_column(String(128))
    verified_identity_arn: Mapped[str | None] = mapped_column(Text)
    external_id_enforced: Mapped[bool | None] = mapped_column(Boolean)
    verification_message: Mapped[str | None] = mapped_column(Text)
