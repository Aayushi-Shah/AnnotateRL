from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import decode_access_token
from app.core.db import get_db
from app.core.redis import get_redis
from app.models.user import User, UserRole

security = HTTPBearer()

DbDep = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: DbDep,
) -> User:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if not user_id:
            raise exc
    except (JWTError, ValueError):
        raise exc

    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        raise exc
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_researcher(current_user: CurrentUser) -> User:
    if current_user.role not in (UserRole.researcher, UserRole.admin):
        raise HTTPException(status_code=403, detail="Researcher access required")
    return current_user


async def require_annotator(current_user: CurrentUser) -> User:
    if current_user.role not in (UserRole.annotator, UserRole.admin):
        raise HTTPException(status_code=403, detail="Annotator access required")
    return current_user


ResearcherDep = Annotated[User, Depends(require_researcher)]
AnnotatorDep = Annotated[User, Depends(require_annotator)]
