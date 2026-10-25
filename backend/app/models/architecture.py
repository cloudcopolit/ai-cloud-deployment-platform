import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.type import TimestampMixin, UUIDPrimaryKeyMixin


class Architecture(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "architectures"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','ARCHIVED')", name="ck_architectures_status"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")


class ArchitectureVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "architecture_versions"
    __table_args__ = (
        CheckConstraint("version_number > 0", name="ck_architecture_versions_version_number"),
        CheckConstraint(
            "status IN ('DRAFT','VALIDATED','INVALID','APPROVED','SUPERSEDED')",
            name="ck_architecture_versions_status",
        ),
        UniqueConstraint(
            "architecture_id",
            "version_number",
            name="uq_architecture_versions_architecture_id_version_number",
        ),
    )

    architecture_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("architectures.id", ondelete="RESTRICT"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer)
    source_analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("repository_analyses.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), default="DRAFT")
    architecture_data: Mapped[dict] = mapped_column(JSONB)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
