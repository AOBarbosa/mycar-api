"""Data access layer (queries, persistence).

Isolates SQLAlchemy from the rest of the application. `base.py` has the
generic `BaseRepository` shared by every entity; no domain repository
yet, will be added in future steps.
"""
