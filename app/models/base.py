import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class BaseModel:
    """Mixin adding id/created_at/updated_at to every domain model.

    Not a `DeclarativeBase` itself — combine it with the app's `Base`
    via multiple inheritance, mixin first:
    `class Vehicle(BaseModel, Base): __tablename__ = "vehicles"`.
    Being a plain mixin (not tied to a specific declarative base) also
    lets tests combine it with a throwaway base to exercise it in
    isolation (see `tests/support.py::DummyItem`).
    """

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
