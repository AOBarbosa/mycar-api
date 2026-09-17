import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from tests.support import DummyItem


class DummyRepository(BaseRepository[DummyItem]):
    model = DummyItem


@pytest.fixture
def repo(dummy_session: AsyncSession) -> DummyRepository:
    return DummyRepository(dummy_session)


async def test_create_persists_and_returns_the_object(repo: DummyRepository) -> None:
    obj = await repo.create(name="widget", value=1)

    assert obj.id is not None
    assert obj.name == "widget"
    assert obj.value == 1


async def test_get_by_id_returns_existing_object(repo: DummyRepository) -> None:
    created = await repo.create(name="widget", value=1)

    found = await repo.get_by_id(created.id)

    assert found is not None
    assert found.id == created.id


async def test_get_by_id_returns_none_when_missing(repo: DummyRepository) -> None:
    found = await repo.get_by_id(uuid.uuid4())

    assert found is None


async def test_list_returns_all_created_objects(repo: DummyRepository) -> None:
    await repo.create(name="a", value=1)
    await repo.create(name="b", value=2)

    items = await repo.list()

    assert {item.name for item in items} == {"a", "b"}


async def test_list_respects_offset_and_limit(repo: DummyRepository) -> None:
    for i in range(5):
        await repo.create(name=f"item-{i}", value=i)

    page = await repo.list(offset=2, limit=2)

    assert len(page) == 2


async def test_update_changes_fields_and_persists(repo: DummyRepository) -> None:
    obj = await repo.create(name="widget", value=1)

    updated = await repo.update(obj, name="renamed")

    assert updated.name == "renamed"
    found = await repo.get_by_id(obj.id)
    assert found is not None
    assert found.name == "renamed"


async def test_delete_removes_the_object(repo: DummyRepository) -> None:
    obj = await repo.create(name="widget", value=1)

    await repo.delete(obj)

    assert await repo.get_by_id(obj.id) is None
