from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.type import TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    github_user_id: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(
        String(320), unique=True
    )  # GitHub emails can be hidden
    avatar_url: Mapped[str | None] = mapped_column(String(500))
