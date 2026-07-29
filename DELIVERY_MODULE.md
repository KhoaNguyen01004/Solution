# Delivery Module — Documentation

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   Flask Application                      │
│  ┌───────────────────────────────────────────────────┐  │
│  │                   app.py                           │  │
│  │  Routes: /, /delivery/*, /api/*, /manage-trips     │  │
│  │  Blueprints: tlp_bp, delivery_bp                   │  │
│  └──────────┬────────────────────────────────────────┘  │
│             │                                            │
│  ┌──────────▼────────────────────────────────────────┐  │
│  │           delivery Blueprint (routes.py)           │  │
│  │  Prefix: /api                                      │  │
│  │  Endpoints: /plans, /assignments, /stops, /exec,   │  │
│  │             /eta, /drivers, /images                │  │
│  └──────────┬────────────────────────────────────────┘  │
│             │                                            │
│  ┌──────────▼────────────────────────────────────────┐  │
│  │              Service Layer                          │  │
│  │  ┌────────────┐ ┌──────────────┐ ┌─────────────┐  │  │
│  │  │plan_service│ │execution_svc │ │  eta_svc    │  │  │
│  │  │  CRUD ops  │ │adv/skip/cancel│ │  ORS calc   │  │  │
│  │  └────────────┘ └──────────────┘ └─────────────┘  │  │
│  │  ┌────────────┐ ┌──────────────┐ ┌─────────────┐  │  │
│  │  │image_svc   │ │tracking_svc  │ │ database.py │  │  │
│  │  │file upload │ │ GPS normalize│ │  table init │  │  │
│  │  └────────────┘ └──────────────┘ └─────────────┘  │  │
│  └────────────────────────────────────────────────────┘  │
│             │                                            │
│  ┌──────────▼────────────────────────────────────────┐  │
│  │              SQLite Database                       │  │
│  │  routing_system.db (delivery_* tables + legacy)    │  │
│  └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
         ▲                          ▲
         │ HTML templates           │ Static assets
         ▼                          ▼
┌────────────────────┐  ┌───────────────────────────┐
│   Jinja2 Templates │  │  JS / CSS / Images        │
│  delivery-*.html    │  │  dashboard/* (modular)    │
│  manage-trips.html  │  │  delivery-plan-builder.js │
└────────────────────┘  └───────────────────────────┘
```

---

## Frontend Structure

```
templates/
├── delivery-plan-builder.html     Plan creation / editing wizard
└── delivery-dashboard.html        Operational dispatch dashboard

static/css/
├── delivery-plan-builder.css      Wizard styles, modals, responsive
└── delivery-dashboard.css         3-panel layout, vehicle cards, timeline

static/js/
├── delivery-plan-builder.js       Single-file wizard (state machine, 5 steps)
└── dashboard/
    ├── main.js                    Orchestrator, state, filters, init
    ├── api.js                     All API calls
    ├── polling.js                 12-second poll cycle
    ├── vehicle-list.js            Left panel rendering
    ├── map.js                     Leaflet map, markers, routes
    └── timeline.js                Right panel, stop list, actions
```

### Plan Builder Flow

| Step | Panel | Key Actions |
|------|-------|-------------|
| 1 | Plan Info | Enter name, date, description |
| 2 | Vehicles | Add/edit/duplicate/remove assignments |
| 3 | Stops | Add/edit/delete/reorder (drag) stops per assignment |
| 4 | Review | Validate, save draft, or confirm |
| 5 | Success | View plan ID, open/edit, create another |

All steps share a single state object. Auto-save runs every 30s when dirty.

### Dashboard Panels

| Panel | Content | Update |
|-------|---------|--------|
| Left (320px) | Vehicle cards with progress, status, GPS time | Every 12s poll |
| Center (flex) | Leaflet map with vehicle markers + stop pins | On selection + poll |
| Right (360px) | Stop timeline with action buttons | On selection only |

---

## Database Schema

### `delivery_plans`

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| plan_name | TEXT | Required |
| plan_date | TEXT | ISO date |
| description | TEXT | Optional |
| status | TEXT | `draft` → `confirmed` → `executing` → `completed`/`cancelled` |
| created_by | TEXT | Dispatcher name |
| created_at | TIMESTAMP | Auto |
| updated_at | TIMESTAMP | Auto |
| imported_at | TIMESTAMP | Set on Excel import |

### `vehicle_assignments`

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| plan_id | INTEGER FK → delivery_plans | Cascade delete |
| vehicle_id | INTEGER → vehicles | From master vehicle table |
| driver_id | INTEGER → drivers | FK to drivers |
| sequence | INTEGER | Order within plan |
| notes | TEXT | Optional |
| created_at | TIMESTAMP | Auto |
| updated_at | TIMESTAMP | Auto |

### `delivery_plan_stops`

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| vehicle_assignment_id | INTEGER FK → vehicle_assignments | Cascade delete |
| planned_sequence | INTEGER | Original planned order |
| station_code | TEXT | Client-defined code |
| station_name | TEXT | Required |
| address | TEXT | |
| lat | REAL | Latitude |
| lng | REAL | Longitude |
| manager_name | TEXT | |
| manager_phone | TEXT | |
| product_description | TEXT | |
| note | TEXT | |
| created_at | TIMESTAMP | Auto |
| updated_at | TIMESTAMP | Auto |

### `stop_executions`

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| stop_id | INTEGER FK → delivery_plan_stops | Unique, cascade delete |
| execution_sequence | INTEGER | 1-based during execution |
| status | TEXT | `planned` → `enroute` → `arrived` → `completed` (or `skipped`/`cancelled`) |
| skip_reason | TEXT | |
| cancel_reason | TEXT | |
| actual_arrival_at | TIMESTAMP | |
| actual_departure_at | TIMESTAMP | |
| completed_at | TIMESTAMP | |
| created_at | TIMESTAMP | Auto |
| updated_at | TIMESTAMP | Auto |

### `drivers`

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | |
| name | TEXT | |
| phone | TEXT | |
| license_number | TEXT | |

### `delivery_stop_images`

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | |
| stop_id | INTEGER FK → delivery_plan_stops | |
| relative_path | TEXT | File path |
| category | TEXT | `arrival`, `delivery`, `damage`, `departure`, `extra` |
| gps_lat | REAL | |
| gps_lng | REAL | |
| captured_at | TIMESTAMP | |
| uploaded_by | TEXT | |

### Status Lifecycle

```
planned ──► enroute ──► arrived ──► completed
  │                        │
  ├──► skipped              └──► cancelled
  └──► cancelled
```

---

## API Endpoints

### Plans

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/plans` | List plans (filter: `?status=`) | None |
| POST | `/api/plans` | Create plan | None |
| GET | `/api/plans/<id>` | Get plan + assignments + stops | None |
| PUT | `/api/plans/<id>` | Update plan fields | None |
| DELETE | `/api/plans/<id>` | Delete plan (cascades) | None |
| POST | `/api/plans/<id>/confirm` | Set status → confirmed | None |

### Assignments

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/assignments` | List (`?plan_id=`) |
| POST | `/api/assignments` | Create (`plan_id`, `vehicle_id`, `driver_id`, `sequence`, `notes`) |
| GET | `/api/assignments/<id>` | Get single |
| PUT | `/api/assignments/<id>` | Update |
| DELETE | `/api/assignments/<id>` | Delete (cascades stops) |

### Stops

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stops?assignment_id=X` | List stops with execution status |
| POST | `/api/stops` | Create stop + execution record |
| GET | `/api/stops/<id>` | Get stop with images |
| PUT | `/api/stops/<id>` | Update stop fields |
| DELETE | `/api/stops/<id>` | Delete stop + execution |
| POST | `/api/stops/<id>/skip` | Mark skipped |
| POST | `/api/stops/<id>/cancel` | Mark cancelled |
| POST | `/api/stops/reorder` | Reorder stops (`assignment_id`, `stop_ids[]`) |
| POST | `/api/stops/insert` | Insert temp stop between existing stops |

### Execution

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/execution/current?assignment_id=X` | Current active stop |
| POST | `/api/execution/advance` | Advance stop (`planned→arrived→completed`) |
| GET | `/api/execution/dashboard` | All assignments + GPS + progress |
| GET | `/api/execution/progress?assignment_id=X` | Progress stats per assignment |

### ETA

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/eta?assignment_id=X` | ETAs for remaining stops via ORS |

### Drivers

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/drivers` | List all |
| POST | `/api/drivers` | Create |

### Images

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stops/<id>/images` | List images for stop |
| POST | `/api/stops/<id>/images` | Upload image |
| GET | `/api/images/<id>/file` | Serve image file |
| DELETE | `/api/images/<id>` | Delete image |

### Legacy (in app.py)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/fleet/vehicles` | List all vehicles (`?q=`) |
| GET | `/api/vehicles` | Live vehicle data from TTAS |

---

## Service Responsibilities

| Service | File | Responsibility |
|---------|------|----------------|
| `plan_service` | `plan_service.py` | CRUD for plans, assignments, stops. Excel parse/validate. |
| `execution_service` | `execution_service.py` | Stop progression (advance/skip/cancel), reordering, dashboard data, progress calculation. |
| `eta_service` | `eta_service.py` | ETA calculation using OpenRouteService API. |
| `image_service` | `image_service.py` | Image upload/serve/delete for delivery stops. |
| `tracking_service` | `tracking_service.py` | Normalize GPS positions from TTAS. |
| `database` | `database.py` | Create delivery tables (idempotent migrations). |

---

## Key Design Decisions

1. **Plan tables are immutable after import** — Once confirmed, the plan structure cannot be changed. Execution changes happen through the execution layer (advance/skip/cancel).

2. **Current stop is derived** — No `is_current` column. The current stop is the first stop with status `planned`, `enroute`, or `arrived` (ordered by execution_sequence).

3. **`stop_executions` has no `vehicle_assignment_id`** — The link is through `delivery_plan_stops.vehicle_assignment_id`. This avoids duplication.

4. **Excel import pipeline** — The `confirm_import` function in `plan_service.py` handles the Excel flow by parsing, validating, previewing, and persisting in one transaction per vehicle group.

5. **Dashboard polls every 12s** — The dashboard endpoint returns all data in one call (`/api/execution/dashboard`). Detailed data (stops, ETA) is fetched per-selection only.

---

## Configuration

All configuration is via `.env` file:

```
# Required
ORS_API_KEY=           OpenRouteService API key
ORS_BASE_URL=          ORS API base URL

# TTAS tracking (vehicle GPS)
TTAS_LOGIN_URL=        TTAS login page
TTAS_TRACKING_PAGE_URL=TTAS tracking page
TTAS_TRACKING_API=     TTAS realtime tracking endpoint
TTAS_USERNAME=         TTAS login username
TTAS_PASSWORD=         TTAS login password

# Optional
DB_PATH=               SQLite database path (default: routing_system.db)
FLASK_HOST=            Server host (default: 0.0.0.0)
FLASK_PORT=            Server port (default: 5000)
FLASK_DEBUG=           Debug mode (default: true)
DEFAULT_RADIUS_KM=     Geofence radius (default: 3)
ROUTE_REFRESH_INTERVAL=Route cache refresh seconds (default: 60)
```

---

## Testing

### Running Tests

```bash
# All tests (31 delivery + 26 TLP)
pytest tests/

# Delivery-specific
pytest tests/test_delivery.py -v

# Single test class
pytest tests/test_delivery.py::TestStopProgression -v

# With coverage
pytest tests/test_delivery.py --cov=services/delivery --cov-report=term
```

### Test Coverage

| Test Class | Tests | Coverage |
|-----------|-------|----------|
| TestEtaService | 7 | ETA calculation, ORS fallback |
| TestStopProgression | 7 | Advance, skip, cancel, current stop |
| TestStopReordering | 4 | Reorder, insert temp stop, sequence update |
| TestImageService | 5 | Upload, list, delete, edge cases |
| TestProgress | 4 | Progress calculation, breakdown |
| TestTransactions | 2 | Rollback on failure, cascade delete |

### Manual Test Checklist

- [ ] Create plan with 2+ assignments, 3+ stops each
- [ ] Edit draft plan — verify all stops load correctly
- [ ] Confirm plan — verify status changes to `confirmed`
- [ ] Open dashboard — verify vehicle appears
- [ ] Select vehicle — verify map shows stops + route
- [ ] Advance stop — verify timeline updates
- [ ] Skip stop — verify status becomes `skipped`
- [ ] Cancel stop — verify status becomes `cancelled`
- [ ] Verify execution persists after page refresh
- [ ] Add duplicate assignment — verify stops copy correctly
- [ ] Reorder stops via drag-and-drop
- [ ] Use station search — verify auto-fill
- [ ] Use map picker — verify lat/lng populated
- [ ] Test responsive layout at 768px width
- [ ] Test filters (plan, date, vehicle, driver, status)

---

## Deployment

### Requirements

- Python 3.10+
- Flask 3.x
- SQLite 3
- OpenRouteService API key
- TTAS tracking credentials

### Install

```bash
pip install -r requirements.txt
```

### Run

```bash
# Development
python app.py

# Production (Gunicorn)
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Environment

Create `.env` from `.env.example` with all required keys.

---

## Known Limitations

1. **ETA requires live GPS** — If TTAS is unreachable, ETA shows "Vehicle GPS not available". The dashboard gracefully handles this.
2. **Single SQLite database** — No connection pooling. Not suitable for high-concurrency production use without a pooler.
3. **No real-time push** — The dashboard uses polling (12s interval). For sub-second updates, WebSocket or SSE would be needed.
4. **N+1 in get_plan** — Loading a plan with N assignments issues N+1 queries (1 for plan, 1 for assignments list, N for each assignment's stops). Acceptable for typical plan sizes (< 20 assignments).
5. **Page refresh loses unsaved auto-save timer** — The `beforeunload` handler warns users, but a crash during auto-save could lose the current save operation.
6. **TTAS session expires** — The fleet session cookie expires periodically. The app retries with a fresh session on failure.
