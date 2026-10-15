import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.type import UUIDPrimaryKeyMixin


class Subscription(UUIDPrimaryKeyMixin, Base):
    """A team's plan history. One row per plan period."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE','TRIALING','PAST_DUE','CANCELLED','EXPIRED')",
            name="status_valid",
        ),
        # A team can have only one active subscription at a time.
        Index(
            "uq_subscriptions_one_active_per_team",
            "team_id",
            unique=True,
            postgresql_where=text("status IN ('ACTIVE','TRIALING')"),
        ),
    )

    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="RESTRICT"), index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plans.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    price_at_subscription: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # price snapshot
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_subscription_id: Mapped[str | None] = mapped_column(String(255))
