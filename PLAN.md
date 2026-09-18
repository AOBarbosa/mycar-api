# mycar-api — Implementation Plan

> Source of truth: `ARCH.md` (approved). Boilerplate and the generic base
> layers (`BaseModel`, `BaseRepository[ModelType]`,
> `BaseService[ModelType, CreateSchemaType, UpdateSchemaType]`) already
> exist and are already tested — no issue below re-implements or re-tests
> plain CRUD; every issue only covers what's specific to that entity.

## 1. Feature list (business language)

### Authentication & users

- **Create an account** — a new user registers with email/password so
  everything they track afterwards (vehicles, history, alerts) is private
  to them.
- **Log in** — a registered user authenticates and receives access to the
  rest of the app.
- **View my profile** — a logged-in user can check their own account
  details.

### Vehicle management

- **Register a vehicle** — the user adds a car to their garage (brand,
  model, year, plate, current mileage), which becomes the anchor for all
  future tracking.
- **List my vehicles** — the user sees every vehicle they've registered.
- **View a vehicle's details** — the user opens one vehicle to see its
  full info.
- **Edit a vehicle** — the user corrects or updates data (e.g. mileage,
  color) as things change.
- **Remove a vehicle** — the user deletes a vehicle they no longer track,
  along with its entire history (events, rules, alerts).

### Event logging (manual and by voice)

- **Log a fueling manually** — the user records a fill-up (liters, price,
  mileage) to track fuel costs and consumption over time.
- **Log a maintenance manually** — the user records a service performed
  (oil change, tires, etc.) so the app knows the vehicle is up to date.
- **Log an event by voice** — the user dictates what happened ("filled up
  40 liters at 5.89 a liter") and the app turns it into a fueling or
  maintenance record automatically, without typing it in.
- **View a vehicle's history** — the user browses a timeline of everything
  logged for a vehicle.
- **Correct or remove an event** — the user fixes a mistake in something
  they logged before.

### Maintenance rules

- **Set a maintenance interval** — the user configures how often a type of
  maintenance should happen (e.g. oil change every 10,000 km or 12
  months), so the app knows when it's due.
- **Manage existing rules** — the user reviews, edits, or turns off the
  rules configured for a vehicle.

### Alerts

- **Get warned when maintenance is due** — the app automatically flags a
  vehicle as approaching, due, or overdue for a maintenance, without the
  user having to check manually.
- **Alerts clear themselves** — logging the matching maintenance
  automatically resolves the alert that was open for it.
- **Dismiss an alert manually** — the user can mark an alert as handled
  even without logging a matching event (e.g. "I know, I'll deal with it
  later").
- **See everything pending, in one place** — the user gets a single inbox
  of every open alert across all their vehicles.

### Dashboard / summary (future CarPlay)

- **At-a-glance vehicle status** — the user sees, per vehicle, the last
  fueling, the last maintenance, open alerts, and recent spending, without
  digging through the full history.
- **Fuel economy tracking** — the user sees their average consumption
  (km/liter), computed automatically from their fueling history.
- **Spending overview** — the user sees how much they've spent (fuel +
  maintenance) recently, at a glance.

## 2. Endpoint-by-endpoint explanation

Conventions that apply to *every* row below (see `ARCH.md` §2 for the full
detail, not repeated per row):

- Every endpoint except `POST /auth/register` and `POST /auth/login`
  requires a valid Bearer JWT, or responds **401**.
- There is no **403** anywhere in this API: a resource that exists but
  belongs to another user responds **404**, same as if it didn't exist.
- All list endpoints are paginated (`page`, `page_size` query params),
  wrapped as `{ items, total, page, page_size }`.

### auth

| Endpoint | What it does | Who can call | Request | Response | Side effects |
|---|---|---|---|---|---|
| `POST /auth/register` | Creates a new user account | public | `{email, password, name}` | `201` user (no password) · `400` email already registered | none |
| `POST /auth/login` | Exchanges credentials for a JWT | public | `{email, password}` | `200 {access_token, token_type, expires_in}` · `401` wrong email/password | none |
| `GET /auth/me` | Returns the caller's own account | authenticated | — | `200` current user · `401` | none |

### vehicles

| Endpoint | What it does | Who can call | Request | Response | Side effects |
|---|---|---|---|---|---|
| `POST /vehicles` | Registers a vehicle owned by the caller | authenticated | Vehicle fields | `201` Vehicle · `400` validation (e.g. duplicate plate for this owner) | none |
| `GET /vehicles` | Lists the caller's own vehicles | authenticated | `page, page_size` | `200` Page\<Vehicle\> | none |
| `GET /vehicles/{id}` | Fetches one vehicle | authenticated, owner | — | `200` Vehicle · `404` | none |
| `PATCH /vehicles/{id}` | Updates a vehicle's fields | authenticated, owner | partial Vehicle | `200` Vehicle · `400` · `404` | none |
| `DELETE /vehicles/{id}` | Deletes a vehicle | authenticated, owner | — | `204` · `404` | **cascades**: deletes its Events, MaintenanceRules and Alerts |

### events

| Endpoint | What it does | Who can call | Request | Response | Side effects |
|---|---|---|---|---|---|
| `POST /vehicles/{vehicle_id}/events` | Logs a fueling or maintenance event manually | authenticated, owner of vehicle | `{type, event_date, mileage, notes?, details}` (`details` shape depends on `type`) | `201` Event · `400` validation (e.g. `details` doesn't match `type`) · `404` vehicle not found | (1) bumps `Vehicle.current_mileage` if `mileage` is greater than the current value; (2) **only from Issue 7 onward**: if `type=maintenance` and there's a matching open Alert for that vehicle + maintenance_type, resolves it and updates the matching MaintenanceRule's `last_done_*` |
| `POST /vehicles/{vehicle_id}/events/voice` | Logs an event by parsing free-text/voice-transcribed input | authenticated, owner of vehicle | `{raw_text}` | `201` Event (`source=voice`) · `422` couldn't parse with confidence · `404` vehicle not found | same as manual create, once the parse succeeds |
| `GET /vehicles/{vehicle_id}/events` | Lists a vehicle's timeline | authenticated, owner of vehicle | `page, page_size, type?, from?, to?` | `200` Page\<Event\> · `404` | none |
| `GET /events/{id}` | Fetches one event | authenticated, owner via vehicle | — | `200` Event · `404` | none |
| `PATCH /events/{id}` | Corrects an event | authenticated, owner via vehicle | partial Event | `200` Event · `400` · `404` | none — does **not** re-run mileage bump or alert resolution (see `ARCH.md` decision #4) |
| `DELETE /events/{id}` | Removes an event | authenticated, owner via vehicle | — | `204` · `404` | none — does **not** reopen an Alert it had resolved (see `ARCH.md` decision #4) |

### maintenance-rules

| Endpoint | What it does | Who can call | Request | Response | Side effects |
|---|---|---|---|---|---|
| `POST /vehicles/{vehicle_id}/maintenance-rules` | Defines a recurring maintenance interval | authenticated, owner of vehicle | `{maintenance_type, interval_km?, interval_months?}` | `201` MaintenanceRule · `400` neither interval set · `404` vehicle not found | none |
| `GET /vehicles/{vehicle_id}/maintenance-rules` | Lists a vehicle's rules | authenticated, owner of vehicle | `page, page_size, active?` | `200` Page\<MaintenanceRule\> · `404` | none |
| `GET /maintenance-rules/{id}` | Fetches one rule | authenticated, owner via vehicle | — | `200` MaintenanceRule · `404` | none |
| `PATCH /maintenance-rules/{id}` | Edits a rule (including toggling `active`) | authenticated, owner via vehicle | partial fields | `200` MaintenanceRule · `400` · `404` | none |
| `DELETE /maintenance-rules/{id}` | Removes a rule | authenticated, owner via vehicle | — | `204` · `404` | **cascades**: deletes/cancels its open Alerts |

### alerts

There is **no create endpoint** for alerts — they only come from the
periodic generation job (Issue 8). Everything below is read or manual
dismissal only.

| Endpoint | What it does | Who can call | Request | Response | Side effects |
|---|---|---|---|---|---|
| `GET /alerts` | Lists every open/handled alert across *all* the caller's vehicles — the "inbox" | authenticated | `page, page_size, status?` | `200` Page\<Alert\> | none |
| `GET /vehicles/{vehicle_id}/alerts` | Lists one vehicle's alerts | authenticated, owner of vehicle | `page, page_size, status?` | `200` Page\<Alert\> · `404` | none |
| `GET /alerts/{id}` | Fetches one alert | authenticated, owner via vehicle | — | `200` Alert · `404` | none |
| `POST /alerts/{id}/resolve` | Manually dismisses an alert, without a matching event | authenticated, owner via vehicle | — | `200` Alert (`status=dismissed`) · `400` already resolved/dismissed · `404` | none |

> Naming nuance carried over from `ARCH.md`: the endpoint is called
> `/resolve`, but it sets `status=dismissed`, not `resolved`. `resolved` is
> reserved for the automatic case (a matching Event closed it); `dismissed`
> means a human closed it manually. This distinction matters for Issue 5's
> tests.

### summary

| Endpoint | What it does | Who can call | Request | Response | Side effects |
|---|---|---|---|---|---|
| `GET /vehicles/{vehicle_id}/summary` | Returns the dashboard aggregate for one vehicle | authenticated, owner of vehicle | — | `200` Summary · `404` | none |
| `GET /summary` | Returns one Summary per vehicle owned by the caller — the future CarPlay overview | authenticated | — | `200 {vehicles: Summary[]}` | none |

## 3. Implementation issues

Numbering is sequential and is the intended execution order. Every issue
assumes the generic base layers already exist and are already tested —
**do not re-implement or re-test plain CRUD**; only describe what's
specific to the entity.

---

### Issue 1 — Auth: registration, login, current user

**Description**
- `models`: `User(BaseModel, Base)` — email (unique), password_hash, name.
- `schemas`: `UserRequest` (email, password, name), `UserResponse` (never
  includes password_hash), `LoginRequest`, `TokenResponse`.
- `core/security.py`: password hashing/verification (e.g. passlib/bcrypt),
  `create_access_token`, `decode_access_token`, using the existing
  `SECRET_KEY` / `ALGORITHM` / `ACCESS_TOKEN_EXPIRE_MINUTES` settings
  already in `core/config.py`.
- `repositories`: `UserRepository(BaseRepository[User])` + `get_by_email`.
- `services`: a `UserService` handling registration (hash password before
  calling the repository — this is *not* plain `BaseService.create`, since
  the schema field (`password`) and the persisted field (`password_hash`)
  differ) and login (verify credentials, issue a token).
- `api/deps.py`: `get_current_user` dependency — decodes the bearer token,
  loads the user via `UserRepository`, raises 401 if missing/invalid/
  expired/user no longer exists.
- `api/routers/auth.py`: `POST /auth/register`, `POST /auth/login`,
  `GET /auth/me`.

**Acceptance criteria**
- Registering with a new email creates the user and never returns the
  password or its hash.
- Registering with an already-used email fails with 400.
- Logging in with correct credentials returns a JWT that expires per
  `ACCESS_TOKEN_EXPIRE_MINUTES`.
- Logging in with a wrong password or unknown email fails with 401.
- `GET /auth/me` returns the caller's own data for a valid token, and 401
  for a missing, malformed, or expired one.

**Tests**
- Register happy path.
- Register with duplicate email → 400.
- Login happy path → valid token.
- Login with wrong password → 401.
- Login with unknown email → 401.
- `GET /auth/me` with valid token → correct user.
- `GET /auth/me` with missing/invalid/expired token → 401.
- `UserResponse` never serializes `password_hash` (even if accidentally passed
  in).

**Dependencies:** none — first issue.

---

### Issue 2 — Vehicles CRUD + shared pagination infrastructure

**Description**
- **New shared infra** (used by every list endpoint from here on): a
  generic `Page[T]` response schema and a `PaginationParams` (`page`,
  `page_size`) dependency, e.g. in `app/schemas/pagination.py`. Introduced
  here because it's the first entity with a list endpoint — see §4 for why
  this doesn't wait until the cross-cutting issues.
- **New shared dependency**: `get_owned_vehicle` in `api/deps.py` — loads a
  vehicle by id and 404s if it doesn't exist *or* doesn't belong to
  `current_user`. Reused by Issues 3, 4 and 5 for their own
  vehicle-scoping.
- `models`: `Vehicle(BaseModel, Base)` — owner_id (FK → User), brand,
  model, year, license_plate, color, fuel_type, current_mileage.
- `schemas`: `VehicleCreateRequest`, `VehicleUpdateRequest`, `VehicleResponse`.
- `repositories`: `VehicleRepository(BaseRepository[Vehicle])` +
  `list_by_owner(owner_id)`.
- `services`: `VehicleService(BaseService[Vehicle, VehicleCreateRequest,
  VehicleUpdateRequest])` — overrides `create` to set `owner_id` from the caller
  and to check `license_plate` uniqueness *per owner*.
- `api/routers/vehicles.py`: full CRUD, all under `get_current_user`.

**Acceptance criteria**
- A created vehicle's `owner_id` is always the caller, never
  client-supplied.
- `GET /vehicles` only ever returns the caller's own vehicles.
- Creating a second vehicle with a plate the caller already has fails with
  400 (the same plate under a *different* owner is allowed).
- Reading/updating/deleting another user's vehicle → 404.

**Tests**
- Create happy path.
- Create with a plate already registered by the same owner → 400.
- Create with the same plate but a different owner → succeeds.
- List only returns the caller's vehicles (seed vehicles for two users).
- Get/patch/delete on another owner's vehicle → 404.
- Pagination: `page`/`page_size` on `GET /vehicles` behave correctly
  (defaults, second page, `page_size` cap).

> Note: full cascade-delete behavior (deleting a vehicle also removing its
> Events/MaintenanceRules/Alerts) can't be exercised yet — those entities
> don't exist. It's verified in Issue 5, once all of them do.

**Dependencies:** Issue 1 (`get_current_user`).

---

### Issue 3 — Maintenance rules CRUD

**Description**
- `models`: `MaintenanceRule(BaseModel, Base)` — vehicle_id (FK → Vehicle,
  `ondelete="CASCADE"`), maintenance_type, interval_km, interval_months,
  last_done_mileage, last_done_date, active.
- `schemas`: `MaintenanceRuleCreateRequest` with a `model_validator` enforcing at
  least one of `interval_km` / `interval_months`; `MaintenanceRuleUpdateRequest`;
  `MaintenanceRuleResponse`.
- `repositories`: `MaintenanceRuleRepository(BaseRepository[
  MaintenanceRule])` + `list_by_vehicle(vehicle_id, active=None)`.
- `services`: `MaintenanceRuleService(BaseService[MaintenanceRule,
  MaintenanceRuleCreateRequest, MaintenanceRuleUpdateRequest])` — no overrides needed
  beyond what the schema validator already covers.
- `api/routers/maintenance_rules.py`: nested under
  `/vehicles/{vehicle_id}/maintenance-rules` for create/list, top-level
  `/maintenance-rules/{id}` for get/patch/delete, all resolving ownership
  via `get_owned_vehicle` (Issue 2) then checking the rule belongs to that
  vehicle.

**Acceptance criteria**
- Creating a rule with neither `interval_km` nor `interval_months` fails
  with 400.
- A rule can be created with either or both intervals set.
- `active` defaults to `true` and can be toggled via `PATCH`.
- All operations 404 if the vehicle isn't the caller's, or if the rule
  doesn't belong to the caller's vehicle.

**Tests**
- Create with only `interval_km` → succeeds.
- Create with only `interval_months` → succeeds.
- Create with both → succeeds.
- Create with neither → 400.
- Create under a vehicle owned by another user → 404.
- List scoped to one vehicle only; `active` filter works.
- Get/patch/delete a rule belonging to another owner's vehicle → 404.
- Deleting the rule's vehicle cascades and removes the rule (FK check).

**Dependencies:** Issue 2 (`get_owned_vehicle`).

---

### Issue 4 — Events CRUD (manual) + mileage bump

**Description**
- `models`: `Event(BaseModel, Base)` — vehicle_id (FK → Vehicle,
  `ondelete="CASCADE"`), type, source, event_date, mileage, notes, and a
  `details` **JSONB** column (its shape is polymorphic by `type`, per
  `ARCH.md`; this is a single-table design, not two separate tables).
- `schemas`: model `EventCreateRequest` as a Pydantic **discriminated union** on
  `type` — `FuelingEventCreateRequest | MaintenanceEventCreateRequest` via
  `Field(discriminator="type")` — each with its own typed `details`
  sub-model (`FuelingDetails`, `MaintenanceDetails`). `EventResponse` mirrors
  this for output (and is where `MaintenanceDetails.resolved_alert_id`
  shows up once Issue 7 exists). `EventUpdateRequest` stays a plain partial model
  (no type-switching on update).
- `repositories`: `EventRepository(BaseRepository[Event])` +
  `list_by_vehicle(vehicle_id, type=None, date_from=None, date_to=None)`.
- `services`: `EventService(BaseService[Event, EventCreateRequest, EventUpdateRequest])`
  **overrides `create`**, for two reasons: (1) the discriminated union's
  nested `details` sub-model needs to be dumped into a plain dict before
  it can go into the JSONB column — the base class's naive
  `**data.model_dump()` isn't enough on its own; (2) the mileage side
  effect: after creating the Event, if its `mileage` is greater than the
  vehicle's `current_mileage`, update the vehicle via `VehicleRepository`.
  (**Not** included here: alert resolution — that's Issue 7, kept
  separate on purpose.)
- `api/routers/events.py`: `POST`/`GET list` nested under
  `/vehicles/{vehicle_id}/events`, `GET`/`PATCH`/`DELETE` at
  `/events/{id}`, ownership resolved via the vehicle.

**Acceptance criteria**
- `type=fueling` requires `FuelingDetails`; `type=maintenance` requires
  `MaintenanceDetails` — mismatched `details` for the given `type` fails
  with 400/422.
- Creating an event with `mileage` greater than the vehicle's current
  mileage updates the vehicle; a lower or equal mileage does not.
- List filters by `type` and by `event_date` range; results sorted by
  `event_date` desc.
- All operations 404 if the vehicle (or the event's vehicle) isn't the
  caller's.

**Tests**
- Create fueling happy path.
- Create maintenance happy path.
- Create with `type=fueling` but maintenance-shaped `details` → 422.
- Create with mileage below current → event created, vehicle mileage
  unchanged.
- Create with mileage above current → vehicle mileage updated to match.
- Create under another owner's vehicle → 404.
- List filters by `type`.
- List filters by `event_date` range.
- Get/patch/delete an event via another owner's vehicle → 404.

**Dependencies:** Issue 2 (Vehicle + `get_owned_vehicle`).

---

### Issue 5 — Alerts: read, manual dismissal, and vehicle cascade-delete verification

**Description**
- `models`: `Alert(BaseModel, Base)` — vehicle_id (FK → Vehicle,
  `ondelete="CASCADE"`), maintenance_rule_id (FK → MaintenanceRule,
  `ondelete="CASCADE"`), severity, status, message, due_mileage, due_date,
  resolved_by_event_id (nullable FK → Event).
- `schemas`: `AlertResponse` only — there is deliberately no `AlertCreateRequest` /
  `AlertUpdateRequest` exposed to any router (see `ARCH.md`: no direct create
  endpoint).
- `repositories`: `AlertRepository(BaseRepository[Alert])` +
  `list_by_owner(owner_id, status=None)` (joins through Vehicle) and
  `list_by_vehicle(vehicle_id, status=None)`.
- `services`: `AlertService` — a thin service wrapping the repository with
  a `dismiss(alert)` method (open/resolved → dismissed, or 400 if already
  resolved/dismissed). It does **not** expose the generic `create`/
  `update` from `BaseService` through any router; those stay internal,
  for the generation job (Issue 8) and the resolution logic (Issue 7) to
  use directly.
- `api/routers/alerts.py`: `GET /alerts`, `GET
  /vehicles/{vehicle_id}/alerts`, `GET /alerts/{id}`, `POST
  /alerts/{id}/resolve`.

**Acceptance criteria**
- `GET /alerts` only returns alerts belonging to the caller's own
  vehicles, aggregated across all of them.
- Dismissing an already-resolved or already-dismissed alert fails with
  400.
- Dismissing sets `status=dismissed`, never touches `resolved_by_event_id`
  (that field is exclusively for the automatic path, Issue 7).
- Deleting a vehicle removes its Events, MaintenanceRules, and Alerts
  (this is the first issue where all four entities exist, so this is
  where the full cascade gets verified end-to-end).

**Tests**
- Since there's no create endpoint yet, seed Alerts directly via
  `AlertRepository`/`AlertService` in test setup, not via HTTP.
- List across two vehicles owned by the caller → both appear; alerts
  belonging to another user's vehicle do not.
- List scoped to one vehicle only.
- Dismiss an open alert → `status=dismissed`.
- Dismiss an already-dismissed/resolved alert → 400.
- Get/dismiss an alert on another owner's vehicle → 404.
- Delete a vehicle that has Events, MaintenanceRules and Alerts → all of
  them are gone afterward.

**Dependencies:** Issue 3 (MaintenanceRule, FK target), Issue 4 (Event, FK
target for `resolved_by_event_id`).

---

### Issue 6 — Voice-based event logging (regex/rule-based parser, v1)

**Description**
- New module, e.g. `services/voice_parser.py` — a **regex/rule-based**
  parser (explicitly **not** an LLM call) that takes `raw_text` and
  attempts to extract a `FuelingEventCreateRequest` or `MaintenanceEventCreateRequest`.
  Cover a deliberately small, fixed set of phrasing patterns (e.g. "abasteci
  N litros a R$X o litro[, Y km]", "troquei o óleo[ em Y km]") — this is a
  first version meant to handle the common, predictable cases only. Do
  **not** attempt to generalize beyond explicit patterns; anything that
  doesn't match a known pattern is a parse failure, not a best guess.
- `EventService` (Issue 4) gains a `create_from_voice(vehicle_id, raw_text)`
  method: run the parser, and on success call the existing `create()` path
  (reusing the mileage-bump and, once Issue 7 lands, alert-resolution side
  effects) with `source=voice` and `raw_text` stored; on failure, raise a
  domain error the router maps to 422.
- `api/routers/events.py`: adds `POST
  /vehicles/{vehicle_id}/events/voice`.

**Acceptance criteria**
- At least fueling and maintenance each have one supported phrasing
  pattern that reliably parses.
- A successful parse produces an Event indistinguishable in shape from a
  manually-created one, except `source=voice` and `raw_text` populated.
- Text that matches no known pattern returns 422, and creates nothing.
- This issue does not call any external AI/LLM service — see §5 for the
  Gemini fallback, explicitly deferred.

**Tests**
- Parser unit tests: one passing case per supported pattern (fueling,
  maintenance), asserting the exact extracted fields.
- Parser unit tests: text that doesn't match any pattern → parse failure.
- Parser unit tests: a couple of "near-miss" inputs (extra words, slightly
  different number formatting) to define the boundary of what v1 is
  expected to handle — document any that intentionally fail.
- Router/service test: `POST .../events/voice` with a supported phrase →
  201, Event has `source=voice` and `raw_text` set.
- Router/service test: unsupported phrase → 422, no Event persisted.
- Router/service test: voice endpoint on another owner's vehicle → 404.

**Dependencies:** Issue 4 (Event CRUD).

---

### Issue 7 — Alert auto-resolution on matching maintenance events

**Description**
- Extend `EventService.create` (Issue 4) — after the base `create()` and
  the mileage bump, if `type=maintenance`: look up an open Alert for that
  vehicle + `maintenance_type` (via `AlertRepository`); if found, mark it
  `status=resolved` and `resolved_by_event_id=<new event id>`, and update
  the matching `MaintenanceRule`'s `last_done_mileage`/`last_done_date`
  from the event.
- This must compose with the mileage-bump override already added in Issue
  4 and the voice-creation path from Issue 6 (both funnel through the same
  `create()`), not duplicate logic in three places.
- If there's no open Alert for that maintenance_type, this is a no-op —
  logging maintenance proactively (before anything was ever due) doesn't
  error.

**Acceptance criteria**
- Creating a matching maintenance Event while an open Alert exists for
  that vehicle + maintenance_type resolves it and sets
  `resolved_by_event_id`.
- The matching MaintenanceRule's `last_done_mileage`/`last_done_date` gets
  updated from the event that resolved the alert.
- Creating a maintenance Event with no matching open Alert succeeds and
  changes nothing else.
- This resolution path also fires when the Event comes from the voice
  endpoint (Issue 6), not only from manual creation.
- Editing or deleting the resolving Event afterward does not reopen the
  Alert (already covered structurally by `ARCH.md` decision #4 — this
  issue doesn't change that; just don't accidentally add reopening logic).

**Tests**
- Open Alert + matching maintenance Event created → Alert resolved,
  `resolved_by_event_id` set, rule's `last_done_*` updated.
- Open Alert for a *different* maintenance_type on the same vehicle + a
  maintenance Event created → that Alert stays untouched.
- No open Alert + maintenance Event created → succeeds, no Alert touched.
- Fueling Event created (any state of Alerts) → no Alert is ever touched.
- Same resolution behavior via the voice-creation path (Issue 6).

**Dependencies:** Issue 4 (Event CRUD), Issue 5 (Alert model/repository),
Issue 6 (so the voice path is covered too — can be developed in parallel
with 6 and merged after both land, but tested together).

---

### Issue 8 — Periodic alert-generation job

**Description**
- A scheduled/periodic task (e.g. triggered by a script invocable via cron,
  or FastAPI's own background scheduling if already decided elsewhere —
  out of scope here to pick the runner; this issue is about the
  comparison logic itself) that, for every active `MaintenanceRule`,
  compares the vehicle's `current_mileage`/today's date against
  `last_done_mileage` + `interval_km` and `last_done_date` +
  `interval_months`, and creates an `Alert` (via `AlertService`/
  `AlertRepository`, bypassing any router — there is none) when due,
  setting `severity` per how far past due it is.
- Must not create a duplicate open Alert for a rule that already has one
  (idempotent — safe to run repeatedly, e.g. every night).
- Severity thresholds (`info`/`warning`/`critical`) are a fixed, documented
  rule for v1 (e.g. `info` within N km/days of due, `warning` at due,
  `critical` M km/days past due) — not configurable per rule yet.

**Acceptance criteria**
- Running the job against a rule that's due (by km or by date) creates
  exactly one Alert with the correct `due_mileage`/`due_date`.
- Running it again immediately after does not create a second Alert for
  the same rule while one is still open.
- A rule that's inactive (`active=false`) never generates an Alert.
- A rule that isn't due yet generates nothing.
- Severity escalates correctly as the vehicle gets further past due.

**Tests**
- Rule due by km → Alert created with expected fields.
- Rule due by date → Alert created with expected fields.
- Rule not due → no Alert.
- Inactive rule, otherwise due → no Alert.
- Running the job twice in a row → still exactly one open Alert.
- Severity boundaries: just approaching / exactly due / past due by
  varying margins → correct `severity` for each.

**Dependencies:** Issue 3 (MaintenanceRule), Issue 5 (Alert).

---

### Issue 9 — Vehicle & global summary (dashboard)

**Description**
- New read-only aggregation, not a persisted entity — no repository/service
  pair extending the generic base classes (there's no `Summary` table).
  A `SummaryService` (or a couple of focused query functions) computes:
  last fueling Event, last maintenance Event, open Alerts, average
  consumption (km/liter, from fueling history), and total spend (fueling +
  maintenance costs) for the last 30 days and last 12 months.
- `schemas`: `SummaryResponse`.
- `api/routers/summary.py`: `GET /vehicles/{vehicle_id}/summary`, `GET
  /summary` (one `SummaryResponse` per vehicle owned by the caller).

**Acceptance criteria**
- `avg_consumption_km_per_liter` is computed correctly from at least two
  fuelings with `full_tank=true` (define and document the exact formula
  used, e.g. distance between two full-tank fuelings ÷ liters used since
  the first).
- Spend totals correctly sum both fueling and maintenance costs within
  each window.
- A vehicle with no events yet returns a valid Summary with `null`/zero
  aggregates, not an error.
- `GET /summary` only includes the caller's own vehicles.

**Tests**
- Summary for a vehicle with a realistic mix of fueling/maintenance events
  → correct last-event references, correct consumption, correct spend
  totals.
- Summary for a brand-new vehicle with no events → no error, empty/zero
  aggregates.
- Summary includes only currently-open Alerts.
- `GET /summary` for a user with multiple vehicles → one entry per
  vehicle, none from other users.
- `GET /vehicles/{id}/summary` on another owner's vehicle → 404.

**Dependencies:** Issue 4 (Event), Issue 5 (Alert). Functionally
independent of Issues 6–8 (it reads whatever exists, regardless of how it
was created), but richer to demo once they're in.

---

### Issue 10 — Global error handling

**Description**
- Centralize the domain-level exceptions that have accumulated across
  Issues 1–9 (not-found, validation, duplicate, etc.) into a small
  exception hierarchy (e.g. in `core/exceptions.py`) and a single set of
  FastAPI exception handlers registered on the app, instead of each router
  raising `HTTPException` ad hoc. Response shape stays exactly what
  `ARCH.md` §2 already specifies (`{"detail": ...}`) — this issue is about
  *where* that gets decided, not changing the contract.

**Acceptance criteria**
- Every error response already covered by Issues 1–9's tests still returns
  the same status code and body shape after this refactor (no behavior
  change, purely structural).
- Adding a new domain exception type doesn't require touching every
  router that might raise it.

**Tests**
- Re-run (not rewrite) the existing error-path tests from Issues 1–9 to
  confirm no regression.
- One new test per exception type added to the hierarchy, if any weren't
  already covered by an existing issue.

**Dependencies:** Issues 1–9 (there must be existing error paths to
consolidate).

---

### Issue 11 — OpenAPI documentation polish

**Description**
- Tag descriptions, summary/description text, and response examples for
  every router group (auth, vehicles, events, maintenance-rules, alerts,
  summary) in the generated OpenAPI schema, plus documenting the bearer
  auth scheme so `/docs` is usable by someone who isn't already reading
  `ARCH.md`.

**Acceptance criteria**
- `/docs` and `/openapi.json` render without errors and every endpoint has
  a human-readable summary.
- The security scheme is documented so `/docs`'s "Authorize" flow works
  against a real token obtained from `/auth/login`.

**Tests**
- None beyond confirming `/openapi.json` is valid (this issue is
  documentation, not behavior — no new business-logic tests apply).

**Dependencies:** Issues 1–9 (documents what already exists).

---

## 4. Ordering rationale

- **Auth first** (Issue 1): every other issue's tests need an authenticated
  caller, so nothing else can be meaningfully tested before this exists.
- **Vehicle before anything vehicle-scoped** (Issue 2): Events,
  MaintenanceRules and Alerts all key off `vehicle_id` and reuse the
  ownership-check dependency introduced here.
- **MaintenanceRule before Event and Alert** (Issue 3): Alerts FK to
  MaintenanceRule, and the mental model ("a rule defines when maintenance
  is due") reads more naturally before "an event can satisfy a rule."
- **Event before Alert** (Issue 4 before 5): Alert's
  `resolved_by_event_id` FKs to Event.
- **One exception to "CRUD before cross-cutting infra"**: pagination.
  The instructions group pagination with global error handling and
  OpenAPI docs as "do after CRUD," but `ARCH.md`'s own convention requires
  *every* list endpoint — starting with `GET /vehicles` in Issue 2 — to
  return the paginated `Page<T>` shape. Deferring it to Issue 10/11 would
  make Issue 2 impossible to build to spec. Resolution: the generic
  `Page[T]` schema and pagination dependency are introduced inside Issue
  2 (the first issue that needs them) since they're a few lines of shared
  infrastructure, not a business rule — while the two other cross-cutting
  items named in the instructions (global error handling, OpenAPI polish)
  stay deferred to Issues 10–11, since FastAPI's default `HTTPException`
  already satisfies the contract's error shape without any custom
  plumbing, so nothing blocks on them earlier.
- **Business rules after CRUD** (Issues 6–8): voice parsing, alert
  auto-resolution, and the alert-generation job all build on CRUD
  endpoints/entities that need to exist and be correct first. Issue 7
  (auto-resolution) is ordered after Issue 6 (voice) because it must also
  cover the voice-creation path, not just manual creation — though the two
  could be developed in parallel and merged together.
- **Summary near the end** (Issue 9): it's read-only and technically only
  needs Issues 2/4/5, but is far more meaningful to build and demo once
  there's real event/alert history to summarize.
- **Error handling and OpenAPI polish last** (Issues 10–11): both are
  refactors/documentation over behavior that already exists and is already
  tested; doing them earlier would mean repeatedly retrofitting new
  exception types and endpoint docs as each new entity landed.

## 5. Future backlog (out of scope for this phase)

Not broken into technical issues yet — listed here only so they're not
forgotten, and explicitly **not** part of Issues 1–11 above:

- **Voice parsing fallback via Gemini** — when the regex/rule-based parser
  (Issue 6) can't confidently parse `raw_text`, fall back to a Gemini call
  instead of failing with 422.
- **Natural-language insights over history** — a Gemini-generated summary
  of a vehicle's history in plain language (e.g. "your consumption dropped
  10% this month").
- **Natural-language questions over history** — translating a free-text
  question about a vehicle's history into a structured query via Gemini,
  rather than the user navigating filters manually.
- **Receipt/invoice OCR** — multimodal Gemini extraction of fueling/
  maintenance receipts into Event data. Planned for **Phase 3**, alongside
  OBD-II integration.

All four items depend on an isolated AI client module (e.g. `core/ai/` or
`services/ai/`) that **does not exist yet and is not created in this
phase** — none of Issues 1–11 above introduce any Gemini/LLM dependency,
by design.
