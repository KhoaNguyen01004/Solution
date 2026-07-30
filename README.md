# Fleet Fuel Management

Flask-based fleet management with GPS tracking, fuel monitoring, and a 3D/2D **Truck Load Planner** featuring a multi-vehicle bin-packing algorithm, door-aware access validation, and step-by-step placement animation.

## Pages

- **Map** (`/`) — GPS trip tracking with geofencing (Ray Casting)
- **Fuel Efficiency** (`/fuel-efficiency`) — Dashboard with KPIs, chart, refuel log
- **Container Fuel** (`/fuel-container`) — Container-vehicle dashboard with partial-tank support
- **Truck Load Planner** (`/truck-load-planner`) — 3D/2D cargo loader with auto-arrange, stacking, step animation
- **Vehicle Management** (`/vehicle-management`) — Vehicle CRUD and interactive 3D container diagram (Three.js)
- **Oil Change** (`/oil-change`) — Oil change tracking
- **Delivery Management** — Delivery plan oriented trip management with Excel import pipeline (`/delivery/new`), and an operational **Dispatch Dashboard** (`/delivery/dashboard`) with stop-level execution tracking, road-aware ETA/distance, attention indicators (stuck/GPS-stale), a pinned current-stop card with click-to-call, inline skip/cancel reason editing, a read-only photo gallery, and follow-vehicle map mode

---

## Running Tests

### Delivery Management Tests (49 tests)
```bash
python -m pytest tests/test_delivery.py -v
```

### Truck Load Planner Tests (31 tests)

```bash
python -m pytest tests/test_scorer.py tests/test_auto_arrange_e2e.py -v
```

`test_scorer.py` (26) covers scoring/candidate-generation units; `test_auto_arrange_e2e.py`
(5) runs realistic-sized shipments through the real production entry points and asserts
on utilization, stacking behavior, the stack-depth cap, and multi-vehicle truck-count
minimization — see `docs/TRUCK_LOAD_PLANNER.md` for the algorithm these exercise.

### TLP Benchmarks, Diagnostics & Manual Debugging (non-pytest)

```bash
# ── Benchmarks ─────────────────────────────────────────────
python tests/test_all.py benchmark --mode distribution   # Single distribution run (46 pkgs, 32 vehicles)
python tests/test_all.py benchmark --mode floor_contact  # Compare floor_contact weight 25 vs 5 (60 trials)
python tests/test_all.py benchmark --mode real_data      # End-to-end with real DB data

# ── Diagnostics ────────────────────────────────────────────
python tests/test_all.py diagnose --scenario general     # KBF 280R + 3x LC 900 placement debug
python tests/test_all.py diagnose --scenario kbf_lc900   # Same scenario, focused output
python tests/test_all.py diagnose --scenario candidates  # Candidate generation & scoring breakdown
python tests/test_all.py diagnose --scenario stacking    # Floor vs stack decision analysis (15 pkgs)
python tests/test_all.py diagnose --scenario stacking --full  # Detailed breakdown

# ── Debug ──────────────────────────────────────────────────
python tests/test_all.py debug --mode py3dbp      # Run py3dbp engine on first vehicle
python tests/test_all.py debug --mode stats       # Statistics from py3dbp engine
python tests/test_all.py debug --mode validation  # Validate first package through pipeline
python tests/test_all.py debug --mode vehicles    # List all vehicles with dimensions

# ── Database Queries ───────────────────────────────────────
python tests/test_all.py query --mode vehicles   # Vehicles sorted by capacity
python tests/test_all.py query --mode tables     # Row counts per table
python tests/test_all.py query --mode db         # Full database overview
python tests/test_all.py query --mode shipments  # Shipments with package details

# ── Instrumentation ────────────────────────────────────────
python tests/test_all.py instrument --mode trace      # Read instrument_trace.jsonl
python tests/test_all.py instrument --mode bug-trace  # Support integrity trace (10 pkgs)

# ── Standalone Debugger ────────────────────────────────────
python tests/debug_arrange.py kbf_lc900          # Auto-arrange debug per scenario
python tests/debug_arrange.py real --full        # Full 46-pkg real shipment debug

# ── Manual Test (full pipeline) ────────────────────────────
python manual_test.py                            # Internal engine (default)
python manual_test.py --engine py3dbp            # py3dbp engine (experimental, not wired into the web app)
python manual_test.py --compare                  # Side-by-side comparison
```

Note: `test_all.py` matches pytest's `test_*.py` discovery but contains no `test_*`
functions (everything is `cmd_*`/argparse-CLI-only) — running it via the commands above
is the only way any of this logic executes; `pytest` collects the file but asserts
nothing from it.

---

## Truck Load Planner — Algorithm, API & Frontend Reference

See **`docs/TRUCK_LOAD_PLANNER.md`** for the full reference: package sort order,
multi-vehicle distribution/vehicle-selection, single-vehicle placement strategies,
scoring, stacking rules, door access, clearance handling, the engine module map, the
`py3dbp` experimental engine, database schema, the auto-arrange API, and frontend
(step animation, 3D controls, 2D canvas coordinates, validation panel) details.

---

## Project Structure

```
app.py                          # Entry point: create_app() + remaining core routes; `python app.py` runs the dev server
wsgi.py                         # Gunicorn entry point (`gunicorn wsgi:app`) — see note below
main.py                         # Standalone TTAS GPS tracking tool
manual_test.py                  # Manual pipeline test with instrumentation
app/                            # Flask application package (see app/__init__.py's create_app())
  __init__.py                   # App factory: config, init_db(), blueprint registration
  config.py                     # Env vars, constants
  state.py                      # Shared mutable runtime state (route cache, locks, TTAS session)
  db.py                         # DatabaseManager — context-manager SQLite connections, PRAGMA foreign_keys=ON
  database/
    schema.py                   # CREATE TABLE statements
    migrations.py               # Column migrations, data backfill
  utils/
    geo.py                      # Distance/polygon/centroid helpers
    export.py                   # Shared CSV-response helper
  services/
    ttas_client.py               # TTAS session, live vehicle fetch, report scraping
    routing.py                   # OpenRouteService routing helpers
    locations.py                 # Manual-location file I/O
  routes/                       # Flask Blueprints
    fleet.py                     # Vehicle CRUD
    fuel.py                      # Fuel log CRUD, profiles, CSV export, Google Sheet sync
    oil.py                       # Oil maintenance CRUD, TTAS KM-log scraping
    trips.py                     # Trip management, background route-refresh loop
tests/                          # All test, debug, and diagnostic files
  test_all.py                   # Unified test harness (16 subcommands)
  test_scorer.py                # Pytest unit tests (TLP scoring — 26 tests)
  test_auto_arrange_e2e.py      # Pytest end-to-end TLP tests (5 tests)
  test_delivery.py              # Pytest unit tests (delivery management — 49 tests)
  debug_arrange.py              # Per-package auto-arrange debugger
  merge_duplicate_vehicles.py   # One-time DB dedup utility
reports/                        # Test and debug output files
docs/                           # CHANGELOG, CODEBASE_ANALYSIS_REPORT, DELIVERY_MODULE,
                                 # TRUCK_LOAD_PLANNER reference docs
services/                       # Application services (not to be confused with app/services/ above)
  delivery/                     # Delivery plan management
    database.py                 # Schema DDL, table initialization
    plan_service.py             # Plans, assignments, stops CRUD + Excel import pipeline
    execution_service.py        # Current stop derivation, advance, skip, cancel, reorder
    tracking_service.py         # TTAS GPS wrapper, vehicle lookup
    eta_service.py              # ORS-based ETA calculation (Haversine fallback)
    image_service.py            # Stop image upload, serve, delete
    routes.py                   # Flask Blueprint (24 endpoints under /api)
scripts/
  migrate_to_delivery.py        # Idempotent migration from legacy vehicle_trips
truck_load_planner/             # Core application package
  routes.py                     # Flask routes / API endpoints
  session.py                    # Load planning session
  db.py                         # Database initialization
  engine/                       # Packing algorithms (17 modules)
  engines/                      # Packing engine abstraction (internal + py3dbp)
  models/                       # Data models
  logistics/                    # Legacy validation helpers — adapters.py delegates check_boundary/
                                 # calculate_total_weight/check_weight to engine/; volume.py and
                                 # constraints.py::get_door_status have no engine equivalent and
                                 # remain self-contained
static/                         # Frontend assets (JS, CSS)
  js/utils.js                   # ApiClient (fetch wrapper) + UI (toast, escapeHtml) namespace, shared by all pages
templates/                      # HTML templates
```

**Why both `app.py` and `wsgi.py`?** `app.py` (file) and `app/` (package) share the name `app`, and Python's import system always resolves `import app` to the package over the file. Gunicorn's `app:app` target therefore can't reach `app.py`'s Flask instance — `wsgi.py` gives it an unambiguous one (`gunicorn wsgi:app`, see `render.yaml`). `python app.py` for local dev is unaffected — running a script directly doesn't register it under the package's name.

## Tech Stack

- **Backend**: Python, Flask, SQLite3
- **Frontend**: Vanilla JS (`ApiClient`/`UI` shared namespace in `static/js/utils.js`), Chart.js 4.4.7, Konva.js 9 (canvas), Three.js (3D)
- **No ORM** — raw SQL for full control, via `DatabaseManager` (`app/db.py`) context-managed connections
