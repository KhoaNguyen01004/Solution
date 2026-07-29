# Fleet Fuel Management — AI Context

Flask-based fleet management for a real trucking fleet (36 box trucks, 4 large container vehicles):
GPS trip tracking, fuel/oil monitoring, a 3D/2D truck load (bin-packing) planner, and a
delivery plan management module. Solo-developed, deployed to Render via Gunicorn.

Repo root also contains non-app files (an internship report, Vietnamese process docs,
an `.xlsx`) — unrelated to the Flask app; ignore them for code changes.

## Architecture

- **Entry points**: `app.py` (dev, `python app.py`) calls `app.create_app()` then adds
  routes not yet extracted into a blueprint (`/`, `/api/vehicles`, manual-location
  management, `/api/geocode`, delivery page routes). `wsgi.py` is the Gunicorn entry
  (`gunicorn wsgi:app`) — required because `app.py` (file) and `app/` (package) share the
  name `app`, and `import app` always resolves to the package, so Gunicorn's `app:app`
  target can't reach `app.py`'s Flask instance. `python app.py` is unaffected.
- **6 Flask blueprints**: `fleet`, `fuel`, `oil`, `trips` (no shared prefix — each route
  keeps its original full path, e.g. `/api/fleet/vehicles`, `/api/fuel-log`,
  `/oil-change`), `tlp_bp` (`/api/tlp`), `delivery_bp` (`/api`).
- **Database**: SQLite at `routing_system.db`, no ORM — raw SQL throughout. Two access
  patterns coexist and both are intentional (CODEBASE_ANALYSIS_REPORT.md items 9-12):
  - `DatabaseManager` (`app/db.py`, context-manager, `PRAGMA foreign_keys=ON` by default)
    — `services/delivery/*.py`, `truck_load_planner/routes.py`.
  - Raw `sqlite3.connect()` — `app/routes/*.py`, `app.py`.
  `truck_load_planner/routes.py` uses `enable_fk=False` deliberately — that schema has no
  `ON DELETE CASCADE`, and 3 existing delete routes would break under FK enforcement.
- **Concurrency caveat**: no `PRAGMA journal_mode=WAL` configured anywhere. `app/routes/
  trips.py` runs a background route-refresh thread writing to the same file concurrent
  requests write to — "database is locked" here is a pre-existing constraint, not
  necessarily something you broke.
- **Deployment**: `render.yaml` has no `disk:` block. Confirm in the Render dashboard
  whether a persistent disk is attached before assuming `routing_system.db` or
  `DeliveryPlans/` uploads survive a redeploy.
- Two virtualenvs exist (`venv/`, `.venv/`) — check which has packages installed before
  running `pip`/`python`; don't assume either.

## Directory Structure

```
app/config.py        env vars + constants (DB_PATH, ORS_*, TTAS_*, FLASK_*)
app/state.py         shared mutable runtime state (route cache, locks, TTAS session,
                      known_locations) — read/written via `state.<name>`, never `global`
app/db.py            DatabaseManager — `with DatabaseManager(db_path).connect() as conn:`
app/database/         schema.py (CREATE TABLE) + migrations.py (ALTER/backfill)
app/utils/            geo.py (distance/polygon math), export.py (csv_response helper)
app/services/         ttas_client.py, routing.py (ORS), locations.py (manual-location I/O)
app/routes/           fleet.py, fuel.py, oil.py, trips.py — the 4 domain Blueprints
truck_load_planner/   3D bin-packing engine; geometry/aabb.py is the single canonical
                      AABB class; logistics/volume.py + constraints.py::get_door_status
                      are self-contained with no engine equivalent — don't fork them
services/delivery/    Plan/execution/tracking/ETA/image services + routes.py. Unrelated
                      to app/services/ above — same parent word, different packages
static/js/utils.js    Shared ApiClient (fetch wrapper) + UI (.toast(), .escapeHtml())
                      namespace. 3 pages still use the legacy global showToast():
                      locations.js, trip-history.js, manage-trips.js
```

`templates/` — one HTML page per entry, matching `static/js/` filenames.

**Where to look**: vehicle CRUD → `app/routes/fleet.py`; fuel → `app/routes/fuel.py`;
oil/TTAS scraping → `app/routes/oil.py`; trips/background refresh → `app/routes/trips.py`;
core routes (index, `/api/vehicles`, locations, geocoding) → `app.py`; TLP algorithm →
`truck_load_planner/engine/` + `geometry/`; delivery logic → `services/delivery/*.py`.

## How to Run

`python app.py` (dev) · `gunicorn wsgi:app` (prod, see `render.yaml`) · full test-command
reference is in README.md "Running Tests" — don't duplicate it here.

`.env`/`credentials.json` hold real TTAS/Google credentials (gitignored) — never read
their contents into a response, log, or commit.

## AI Working Workflow

For any non-trivial task (multi-file change, new feature, architectural change):

1. **Review** — read the relevant files before touching anything; verify against actual
   code, not memory of a doc or a prior session.
2. **Implementation plan** — state which files you intend to touch and the approach in a
   few sentences.
3. **Approval** — wait for explicit go-ahead before editing, unless already approved in
   the same message.
4. **Implementation** — make the change per Architecture Decision Rules and Scope Control
   below.
5. **Testing** — run the relevant suite from Definition of Done; don't report done
   without having run it.
6. **Summary** — 2-3 sentences on what changed and what's left. No re-narrating the diff.

For trivial, single-file, obviously-scoped fixes, collapse steps 1-3 — use judgment;
don't manufacture ceremony for a one-line change.

## Decision Making

**Don't guess.** If an implementation detail, existing behavior, or convention is unclear:

1. Inspect the repository — read the actual file, don't rely on a doc or a prior summary.
2. Inspect the relevant module for the pattern already in use there.
3. Inspect neighboring/sibling code for precedent.
4. If uncertainty remains after that, ask the user for clarification rather than assume.

Never present an assumption as a verified fact.

## Architecture Decision Rules

- Reuse an existing service/engine module before creating a new one — `truck_load_planner/
  logistics/` and `services/delivery/*.py` are each meant to be the single source of truth
  for their concern.
- Match the existing pattern in the file/module you're editing (DB access style, error
  handling) over introducing a new one. This codebase has deliberately coexisting patterns
  in several places (DB access, frontend toast/escape) — "fixing" one in isolation creates
  a half-migrated state, not an improvement.
- New shared mutable state goes through `app/state.py` behind its existing locks, never a
  bare module-level `global` — especially given `trips.py`'s background thread.

## Long-Term Maintainability

- Extend existing code over replacing it.
- Refactor over rewrite.
- Preserve existing behavior unless the task explicitly calls for changing it.
- Avoid unnecessary abstractions — don't introduce a new pattern, layer, or generalization
  for a problem that doesn't yet exist.

## Coding Standards

- Parameterized SQL only (`?` placeholders) — never string-format user input into a
  query. There's no ORM, so this is the primary injection surface.
- Raw `sqlite3.connect()` call sites (`app/routes/*.py`, `app.py`) must close the
  connection in a `finally` — they don't get `DatabaseManager`'s automatic cleanup.
- Frontend: use `ApiClient`/`UI` from `static/js/utils.js` for any new fetch/toast/escape
  code. Only the 3 unmigrated pages get a pass on the legacy global `showToast()`.
- New pages follow the existing `templates/<page>.html` + `static/js/<page>.js` pairing
  and must include the `utils.js` script tag.

## Operational UI Principles

This is an operations system used by dispatchers, not a consumer app. New UI work should
prioritize:

- **Stability** — don't risk breaking an in-use workflow for a cosmetic change.
- **Responsiveness** — favor incremental DOM updates over full page reloads/re-renders.
- **Preserving UI state** — scroll position, open panels, form input, active filters must
  survive updates; state loss during a refresh disrupts real dispatch use.
- **Minimal clicks** — don't add steps to a workflow used many times a day.
- **Clear information hierarchy** — surface what a dispatcher needs first (current stop,
  ETA, delay status) over secondary detail.
- Always escape user-supplied text via `UI.escapeHtml()` before DOM insertion — the
  2026-07-29 refactor fixed a real XSS bug from older copies that missed single quotes.
- Mobile-friendly for delivery/dispatch pages — used in the field, not at a desk.

## Scope Control

- Only modify files directly related to the requested task — no unrelated cleanup,
  renames, or "while I'm here" fixes.
- If you discover an architectural improvement outside the requested scope, document it
  (in your summary or a note to the user) — do not implement it unless explicitly
  instructed.
- The DB-access-pattern split and the 3-page frontend-namespace gap are deliberately
  incomplete (CODEBASE_ANALYSIS_REPORT.md §9) — don't fix them as a drive-by.
- Ignore root-level non-app files (internship report, `.docx`/`.xlsx`) for code tasks.

## Definition of Done

A task is done only when:

- The relevant suite passes — `pytest tests/test_delivery.py -v` (31 tests) for delivery
  changes, `pytest tests/test_scorer.py -v` (26 tests) for TLP scoring/placement changes.
  No CI is configured, so running these yourself is the only real verification.
- A `CHANGELOG.md` entry was added, in the existing dated-entry style, for
  architecturally significant changes (see the 2026-07-29 entry for expected detail).
  Skip for small, self-contained fixes.
- The user has received the implementation summary (AI Working Workflow step 6).

## Large Feature Workflow

For major features, redesigns, or architectural changes (for example Dispatch, Truck
Load Planner, Fuel Management, or Delivery):

1. Read all relevant modules.
2. Understand the current implementation before proposing changes.
3. Identify affected files and dependencies.
4. Produce a phased implementation plan with clear acceptance criteria.
5. Wait for approval before implementation.
6. Implement one phase at a time.
7. Verify each phase before moving to the next.

Avoid attempting large rewrites in a single implementation. Favor incremental
improvements that preserve existing functionality.

## Reference Documents

- `CODEBASE_ANALYSIS_REPORT.md` — audit, roadmap, Priority Action Items status (§9).
- `CHANGELOG.md` — dated entries on what changed and why.
- `DELIVERY_MODULE.md` — delivery module design/entity reference.
- `SYSTEM.md` — TLP algorithm/scoring internals.
- `INSTRUCTIONS.md` — original delivery-module rewrite spec.
- `README.md` — pages, full test-command reference, algorithm reference, tech stack.
