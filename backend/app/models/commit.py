import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.type import UUIDPrimaryKeyMixin


class Commit(UUIDPrimaryKeyMixin, Base):
    """A commit CloudPilot has seen: listed for a branch picker, pushed to the deployment branch
    (webhook) or analyzed. ``branch_id`` is the branch it was first seen on; a SHA is stored once
    per repository."""

    __tablename__ = "commits"
    __table_args__ = (
        UniqueConstraint("repository_id", "sha"),
        Index("ix_commits_repository_id_committed_at", "repository_id", "committed_at"),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="RESTRICT"), index=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id", ondelete="RESTRICT"), index=True
    )
    sha: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text)
    author_name: Mapped[str | None] = mapped_column(String(255))
    author_email: Mapped[str | None] = mapped_column(String(320))
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
