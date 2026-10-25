import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.type import UUIDPrimaryKeyMixin


class RepositoryAnalysis(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "repository_analyses"
    __table_args__ = (
        CheckConstraint(
            "status IN ('QUEUED','RUNNING','SUCCESS','BLOCKED','FAILED','TIMED_OUT','CANCELLED')",
            name="ck_repository_analyses_status",
        ),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="RESTRICT"), index=True
    )
    commit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("commits.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), default="QUEUED", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    report_schema_version: Mapped[str | None] = mapped_column(String(8))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    analysis_data: Mapped[dict | None] = mapped_column(JSONB)


class Service(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint(
            "port IS NULL OR (port >= 1 AND port <= 65535)",
            name="ck_services_port",
        ),
    )

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_analyses.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    service_type: Mapped[str] = mapped_column(String(32))
    language: Mapped[str | None] = mapped_column(String(64))
    framework: Mapped[str | None] = mapped_column(String(64))
    path: Mapped[str] = mapped_column(String(1024), default=".")
    port: Mapped[int | None] = mapped_column(Integer)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
