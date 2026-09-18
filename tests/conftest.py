import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_db_session
from app.main import create_app
from app.models import Base
from tests.support import DummyBase

# `os.getenv` below doesn't read `.env` on its own (only pydantic-settings
# does, for the app's own Settings) — load it explicitly so `poetry run
# pytest` picks up TEST_DATABASE_URL without needing it exported by hand.
# An already-exported env var still takes precedence (load_dotenv default).
load_dotenv()

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/mycar_test",
)


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
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client against the FastAPI app, backed by the test database.

    Overrides the app's `get_db_session` dependency (which every router
    and `get_current_user` depend on) so requests hit TEST_DATABASE_URL
    instead of whatever database is configured in `.env` — the same
    commit-on-success/rollback-on-error semantics as the real dependency.
    """
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app = create_app()
    app.dependency_overrides[get_db_session] = override_get_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Database session isolated per test, against a real test Postgres.

    Requires TEST_DATABASE_URL pointing to a Postgres database dedicated
    to tests (see docker-compose and .env.example).
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
