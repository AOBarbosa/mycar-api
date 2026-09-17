# mycar-api

API for a vehicle management app (CRUD for vehicles, fueling/maintenance
events, maintenance rules and alerts).

> **Current status**: project boilerplate only. No business rule has
> been implemented yet — just structure, configuration, and a health
> check endpoint.

## Stack

- Python 3.12+, FastAPI, Pydantic v2 (pydantic-settings)
- SQLAlchemy 2.0 **async** + asyncpg, Alembic (async migrations)
- PostgreSQL
- pytest + pytest-asyncio + httpx
- Poetry, Docker / Docker Compose

## Layered architecture

```
app/
├── api/          # HTTP routes (routers) and dependencies (deps.py).
│                 # Only validates input/output via schemas and delegates to services.
├── services/     # Business rules. Knows nothing about HTTP or SQL directly.
├── repositories/ # Data access (queries, persistence). Isolates SQLAlchemy.
├── models/       # SQLAlchemy entities (database mapping).
├── schemas/      # Pydantic request/response models (not the database models).
└── core/         # Settings, logging, database connection, security/JWT.
```

Dependency rule: `api` → `services` → `repositories` → `models`.
A layer only knows the layer immediately below it; `services` never
imports `fastapi`, and `repositories` is the only place that knows the
database is Postgres/SQLAlchemy.

`tests/` mirrors this same structure (`tests/api`, `tests/services`,
`tests/repositories`) to keep each layer's tests isolated from it.

### Why async SQLAlchemy?

FastAPI runs on an async event loop. A synchronous database driver
(psycopg2) would block that loop on every query, forcing SQLAlchemy to
delegate calls to a thread pool to avoid stalling other requests. Since
the final API will have several I/O operations per request (vehicles,
events, alert calculations), using async SQLAlchemy 2.0 + `asyncpg`
from the start avoids that bottleneck. The tradeoff is that Alembic
needs an `env.py` adapted to run migrations asynchronously — already
configured in this project.

## Running locally with Docker

1. Copy the environment variables file:
   ```bash
   cp .env.example .env
   ```
2. Start the containers (API + Postgres):
   ```bash
   docker compose up --build
   ```
   In development, `docker-compose.override.yml` is loaded
   automatically and already enables `--reload` with a bind mount of
   the code.
3. Check the health endpoint:
   ```bash
   curl http://localhost:8000/health
   ```

### Migrations (Alembic)

There are no domain migrations yet, only the setup. To generate/apply a
migration inside the API container:

```bash
docker compose exec api alembic revision --autogenerate -m "description"
docker compose exec api alembic upgrade head
```

## Running without Docker (local dev)

```bash
poetry install
cp .env.example .env   # set POSTGRES_HOST=localhost
poetry run uvicorn app.main:app --reload
```

## Running the tests

API tests don't need a database. The `db_session` fixture (for future
repository/service tests) expects a test Postgres reachable via
`TEST_DATABASE_URL` (see `.env.example`) — it can be the same Postgres
from `docker compose`, in a separate database.

```bash
poetry run pytest
```

**Project rule**: every new feature (endpoint, service, repository,
business rule) must ship with the corresponding tests in the same
delivery.

## Next logical steps (out of scope for this step)

- First domain model (e.g. `Vehicle`) + Alembic migration.
- Repository, service and router for vehicles (CRUD), with tests in
  each layer.
- Authentication/JWT in `app/core/security.py`.
- Modeling of events (fueling, maintenance) and alert rules.
