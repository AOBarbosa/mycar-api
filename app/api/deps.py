"""Shared dependencies for the API routers.

Routers import the database session and the current-user resolver from
here (instead of directly from `app.core.database`/`app.services.user`),
keeping the HTTP layer isolated from infrastructure details.
"""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session as get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.repositories.user import UserRepository
from app.services.user import UserService

__all__ = ["get_current_user", "get_db"]

# auto_error=False: a missing Authorization header must also resolve to
# our own 401 below, not FastAPI's default 403 for this dependency.
_bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise _unauthorized()

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise _unauthorized() from exc

    user = await UserService(UserRepository(db)).get_by_id(user_id)
    if user is None:
        raise _unauthorized()

    return user
