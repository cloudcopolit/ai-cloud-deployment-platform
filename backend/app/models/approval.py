import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.type import UUIDPrimaryKeyMixin


class Approval(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "approvals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED','EXPIRED')",
            name="ck_approvals_status",
        ),
    )

    deployment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("deployments.id", ondelete="RESTRICT"), index=True
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    reason: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
