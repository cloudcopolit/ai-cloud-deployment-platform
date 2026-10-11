import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings
ACCESS_COOKIE = "access_token"

def create_access_token(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),  # who the token is about
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> uuid.UUID:
    """Return the user id, or raise jwt.PyJWTError / ValueError if invalid."""
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],  # always pin the algorithm
        options={"require": ["exp", "sub"]},
    )
    return uuid.UUID(payload["sub"])