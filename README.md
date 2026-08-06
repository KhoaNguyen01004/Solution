# Fleet Fuel Management

Flask-based fleet management with GPS tracking, fuel monitoring, and a 3D/2D **Truck Load Planner** featuring a multi-vehicle bin-packing algorithm, door-aware access validation, and step-by-step placement animation.

## Pages

- **Map** (`/`) — GPS trip tracking with geofencing (Ray Casting)
- **Fuel Efficiency** (`/fuel-efficiency`) — Dashboard with KPIs, chart, refuel log
- **Container Fuel** (`/fuel-container`) — Container-vehicle dashboard with partial-tank support
- **Truck Load Planner** (`/truck-load-planner`) — 3D/2D cargo loader with auto-arrange, stacking, step animation
- **Vehicle Management** (`/vehicle-management`) — Vehicle CRUD and interactive 3D container diagram (Three.js)
- **Oil Change** (`/oil-change`) — Oil change tracking
- **Delivery Management** — Delivery plan oriented trip management with Excel import pipeline (`/delivery/new`), per-assignment driver naming that overrides the vehicle's usual driver for that plan, and an operational **Dispatch Dashboard** (`/delivery/dashboard`) with stop-level execution tracking, road-aware ETA/distance, attention indicators (stuck/GPS-stale/reported-stopped), a **No GPS** quick filter covering both unmatched plates and TTAS lost-signal (`MTH`) vehicles, a pinned current-stop card with click-to-call, inline skip/cancel reason editing, per-stop phase history with undo, single-shot and batch photo upload, a read-only photo gallery, follow-vehicle map mode, live stop reordering, click-a-stop-to-locate-it, and a switchable basemap (satellite / streets / muted) with Esri imagery capture dates
- **Delivery Plan Editor** (`/delivery/edit/<plan_id>`) — Reopens a saved plan in the builder. Confirmed plans are editable, not read-only; plan names in the dashboard's Plans panel link straight here
- **End-of-Day Export** (`/delivery/export`) — Per-day delivery summary, day-level image attachments, and a packaged `day.zip` download

> **No authentication.** Every endpoint, including the destructive ones, is open to anyone who can reach the host — a deliberate 2026-07-31 decision for an internal-network deployment. See `docs/DELIVERY_MODULE.md` § Key Design Decisions before exposing this publicly.

---

## Running Tests

### Delivery Management Tests (358 tests)
```bash
python -m pytest tests/test_delivery.py -v         # 223 — service layer
python -m pytest tests/test_delivery_routes.py -v  # 135 — route layer, real HTTP with TTAS mocked
```

`test_delivery.py` imports the service modules directly; `test_delivery_routes.py` drives
`app.test_client()` end to end, which is the only suite that sees bugs living inside a
request handler or in an assembled response. Run both for any delivery change.

`pytest tests/` runs everything — **548 tests**.

> **`test_delivery_routes.py` needs `playwright` importable** even though it never drives a
> browser: it imports the app through `main.py`, which imports `playwright` at module
> level. Without it all 135 tests error out with `ModuleNotFoundError: No module named
> 'playwright'` rather than failing on anything real. It **is** pinned in
> `requirements.txt` (`playwright==1.61.0`), so this means your environment is behind —
> `pip install -r requirements.txt` fixes it. The browser binaries
> (`playwright install`) are not needed. Note `requirements.txt` is UTF-16, so
> `grep playwright requirements.txt` finds nothing and will tell you the opposite.

### Route-layer Tests (57 tests)

```bash
python -m pytest tests/test_write_handler_connections.py -v  # 36 — write handlers, all four route modules
python -m pytest tests/test_tlp_routes.py -v                 # 8  — truck load planner
python -m pytest tests/test_trips_geofence.py -v             # 7  — background route refresher
python -m pytest tests/test_fuel_routes.py -v                # 6  — fuel log
python -m pytest tests/test_fleet_routes.py -v               # 11 — fleet CRUD
```

Added 2026-08-06 (see `docs/AUDIT_2026-08-06.md`), except `test_fleet_routes.py`. Before
them the truck load planner, `app/routes/trips.py` and `app/routes/fuel.py` had **no**
coverage that issued a request — and the audit's two Critical findings both lived inside
a request handler, where a service-level suite is structurally blind. `test_tlp_routes.py`
and `test_trips_geofence.py` each fail against the pre-fix code, which is the property
that makes them worth keeping.

`test_write_handler_connections.py` is parametrised over all 18 reachable write endpoints:
it swaps `sqlite3.connect` for a wrapper whose `cursor()` raises, forcing an exception at
exactly the point each handler's `finally` exists to cover.

### Frontend Tests (137 drives, non-pytest)

```bash
npm install jsdom                    # once, at the repo root; dev-only, not vendored
node tests/js/dashboard.test.js      # 122 — dispatch dashboard      (needs jsdom)
node tests/js/plan-builder.test.js   # 10  — delivery plan builder   (needs jsdom)
node tests/js/tlp-escaping.test.js   # 5   — truck load planner escaping (no deps)
# jsdom installed elsewhere? NODE_PATH=/path/to/node_modules node tests/js/dashboard.test.js
```

`node_modules/` is gitignored. Node resolves it by walking up from the test file, so a
single `npm install jsdom` at the repo root is enough — no `NODE_PATH` needed.

`tlp-escaping.test.js` is deliberately dependency-free so it runs in a checkout with no
`node_modules` at all. It guards `truck-load-planner.js` against losing its HTML escaping
again (it had none until 2026-08-06), and that is the kind of regression that recurs years
later — a test that needs setup is a test that stops being run.

Frontend changes get no pytest coverage at all, so these are the only real verification
those pages get. Both drive the actual `static/js/` modules against the actual template
(loaded from disk with its `<script>` tags stripped), with only the parts that reach
outside the page stubbed — the API and the Leaflet map for the dashboard, `fetch` for the
builder. An element id renamed in a template but not in the JS fails here.

`plan-builder.test.js` additionally records every stubbed request, so a test can assert on
the exact payload the server would have received. That is how it catches the class of bug
where a field is captured and rendered correctly and then simply left out of the POST.

Run the matching suite for any change under `static/js/`, alongside `node --check` on the
touched files.

**One dashboard ETA case is time-of-day dependent** — `a route running past midnight is
marked, not shown as already late` feeds `UI.etaClock()` a 36-hour ETA and asserts the
result ends in `+1d`. `etaClock` counts *calendar days* crossed, so from 12:00 local
onwards 36 hours lands two dates away and it renders `+2d` instead. The suite therefore
reports **122/122 before noon and 121/122 after**. Known, unrelated to whatever you are
changing; the fix is an injectable clock. Verify with `TZ=UTC node tests/js/dashboard.test.js`
if you need a clean run mid-afternoon.

### Truck Load Planner Tests (39 tests)

```bash
python -m pytest tests/test_scorer.py tests/test_auto_arrange_e2e.py tests/test_tlp_routes.py -v
```

`test_scorer.py` (26) covers scoring/candidate-generation units; `test_auto_arrange_e2e.py`
(5) runs realistic-sized shipments through the real production entry points and asserts
on utilization, stacking behavior, the stack-depth cap, and multi-vehicle truck-count
minimization — see `docs/TRUCK_LOAD_PLANNER.md` for the algorithm these exercise.
`test_tlp_routes.py` (8) is the only one of the three that issues an HTTP request, and so
the only one that could have caught the `shipment_id` 500 fixed on 2026-08-06.

Note `tests/test_all.py` is a **script**, not a pytest module — it defines zero `def test_`
and is collected by `pytest tests/` without contributing any tests. Its subcommands are
below.

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
routing_system.db               # The live SQLite database
database.sql                    # Full `sqlite3 .dump` backup of the above, committed to git.
                                 #   UTF-16LE — grep/head fail on it silently. NOT the schema
                                 #   of record; that's app/database/schema.py +
                                 #   services/delivery/database.py
graphify-out/                   # Knowledge graph (graph.json, GRAPH_REPORT.md, graph.html).
                                 #   Rebuild with `graphify update .` — see CLAUDE.md § graphify
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
    ttas_client.py               # TTAS session, live vehicle fetch, report scraping,
                                 #   speed-phrase parsing and MTH lost-signal detection
    routing.py                   # OpenRouteService routing helpers
    locations.py                 # Manual-location file I/O
    vehicle_specs.py             # Vehicle envelope (weight/height/width/length/axle-load):
                                 #   validation, per-type defaults, ORS restriction options
  routes/                       # Flask Blueprints
    fleet.py                     # Vehicle CRUD
    fuel.py                      # Fuel log CRUD, profiles, CSV export, Google Sheet sync
    oil.py                       # Oil maintenance CRUD, TTAS KM-log scraping
    trips.py                     # Main-map route lines + advance/cancel, background route-refresh loop
                                 # (Trip Management / Trip History pages removed 2026-07-31 —
                                 #  superseded by the Dispatch dashboard)
tests/                          # All test, debug, and diagnostic files
  conftest.py                   # Points DB_PATH at a throwaway file before any test module
                                 #   imports app/ — without it the suite migrates the real DB
  test_all.py                   # Unified test harness (16 subcommands; no pytest tests)
  test_scorer.py                # Pytest unit tests (TLP scoring — 26 tests)
  test_auto_arrange_e2e.py      # Pytest end-to-end TLP tests (5 tests)
  test_delivery.py              # Pytest unit tests (delivery services — 223 tests)
  test_delivery_routes.py       # Pytest route-layer tests (delivery HTTP API — 135 tests)
  test_fleet_routes.py          # Pytest route-layer tests (fleet HTTP API — 11 tests)
  test_routing.py               # Pytest unit tests (ORS options, restrictions — 15 tests)
  test_vehicle_specs.py         # Pytest unit tests (envelope validation/defaults — 40 tests)
  test_vehicle_core_data.py     # Pytest guards on the master vehicles table — 36 tests
  js/                           # jsdom drives of the real frontend modules, run with plain node
    dashboard.test.js           # Dispatch dashboard (122)
    plan-builder.test.js        # Delivery plan builder (10)
  debug_arrange.py              # Per-package auto-arrange debugger
  merge_duplicate_vehicles.py   # One-time DB dedup utility
reports/                        # Test and debug output files
docs/                           # CHANGELOG, CODEBASE_ANALYSIS_REPORT, DELIVERY_MODULE,
                                 # TRUCK_LOAD_PLANNER, DISPATCH_UX_PLAN, VEHICLE_ROUTING_PLAN,
                                 # DELIVERY_AUDIT_2026-07-31 reference docs
services/                       # Application services (not to be confused with app/services/ above)
  plate_utils.py                # normalize_plate() — the one canonical plate normalizer
  vehicle_identity.py           # Canonical-plate index; resolves a plate/serial to one vehicle
  google_sheet_service.py       # Google Sheets fuel-log ingest (parsing + sync)
  delivery/                     # Delivery plan management
    database.py                 # Schema DDL, table initialization
    plan_service.py             # Plans, assignments, stops CRUD + Excel import pipeline
    execution_service.py        # Current stop derivation, advance, skip, cancel, revert, reorder
    tracking_service.py         # TTAS GPS wrapper, vehicle lookup
    eta_service.py              # ORS-based ETA calculation (Haversine fallback)
    image_service.py            # Stop image upload, serve, delete
    export_service.py           # End-of-day summary, day-level images, day.zip packaging
    routes.py                   # Flask Blueprint (42 endpoints under /api, none authenticated)
scripts/
  migrate_to_delivery.py        # Idempotent migration from legacy vehicle_trips
  fill_vehicle_gvw_2026-07-31.sql  # One-off backfill of gross vehicle weights
truck_load_planner/             # Core application package
  routes.py                     # Flask routes / API endpoints
  session.py                    # Load planning session
  db.py                         # Database initialization
  engine/                       # Packing algorithms (21 modules — see docs/TRUCK_LOAD_PLANNER.md §13)
  engines/                      # Packing engine abstraction (internal + py3dbp)
  geometry/                     # Canonical AABB, grid, coordinate transforms
  optimization/                 # vehicle_cost.py — cost model, kept out of the geometry engine
  models/                       # Data models
  logistics/                    # Legacy validation helpers — adapters.py delegates check_boundary/
                                 # calculate_total_weight/check_weight to engine/; volume.py and
                                 # constraints.py::get_door_status have no engine equivalent and
                                 # remain self-contained
static/                         # Frontend assets (JS, CSS)
  js/utils.js                   # ApiClient (fetch wrapper) + UI (toast, escapeHtml, etaClock)
                                 #   namespace, shared by all pages
  js/delivery-export.js         # End-of-day export page
  js/dashboard/                 # Dispatch dashboard, split by panel — the only multi-file page
    main.js                     # Orchestrator: state, filters, selection, detail loading, plan management
    api.js                      # Every dashboard fetch, with a 20s client timeout
    polling.js                  # 12s poll cycle, refresh coalescing, pause while the tab is hidden
    vehicle-list.js             # Left panel
    map.js                      # Leaflet: basemap switcher, markers, route line, Esri imagery identify
    timeline.js                 # Right panel: stop list, actions, reordering, locate-on-map
templates/                      # HTML templates
```

**Why both `app.py` and `wsgi.py`?** `app.py` (file) and `app/` (package) share the name `app`, and Python's import system always resolves `import app` to the package over the file. Gunicorn's `app:app` target therefore can't reach `app.py`'s Flask instance — `wsgi.py` gives it an unambiguous one (`gunicorn wsgi:app`, see `render.yaml`). `python app.py` for local dev is unaffected — running a script directly doesn't register it under the package's name.

## Tech Stack

- **Backend**: Python, Flask, SQLite3
- **Frontend**: Vanilla JS (`ApiClient`/`UI` shared namespace in `static/js/utils.js`), Chart.js 4.4.7, Konva.js 9 (canvas), Three.js (3D), Leaflet 1.9.4 (maps)
- **No ORM** — raw SQL for full control, via `DatabaseManager` (`app/db.py`) context-managed connections
- **No build step** — every script is loaded directly by a `<script>` tag

### Third-party hosts the browser must reach

Beyond the app itself, the dispatch dashboard loads from these at runtime. If a driver
tablet or office network filters them, the map degrades rather than failing loudly, so
they are worth allow-listing explicitly:

| Host | Used for |
|------|----------|
| `unpkg.com` | Leaflet JS/CSS |
| `server.arcgisonline.com` | Esri World Imagery tiles **and** the imagery capture-date `identify` query |
| `basemaps.cartocdn.com` | CARTO Positron / Voyager tiles and the satellite label overlay |
| `cdnjs.cloudflare.com` | Chart.js, Konva, Three.js on the other pages |

Server-side the app also calls OpenRouteService (routing/ETA) and TTAS (GPS).
