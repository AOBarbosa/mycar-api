from typing import Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy.orm import DeclarativeBase

from app.repositories.base import BaseRepository

ModelType = TypeVar("ModelType", bound=DeclarativeBase)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class BaseService(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Generic CRUD business logic, delegating persistence to a repository.

    Concrete services should override or extend a method (calling
    `super()` and adding the extra behavior) only when that operation
    has business rules beyond plain CRUD, instead of reimplementing it.
    """

    def __init__(self, repository: BaseRepository[ModelType]) -> None:
        self.repository = repository

    async def create(self, data: CreateSchemaType) -> ModelType:
        return await self.repository.create(**data.model_dump())

    async def get_by_id(self, id: int) -> ModelType | None:
        return await self.repository.get_by_id(id)

    async def list(self, *, offset: int = 0, limit: int = 20) -> list[ModelType]:
        return await self.repository.list(offset=offset, limit=limit)

    async def update(self, obj: ModelType, data: UpdateSchemaType) -> ModelType:
        return await self.repository.update(obj, **data.model_dump(exclude_unset=True))

    async def delete(self, obj: ModelType) -> None:
        await self.repository.delete(obj)
