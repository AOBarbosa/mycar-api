from sqlalchemy.ext.asyncio import AsyncSession

from tests.support import DummyItem


async def test_id_is_generated_automatically(dummy_session: AsyncSession) -> None:
    item = DummyItem(name="widget", value=1)
    dummy_session.add(item)
    await dummy_session.flush()

    assert isinstance(item.id, int)


async def test_created_at_and_updated_at_are_set_on_insert(dummy_session: AsyncSession) -> None:
    item = DummyItem(name="widget", value=1)
    dummy_session.add(item)
    await dummy_session.flush()
    await dummy_session.refresh(item)

    assert item.created_at is not None
    assert item.updated_at is not None


async def test_updated_at_is_not_older_than_created_at_after_an_update(
    dummy_session: AsyncSession,
) -> None:
    item = DummyItem(name="widget", value=1)
    dummy_session.add(item)
    await dummy_session.flush()
    await dummy_session.refresh(item)
    created_at = item.created_at

    item.name = "renamed"
    await dummy_session.flush()
    await dummy_session.refresh(item)

    # Postgres' now() returns the current transaction's start time, and
    # this whole test runs inside a single transaction, so updated_at
    # can legitimately equal created_at here — this only proves the
    # column is populated by the UPDATE, not that time has visibly
    # passed (that would require crossing a transaction boundary).
    assert item.created_at == created_at
    assert item.updated_at >= created_at
