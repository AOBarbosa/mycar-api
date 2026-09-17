import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import create_app
from app.models import Base
from tests.support import DummyBase

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/mycar_test",
)


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client against the FastAPI app, without a real server."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


async def _session_against(metadata: MetaData) -> AsyncGenerator[AsyncSession, None]:
    """Create/drop the tables for `metadata` around a single test session."""
    engine = create_async_engine(TEST_DATABASE_URL)

    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Database session isolated per test, against a real test Postgres.

    Requires TEST_DATABASE_URL pointing to a Postgres database dedicated
    to tests (see docker-compose and .env.example). There is no domain
    model yet, so create_all/drop_all are no-ops — the fixture is
    already in place for when the first models are added.
    """
    async for session in _session_against(Base.metadata):
        yield session


@pytest_asyncio.fixture
async def dummy_session() -> AsyncGenerator[AsyncSession, None]:
    """Database session backed only by the throwaway `DummyItem` table.

    Used to test the generic BaseRepository/BaseService layer without
    depending on any real domain model or touching `Base.metadata`.
    """
    async for session in _session_against(DummyBase.metadata):
        yield session
