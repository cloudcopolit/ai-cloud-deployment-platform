import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
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
