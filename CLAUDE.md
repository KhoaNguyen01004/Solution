# Fleet Fuel Management — AI Context

Flask-based fleet management: GPS trip tracking, fuel/oil monitoring, a 3D/2D truck load
(bin-packing) planner, and a delivery plan management module.

## Project structure (key dirs)
- `app.py` — Entry point. Calls `app.create_app()` to build the Flask app, then adds the
  remaining routes that haven't been extracted into a domain blueprint yet (`/`,
  `/api/vehicles`, manual-location management, `/api/geocode`, delivery page routes).
  Run via `python app.py` for local dev.
- `app/` — The Flask application package (see "How the app/ package is organized" below).
  This is what `CODEBASE_ANALYSIS_REPORT.md` Section 6.4.1 proposed and it's now real —
  don't assume the old "everything is in app.py" model from before 2026-07-29.
- `wsgi.py` — Gunicorn entry point (`gunicorn wsgi:app`). Required because `app.py` and
  `app/` share the name `app`; `import app` always resolves to the package, so Gunicorn's
  `app:app` target can't reach `app.py`'s Flask instance. `python app.py` is unaffected.
- `main.py` — Playwright-based scraper for the TTAS tracking/report site; imported by
  `app/routes/oil.py` (`fetch_report`) for oil-change KM-log fetching.
- `truck_load_planner/` — 3D cargo bin-packing engine. Blueprint mounted at `/api/tlp`.
  - `geometry/aabb.py` — the single canonical `AABB` class (clearance-aware, point
    containment, overlap). `engine/geometry.py` just re-exports it — both import paths
    give you the same class.
  - `logistics/` — `adapters.py` delegates `check_boundary`/`calculate_total_weight`/
    `check_weight` to `engine/`; `volume.py` and `constraints.py::get_door_status` have no
    engine equivalent and remain self-contained (not legacy cruft — still the live
    implementation for those two).
- `services/delivery/` — Delivery plan management (plan/execution/tracking/ETA/image
  services + `routes.py`). Blueprint mounted at `/api`. Unrelated to `app/services/` above
  — same parent word, different packages.
- `static/js/utils.js` — Shared `ApiClient` (fetch wrapper, `API_BASE = '/api'`) and `UI`
  (`.toast()`, `.escapeHtml()`) namespace, loaded by every page template. A bare global
  `showToast()` alias also still exists there for 3 pages (`locations.js`,
  `trip-history.js`, `manage-trips.js`) that weren't migrated to the namespace.
- `templates/` — Jinja2 HTML templates, one per page, matching `static/js/` filenames.
- `tests/` — `test_delivery.py` (pytest, 31 tests), `test_scorer.py` (pytest),
  `test_all.py` (CLI harness with benchmark/diagnose/debug/query/instrument subcommands —
  see README "Running Tests"), `debug_arrange.py` (standalone debugger).
- `scripts/` — One-off/maintenance scripts (e.g. `migrate_to_delivery.py`).

## How the app/ package is organized
```
app/__init__.py          create_app(): config, init_db(), state init, blueprint registration
app/config.py            env vars + constants (DB_PATH, ORS_*, TTAS_*, FLASK_*)
app/state.py             shared mutable runtime state (route cache, locks, TTAS session,
                          known_locations) — read/written via `state.<name>`, not `global`
app/db.py                DatabaseManager — `with DatabaseManager(db_path).connect() as conn:`
app/database/            schema.py (CREATE TABLE) + migrations.py (ALTER/backfill)
app/utils/                geo.py (distance/polygon math), export.py (csv_response helper)
app/services/            ttas_client.py, routing.py (ORS), locations.py (manual-location I/O)
app/routes/               fleet.py, fuel.py, oil.py, trips.py — the 4 domain Blueprints
```
Everything in `app/routes/*.py` still uses raw `sqlite3.connect(config.DB_PATH)` rather
than `DatabaseManager` — that migration only covered the 4 files named in the report
(`services/delivery/*.py` + `truck_load_planner/routes.py`), not the newly-extracted
blueprints. Treat that as a known gap, not a mistake, if you're auditing for consistency.

## Key architectural facts
- Database: SQLite at `routing_system.db`, path from `config.DB_PATH`. `DatabaseManager`
  (`app/db.py`) is the modern pattern (`services/delivery/*.py`, `truck_load_planner/routes.py`);
  most of `app/routes/*.py` and `app.py` itself still use raw `sqlite3.connect()` directly.
- 6 Flask blueprints total: `tlp_bp` (`/api/tlp`), `delivery_bp` (`/api`), plus the 4 new
  ones (`fleet`, `fuel`, `oil`, `trips` — no shared prefix, each route keeps its original
  full path, e.g. `/api/fleet/vehicles`, `/api/fuel-log`, `/oil-change`).
- Frontend has a shared `ApiClient`/`UI` namespace (`static/js/utils.js`) — use it for any
  new fetch/toast/escapeHtml code. Check the specific page's JS file before assuming every
  page has fully migrated to it (3 pages haven't: `locations.js`, `trip-history.js`,
  `manage-trips.js`).

## How to run
- `python app.py` — dev server; host/port/debug from `FLASK_HOST`/`FLASK_PORT`/`FLASK_DEBUG`.
- `gunicorn wsgi:app` — production (see `render.yaml`).
- `python -m pytest tests/test_delivery.py -v` — delivery module tests.
- `python -m pytest tests/test_scorer.py -v` — truck load planner scorer tests.
- `python tests/test_all.py <benchmark|diagnose|debug|query|instrument> ...` — truck load
  planner CLI tooling (see README.md for full subcommand list).
- Config is in `.env` (not committed): `DB_PATH`, `ORS_API_KEY`, `ORS_BASE_URL`,
  `GOOGLE_CREDENTIALS_PATH`, `GOOGLE_SHEET_ID`, `TTAS_*` credentials, `FLASK_*`.

## Common tasks — where to look
- Vehicle CRUD: `app/routes/fleet.py`.
- Fuel log / sync: `app/routes/fuel.py`.
- Oil maintenance / TTAS KM scraping: `app/routes/oil.py`.
- Trip management / route-refresh background thread: `app/routes/trips.py`.
- Remaining core routes (index, `/api/vehicles`, locations, geocoding): `app.py` itself.
- Truck load planner logic: `truck_load_planner/engine/` and `truck_load_planner/geometry/`.
- Delivery plan/execution/tracking logic: `services/delivery/*.py`.
- TTAS scraping/report fetching: `app/services/ttas_client.py` (session/live-fetch) and
  `main.py` (Playwright report scraper, used by `app/routes/oil.py`).
- Frontend for a given page: matching pair in `templates/<page>.html` and
  `static/js/<page>.js`; shared helpers in `static/js/utils.js`.

## Further reading
- `CODEBASE_ANALYSIS_REPORT.md` — full audit, refactoring roadmap, and known issues. Its
  Priority Action Items tables (§9) have a Status column now — most of Phases 1–4 are
  done; Phase 2 items 9-12, Phase 3 item 16, and Phase 4 items 21-22 are still open.
- `CHANGELOG.md` — the 2026-07-29 entry documents everything this refactor changed, in
  detail, including two real bugs it caught (a toast-positioning CSS conflict and a
  Gunicorn entry-point break) before they'd have hit users/production.
- `DELIVERY_MODULE.md` — delivery module design/entity reference.
- `SYSTEM.md`, `INSTRUCTIONS.md` — additional project documentation.
