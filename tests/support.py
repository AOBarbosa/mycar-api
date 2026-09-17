"""Test-only fixtures shared across layers.

`DummyItem` exists solely to exercise the generic `BaseModel` /
`BaseRepository` / `BaseService` layers without depending on a real
domain model (none exists yet). It combines `app.models.base.BaseModel`
(the id/created_at/updated_at mixin) with its own throwaway
`DeclarativeBase`, separate from `app.core.database.Base`, so it never
appears in Alembic's `target_metadata` / autogenerate.
"""

from pydantic import BaseModel as PydanticModel
from sqlalchemy.orm import DeclarativeBase, Mapped

from app.models.base import BaseModel


class DummyBase(DeclarativeBase):
    pass


class DummyItem(BaseModel, DummyBase):
    __tablename__ = "dummy_items"

    name: Mapped[str]
    value: Mapped[int]


class DummyItemCreate(PydanticModel):
    name: str
    value: int


class DummyItemUpdate(PydanticModel):
    name: str | None = None
    value: int | None = None
