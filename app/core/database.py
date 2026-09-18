from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.sqlalchemy_database_uri, echo=settings.DEBUG, future=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, expire_on_commit=False, autoflush=False
)


class Base(DeclarativeBase):
    """Declarative base for every SQLAlchemy model."""


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Commits on a clean request, rolls back if anything raised.

    Repositories only `flush()` (never `commit()`), so without this the
    session would just discard every write when it closes at the end of
    the request.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
