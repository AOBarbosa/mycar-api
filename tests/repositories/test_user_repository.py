from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user import UserRepository


async def test_get_by_email_returns_existing_user(db_session: AsyncSession) -> None:
    repo = UserRepository(db_session)
    user = await repo.create(email="andre@example.com", password_hash="hash", name="Andre")

    found = await repo.get_by_email("andre@example.com")

    assert found is not None
    assert found.id == user.id


async def test_get_by_email_returns_none_when_missing(db_session: AsyncSession) -> None:
    repo = UserRepository(db_session)

    found = await repo.get_by_email("nobody@example.com")

    assert found is None
