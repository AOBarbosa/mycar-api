"""SQLAlchemy entities (database mapping).

No domain model yet — will be added in future steps. `Base` is
re-exported here to serve as a single metadata target for Alembic
(`target_metadata`); `BaseModel` is the id/created_at/updated_at mixin
every domain model should combine with `Base`.
"""

from app.core.database import Base
from app.models.base import BaseModel

__all__ = ["Base", "BaseModel"]
