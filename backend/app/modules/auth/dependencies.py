from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.dependencies import DbSession
from app.core.security import ACCESS_COOKIE, decode_access_token
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)  # don't fail automatically; the cookie may exist


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DbSession,
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = credentials.credentials if credentials else request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise unauthorized

    try:
        user_id = decode_access_token(token)
    except (jwt.PyJWTError, ValueError):
        raise unauthorized from None

    user = db.get(User, user_id)
    if user is None:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
