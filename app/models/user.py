from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import BaseModel


class User(BaseModel, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(unique=True, index=True)
    password_hash: Mapped[str]
    name: Mapped[str]
