import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TeamMember(Base):
    """Junction table between users and teams (N:M)."""

    __tablename__ = "team_members"
    __table_args__ = (CheckConstraint("role IN ('OWNER','ADMIN','MEMBER')", name="role_valid"),)

    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="RESTRICT"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True, index=True
    )
    role: Mapped[str] = mapped_column(String(20), default="MEMBER")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
