import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.services.base import BaseService
from tests.support import DummyItem, DummyItemCreate, DummyItemUpdate


class DummyRepository(BaseRepository[DummyItem]):
    model = DummyItem


class DummyService(BaseService[DummyItem, DummyItemCreate, DummyItemUpdate]):
    pass


@pytest.fixture
def service(dummy_session: AsyncSession) -> DummyService:
    return DummyService(DummyRepository(dummy_session))


async def test_create_delegates_to_repository_and_returns_the_model(
    service: DummyService,
) -> None:
    obj = await service.create(DummyItemCreate(name="widget", value=1))

    assert obj.id is not None
    assert obj.name == "widget"
    assert obj.value == 1


async def test_get_by_id_returns_existing_object(service: DummyService) -> None:
    created = await service.create(DummyItemCreate(name="widget", value=1))

    found = await service.get_by_id(created.id)

    assert found is not None
    assert found.id == created.id


async def test_get_by_id_returns_none_when_missing(service: DummyService) -> None:
    assert await service.get_by_id(uuid.uuid4()) is None


async def test_list_returns_created_objects(service: DummyService) -> None:
    await service.create(DummyItemCreate(name="a", value=1))
    await service.create(DummyItemCreate(name="b", value=2))

    items = await service.list()

    assert {item.name for item in items} == {"a", "b"}


async def test_update_only_applies_fields_set_on_the_schema(service: DummyService) -> None:
    obj = await service.create(DummyItemCreate(name="widget", value=1))

    updated = await service.update(obj, DummyItemUpdate(name="renamed"))

    assert updated.name == "renamed"
    assert updated.value == 1  # untouched: not present on the update schema


async def test_delete_removes_the_object(service: DummyService) -> None:
    obj = await service.create(DummyItemCreate(name="widget", value=1))

    await service.delete(obj)

    assert await service.get_by_id(obj.id) is None
