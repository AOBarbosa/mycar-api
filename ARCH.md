# MeuCarro API — Data Model & API Contract

> **Status**: approved. This is the source of truth `PLAN.md` is built on
> top of. The decisions below (originally listed as open assumptions) were
> reviewed and accepted as-is.

## 1. Entities

### User

| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| email | string | unique, used for login |
| password_hash | string | never returned in responses |
| name | string | |
| created_at | datetime | |
| updated_at | datetime | |

### Vehicle

Owned by exactly one `User`.

| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| owner_id | UUID | FK → User |
| brand | string | e.g. "Toyota" |
| model | string | e.g. "Corolla" |
| year | int | |
| license_plate | string | unique per owner |
| color | string \| null | |
| fuel_type | enum: `gasoline`, `ethanol`, `flex`, `diesel`, `electric`, `hybrid` | default fuel type of the vehicle |
| current_mileage | int | odometer, in km; kept up to date by Events |
| created_at | datetime | |
| updated_at | datetime | |

### Event

A single timeline entry for a vehicle: either a **fueling** or a
**maintenance** event. Modeled as one resource with a `type` discriminator
and a type-specific `details` object, rather than two separate resources,
so the timeline can be listed/sorted as one collection.

| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| vehicle_id | UUID | FK → Vehicle |
| type | enum: `fueling`, `maintenance` | discriminator |
| source | enum: `manual`, `voice` | how the event was created |
| event_date | date | |
| mileage | int | odometer reading at event time |
| notes | string \| null | free text |
| details | object | see below, shape depends on `type` |
| raw_text | string \| null | original transcript, only set when `source = voice` |
| created_at | datetime | |
| updated_at | datetime | |

`details` when `type = fueling`:

| Field | Type | Notes |
|---|---|---|
| liters | float | |
| price_per_liter | float | |
| total_cost | float | |
| full_tank | bool | |
| fuel_type | enum (same as Vehicle.fuel_type, minus `flex`) | fuel actually used this time |
| gas_station | string \| null | |

`details` when `type = maintenance`:

| Field | Type | Notes |
|---|---|---|
| maintenance_type | enum: `oil_change`, `tire_rotation`, `brake_pads`, `battery`, `air_filter`, `other` | |
| cost | float \| null | |
| workshop | string \| null | |
| resolved_alert_id | UUID \| null | set if this event auto-resolved an open Alert |

### MaintenanceRule

Defines a recurring maintenance interval for one vehicle (e.g. "oil change
every 10,000 km or 12 months").

| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| vehicle_id | UUID | FK → Vehicle |
| maintenance_type | enum (same list as Event.details.maintenance_type) | |
| interval_km | int \| null | at least one of interval_km / interval_months required |
| interval_months | int \| null | |
| last_done_mileage | int \| null | seeded from the most recent matching maintenance Event |
| last_done_date | date \| null | |
| active | bool | inactive rules stop generating alerts |
| created_at | datetime | |
| updated_at | datetime | |

### Alert

System-generated only (no direct client creation) — produced by comparing
`MaintenanceRule`s against the vehicle's current mileage/date, and
auto-resolved when a matching maintenance `Event` is registered.

| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| vehicle_id | UUID | FK → Vehicle |
| maintenance_rule_id | UUID | FK → MaintenanceRule |
| severity | enum: `info` (approaching), `warning` (due), `critical` (overdue) | |
| status | enum: `open`, `resolved`, `dismissed` | |
| message | string | human-readable, generated |
| due_mileage | int \| null | |
| due_date | date \| null | |
| resolved_by_event_id | UUID \| null | set when auto-resolved by an Event |
| created_at | datetime | |
| resolved_at | datetime \| null | |

### Summary (computed, not persisted)

Read-only aggregate, consumed by the dashboard and (later) CarPlay.

| Field | Type | Notes |
|---|---|---|
| vehicle | Vehicle | |
| last_fueling_event | Event \| null | |
| last_maintenance_event | Event \| null | |
| open_alerts | Alert[] | |
| avg_consumption_km_per_liter | float \| null | computed from fueling history |
| total_spent_last_30_days | float | fueling + maintenance |
| total_spent_last_12_months | float | fueling + maintenance |

## 2. Conventions used across the whole API

- **Auth**: Bearer JWT (`Authorization: Bearer <token>`) on every endpoint
  except `POST /auth/register` and `POST /auth/login`.
- **Ownership**: every Vehicle-scoped resource (Event, MaintenanceRule,
  Alert) is only visible/mutable by the Vehicle's `owner_id`. Accessing a
  resource that exists but belongs to another user returns **404** (not
  403), to avoid leaking existence of other users' data.
- **Pagination**: all list endpoints accept `page` (default 1) and
  `page_size` (default 20, max 100) query params, and respond with
  `{ "items": [...], "total": int, "page": int, "page_size": int }`.
- **Errors**: `{ "detail": string }` for simple errors; `422` for request
  validation errors uses FastAPI's default
  `{ "detail": [{ "loc", "msg", "type" }] }` shape.
- **IDs**: UUIDs everywhere, returned as strings.
- **Dates/times**: ISO 8601, UTC for datetimes.

## 3. Endpoints

### auth

| Method & path | Auth | Request | Response | Notes |
|---|---|---|---|---|
| `POST /auth/register` | public | `{email, password, name}` | `201 {id, email, name, created_at}` · `400` if email already taken | |
| `POST /auth/login` | public | `{email, password}` | `200 {access_token, token_type, expires_in}` · `401` invalid credentials | |
| `GET /auth/me` | authenticated | — | `200 {id, email, name, created_at}` · `401` | |

### vehicles

| Method & path | Auth | Request | Response | Notes |
|---|---|---|---|---|
| `POST /vehicles` | authenticated | `{brand, model, year, license_plate, color?, fuel_type, current_mileage}` | `201 Vehicle` · `400` validation | owner_id set from token |
| `GET /vehicles` | authenticated | query: `page, page_size` | `200 Page<Vehicle>` | only current user's vehicles |
| `GET /vehicles/{id}` | authenticated, owner | — | `200 Vehicle` · `404` | |
| `PATCH /vehicles/{id}` | authenticated, owner | partial `Vehicle` fields | `200 Vehicle` · `400` · `404` | |
| `DELETE /vehicles/{id}` | authenticated, owner | — | `204` · `404` | cascades to its Events, MaintenanceRules, Alerts (see Decisions) |

### events

| Method & path | Auth | Request | Response | Notes |
|---|---|---|---|---|
| `POST /vehicles/{vehicle_id}/events` | authenticated, owner of vehicle | `{type, event_date, mileage, notes?, details}` | `201 Event` · `400` validation · `404` vehicle not found | **side effects**: (1) bumps `Vehicle.current_mileage` if `mileage` is greater than current; (2) if `type=maintenance` and there's an open `Alert` for that vehicle+maintenance_type, auto-resolves it (`status=resolved`, `resolved_by_event_id` set) and updates the matching `MaintenanceRule.last_done_*` |
| `POST /vehicles/{vehicle_id}/events/voice` | authenticated, owner of vehicle | `{raw_text}` | `201 Event` (with `source=voice`, `raw_text` stored) · `422` if the text can't be parsed with enough confidence · `404` vehicle not found | v1 parser is **regex/rule-based only**, no LLM (see Issue for this) |
| `GET /vehicles/{vehicle_id}/events` | authenticated, owner of vehicle | query: `page, page_size, type?, from?, to?` | `200 Page<Event>` · `404` vehicle not found | sorted by `event_date` desc |
| `GET /events/{id}` | authenticated, owner (via vehicle) | — | `200 Event` · `404` | |
| `PATCH /events/{id}` | authenticated, owner (via vehicle) | partial `Event` fields | `200 Event` · `400` · `404` | does **not** re-run the alert-resolution side effect (see Decisions) |
| `DELETE /events/{id}` | authenticated, owner (via vehicle) | — | `204` · `404` | does **not** reopen an Alert it had resolved (see Decisions) |

### maintenance-rules

| Method & path | Auth | Request | Response | Notes |
|---|---|---|---|---|
| `POST /vehicles/{vehicle_id}/maintenance-rules` | authenticated, owner of vehicle | `{maintenance_type, interval_km?, interval_months?}` | `201 MaintenanceRule` · `400` if both intervals missing · `404` vehicle not found | |
| `GET /vehicles/{vehicle_id}/maintenance-rules` | authenticated, owner of vehicle | query: `page, page_size, active?` | `200 Page<MaintenanceRule>` · `404` | |
| `GET /maintenance-rules/{id}` | authenticated, owner (via vehicle) | — | `200 MaintenanceRule` · `404` | |
| `PATCH /maintenance-rules/{id}` | authenticated, owner (via vehicle) | partial fields | `200 MaintenanceRule` · `400` · `404` | |
| `DELETE /maintenance-rules/{id}` | authenticated, owner (via vehicle) | — | `204` · `404` | also deletes/cancels its open Alerts |

### alerts

| Method & path | Auth | Request | Response | Notes |
|---|---|---|---|---|
| `GET /alerts` | authenticated | query: `page, page_size, status?` | `200 Page<Alert>` | across all of the current user's vehicles — the "inbox" view |
| `GET /vehicles/{vehicle_id}/alerts` | authenticated, owner of vehicle | query: `page, page_size, status?` | `200 Page<Alert>` · `404` | |
| `GET /alerts/{id}` | authenticated, owner (via vehicle) | — | `200 Alert` · `404` | |
| `POST /alerts/{id}/resolve` | authenticated, owner (via vehicle) | — | `200 Alert` (`status=dismissed`) · `404` · `400` if already resolved | manual dismissal, no Event involved |

Alerts have **no direct create endpoint** — they're only produced by a
periodic job comparing `MaintenanceRule`s to the vehicle's current state
(covered as an infra/cross-cutting issue in `PLAN.md`).

### summary

| Method & path | Auth | Request | Response | Notes |
|---|---|---|---|---|
| `GET /vehicles/{vehicle_id}/summary` | authenticated, owner of vehicle | — | `200 Summary` · `404` | |
| `GET /summary` | authenticated | — | `200 {vehicles: Summary[]}` | one Summary per vehicle owned by the user; the "CarPlay overview" |

## 4. Generic base layers (models, repositories & services)

To avoid repeating CRUD boilerplate for every entity, the model,
repository and service layers each have a generic base class that
concrete entities extend. Already implemented (not domain-specific, so
it doesn't depend on the entities above being confirmed):

### `app/models/base.py` — `BaseModel`

```python
class BaseModel:
    """Plain mixin, not a DeclarativeBase — see docstring for why."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

Every domain model combines this mixin with the app's `Base`, mixin
first (SQLAlchemy's recommended order for declarative mixins):

```python
class Vehicle(BaseModel, Base):
    __tablename__ = "vehicles"

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    brand: Mapped[str]
    # ... id, created_at, updated_at come from BaseModel
```

`BaseModel` is deliberately **not** itself a `DeclarativeBase` — it's a
mixin with no base class of its own. That's what lets
`tests/support.py::DummyItem` combine it with a throwaway
`DeclarativeBase` (`DummyBase`) to test the mixin's behavior (id
generation, timestamps) without that test table ever being mapped onto
`app.core.database.Base`, and therefore never leaking into Alembic's
`target_metadata`. If `BaseModel` inherited `DeclarativeBase` directly
instead of being a plain mixin, every model built on it — including
test-only ones — would share one metadata registry, and this isolation
would be lost.

`created_at`/`updated_at` use `server_default=func.now()` /
`onupdate=func.now()` (DB-side, via Postgres `now()`) rather than
Python-side defaults, so they stay correct regardless of which process
writes the row. Note the standard Postgres caveat: `now()` returns the
current **transaction's** start time, not per-statement wall-clock time
— irrelevant in production (one transaction per request), but means
`updated_at` can equal `created_at` when both happen inside the same
test transaction (see `tests/models/test_base_model.py`).

### `app/repositories/base.py` — `BaseRepository[ModelType]`

```python
ModelType = TypeVar("ModelType", bound=DeclarativeBase)

class BaseRepository(Generic[ModelType]):
    model: type[ModelType]

    def __init__(self, session: AsyncSession) -> None: ...
    async def create(self, **values: object) -> ModelType: ...
    async def get_by_id(self, id: UUID) -> ModelType | None: ...
    async def list(self, *, offset: int = 0, limit: int = 20) -> list[ModelType]: ...
    async def update(self, obj: ModelType, **values: object) -> ModelType: ...
    async def delete(self, obj: ModelType) -> None: ...
```

A concrete repository parametrizes the generic, sets `model` as a class
attribute, and only adds entity-specific queries:

```python
class VehicleRepository(BaseRepository[Vehicle]):
    model = Vehicle

    async def list_by_owner(self, owner_id: UUID) -> list[Vehicle]:
        stmt = select(self.model).where(self.model.owner_id == owner_id)
        return list((await self.session.execute(stmt)).scalars().all())
```

### `app/services/base.py` — `BaseService[ModelType, CreateSchemaType, UpdateSchemaType]`

```python
class BaseService(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, repository: BaseRepository[ModelType]) -> None: ...
    async def create(self, data: CreateSchemaType) -> ModelType: ...
    async def get_by_id(self, id: UUID) -> ModelType | None: ...
    async def list(self, *, offset: int = 0, limit: int = 20) -> list[ModelType]: ...
    async def update(self, obj: ModelType, data: UpdateSchemaType) -> ModelType: ...
    async def delete(self, obj: ModelType) -> None: ...
```

A concrete service extends the base with the right entity/schemas and
only overrides a method when it needs business logic beyond plain CRUD
— always calling `super()` to reuse the base behavior instead of
reimplementing it:

```python
class EventService(BaseService[Event, EventCreate, EventUpdate]):
    def __init__(self, repository: EventRepository, alert_repository: AlertRepository) -> None:
        super().__init__(repository)
        self.alert_repository = alert_repository

    async def create(self, data: EventCreate) -> Event:
        event = await super().create(data)
        if event.type == "maintenance":
            await self._resolve_matching_alert(event)
        return event
```

### Typing strategy

- `ModelType` is bound to SQLAlchemy's own `DeclarativeBase`, not the
  app's `Base` subclass. This keeps the repository layer generic and
  is what lets tests exercise it with a throwaway model
  (`tests/support.py::DummyItem`) without that model ever touching
  `app.models.Base.metadata` — so it never leaks into Alembic's
  `target_metadata` / autogenerate. Every real domain model, being a
  subclass of `app.core.database.Base` which itself subclasses
  `DeclarativeBase`, still satisfies the bound.
- `CreateSchemaType` / `UpdateSchemaType` are bound to Pydantic's
  `BaseModel`.
- `model` is a typed class attribute (`model: type[ModelType]`), not a
  constructor argument. A subclass like
  `class VehicleRepository(BaseRepository[Vehicle])` gets `self.model`
  inferred as `type[Vehicle]`, and every inherited method returns
  `Vehicle` instead of the generic `ModelType` — Pyright/mypy resolve
  this once the concrete type parameter is supplied, no per-method
  annotations needed in subclasses.
- `create`/`update` accept `**values: object` at the repository level
  (they receive already-dumped Pydantic data from the service, so
  there's no schema left to check there). The type safety that
  matters — `service.create(data: CreateSchemaType)` and
  `service.update(obj: ModelType, data: UpdateSchemaType)` — is
  enforced one layer up, where callers actually pass concrete schema
  instances.

### File placement

- `app/repositories/base.py` — `BaseRepository`
- `app/services/base.py` — `BaseService`
- Concrete repositories/services stay in their existing directories
  (`app/repositories/vehicle.py`, `app/services/vehicle.py`, etc.),
  each importing and extending the matching base class.

### Tests

`tests/models/test_base_model.py`,
`tests/repositories/test_base_repository.py` and
`tests/services/test_base_service.py` cover the generic layer against
`tests/support.py::DummyItem` — id auto-generation, created_at/
updated_at population, create, get_by_id found/not found, list with
offset/limit, update (including that `BaseService.update` only applies
fields actually set on the update schema), and delete — so the base
classes are proven correct before any domain model/service depends on
them.

## Decisions

These were invented because no contract existed yet, and are now approved:

1. **404 vs 403 for cross-owner access** — chose 404 everywhere to avoid
   leaking existence. Confirm this is the desired behavior.
2. **Vehicle deletion cascades** to its Events, MaintenanceRules and Alerts.
   Alternative: block deletion if the vehicle has Events (safer, but more
   friction). Which do you want?
3. **Voice endpoint (`POST .../events/voice`) auto-creates the Event** on a
   successful parse, with no confirmation step. Alternative: return a
   *draft* parsed Event for the user to confirm/edit before it's persisted
   (an extra `POST .../events/voice/confirm` step). This changes the shape
   of the voice issue significantly — please pick one.
4. **Editing/deleting an Event that resolved an Alert does not reopen the
   Alert** — kept simple for MVP. Flag if you want that consistency
   handled now vs. deferred.
5. **MaintenanceRule is always vehicle-scoped** — no user-level "template"
   rules that get copied to every new vehicle. Confirm this is acceptable
   for MVP (a template system could come later).
6. **Units are km** (not miles) — no unit field, assumed fixed for all
   users. Confirm this is fine (no internationalization requirement yet).
7. **No password reset / refresh token** in this contract — `POST
   /auth/login` issues a single JWT with a fixed expiry
   (`ACCESS_TOKEN_EXPIRE_MINUTES`, already in `core/config.py`). Confirm
   that's acceptable for MVP, or if refresh tokens should be in scope now.
8. **Alert severity thresholds** (when does `info` become `warning` become
   `critical`?) are left as an implementation detail of the periodic job,
   not specified here (e.g. "warning at due date/mileage, critical N days/
   km past due"). Should this be configurable per rule, or a fixed global
   rule?
