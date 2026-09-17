"""Shared dependencies for the API routers.

Routers import the database session from here (instead of directly
from `app.core.database`), keeping the HTTP layer isolated from
infrastructure details.
"""

from app.core.database import get_db_session as get_db

__all__ = ["get_db"]
