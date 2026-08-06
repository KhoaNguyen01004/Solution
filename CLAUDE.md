# Fleet Fuel Management — AI Context

Flask-based fleet management for a real trucking fleet — **36 vehicles in `routing_system.db`
as of 2026-08-06: 32 box trucks (1.5–10 t) plus 4 large container vehicles**. GPS trip
tracking, fuel/oil monitoring, a 3D/2D truck load (bin-packing) planner, and a delivery plan
management module. Solo-developed, deployed to Render via Gunicorn.

The fleet count is data, not code — re-derive it with
`SELECT vehicle_type, COUNT(*) FROM vehicles GROUP BY vehicle_type` rather than trusting
this line, which goes stale the moment a truck is added.

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
  patterns coexist and both are intentional (docs/CODEBASE_ANALYSIS_REPORT.md items 9-12):
  - `DatabaseManager` (`app/db.py`, context-manager, `PRAGMA foreign_keys=ON` by default)
    — `services/delivery/*.py`, `truck_load_planner/routes.py`.
  - Raw `sqlite3.connect()` — `app/routes/*.py`, `app.py`.
  `truck_load_planner/routes.py` uses `enable_fk=False` deliberately — that schema has no
  `ON DELETE CASCADE`, and 3 existing delete routes would break under FK enforcement.
- **No authentication, by decision.** A shared dispatcher password existed for part of
  2026-07-31 and was removed at the operator's request (see `docs/CHANGELOG.md`): this
  runs on an internal network and the login step cost dispatchers time at every shift
  change. Every endpoint, `POST /api/plans/clear` included, is open. **Do not re-add auth
  as a drive-by "fix"** — `tests/test_delivery_routes.py::TestOpenAccess` fails if you do,
  and it is deliberate, not an oversight. If the deployment ever becomes publicly
  reachable, that is the conversation to have first.
- **Concurrency**: no `PRAGMA journal_mode=WAL` and no explicit `busy_timeout` anywhere
  (so the effective timeout is Python's 5 s default, by accident rather than decision).
  `app/routes/trips.py` runs a background route-refresh thread writing to the same file
  concurrent requests write to. **Measured 2026-08-06 — see
  `docs/CONCURRENCY_PLAN_2026-08-06.md` before reasoning about this:**
  - `database is locked` is a **writer-vs-writer** failure, and **WAL does not fix it** —
    SQLite serialises writers in both modes. It fires when a write is held past the busy
    timeout. A held `RESERVED` lock does *not* block readers; four readers arriving during
    a 7 s hold all completed in under 5 ms.
  - The real source of those errors was the geofence transaction bug (a write lock held
    across N serial ORS calls), fixed 2026-08-06. This entry previously implied WAL was
    the safety prerequisite for adding workers. It is not.
  - WAL is still worth enabling, on throughput grounds: 2.3× read throughput, read p95
    81 ms → 29.5 ms, write p50 24 ms → 0.8 ms. `journal_mode` persists in the database
    file, so it is one line in `init_db()`, not a per-connection pragma.
  - `render.yaml`'s `gunicorn wsgi:app` has no `--workers`/`--threads`, so production is a
    **single synchronous worker** and requests queue behind each other —
    `/api/execution/dashboard` does a blocking TTAS fetch inside the request, so a user
    action landing mid-poll waits for it. Workers fix that head-of-line blocking, but the
    blocker is **not** the database: `app/state.py` is process-global, so a second worker
    means two route caches, two TTAS sessions, and `state.sync_lock` /
    `state.oil_fetch_lock` silently ceasing to be mutual exclusion. Settle that first.
  - `--threads` is ignored by the default `sync` worker class; it needs
    `--worker-class gthread`.
- **Deployment**: `render.yaml` declares a 20 GB persistent disk (`fleetfuel-data`) at
  `/var/data`, with `DB_PATH=/var/data/routing_system.db` and `DATA_DIR=/var/data`. So
  `routing_system.db` and the `DeliveryPlans/` photos **do** survive a redeploy. Two
  consequences the block's own comment records: a service with a disk cannot run more
  than one instance and loses zero-downtime deploys — neither costs anything while
  production is a single synchronous worker, but both become real the moment the
  `--workers` question below is answered. (This entry said the opposite until
  2026-08-06; the disk was added and the note was not updated.)
- **`database.sql` is a full production data dump, committed to git.** 294 KB, added
  2026-08-03 in `09671bb`, **not gitignored**. It is a complete `sqlite3 .dump` — all 24
  tables plus 868 `INSERT`s — and it matches the live database exactly (36 vehicles, 323
  `fuel_log` rows, 52 `delivery_plan_stops` including the `manager_phone` column). It is a
  backup, not a schema file: **the schema of record is `app/database/schema.py` plus
  `services/delivery/database.py`**, never this dump. Two consequences worth knowing
  before touching it:
  - **It is UTF-16LE with a BOM**, not UTF-8. `grep`, `head` and tree-sitter all fail on
    it silently — `grep -c "INSERT INTO" database.sql` returns 0. Read it with an explicit
    `open(..., 'rb').read().decode('utf-16')`.
  - It carries real operational data — driver names, station addresses, manager phone
    numbers — in a tracked file. `.env` and `credentials.json` are gitignored; this is
    not. Flag it rather than quietly regenerating or deleting it; whether it belongs in
    the repo is the operator's call.
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
app/services/         ttas_client.py, routing.py (ORS), locations.py (manual-location I/O),
                      vehicle_specs.py (envelope validation, per-type defaults, ORS
                      restriction options — see docs/VEHICLE_ROUTING_PLAN.md)
app/routes/           fleet.py, fuel.py, oil.py, trips.py — the 4 domain Blueprints
truck_load_planner/   3D bin-packing engine; geometry/aabb.py is the single canonical
                      AABB class; logistics/volume.py + constraints.py::get_door_status
                      are self-contained with no engine equivalent — don't fork them.
                      optimization/vehicle_cost.py is the cost model, kept deliberately
                      outside engine/ so business factors stay out of packing logic
services/             plate_utils.py (normalize_plate — the one canonical normalizer),
                      vehicle_identity.py (canonical-plate index + resolve()),
                      google_sheet_service.py (fuel-log ingest)
services/delivery/    Plan/execution/tracking/ETA/image/export services + routes.py.
                      Unrelated to app/services/ above — same parent word, different
                      packages
static/js/utils.js    Shared ApiClient (fetch wrapper) + UI (.toast(), .escapeHtml(),
                      .etaClock(), .etaRelative()) namespace. 1 page still uses the
                      legacy global showToast(): locations.js. (Was 3 — trip-history.js
                      and manage-trips.js were deleted 2026-07-31 with the trip pages.)
static/js/dashboard/  The dispatch dashboard, and the ONLY multi-file page. Namespaced
                      on window.DASH; load order is fixed by the template:
                        api.js        every fetch, 20s client timeout
                        polling.js    12s cycle, refresh coalescing, pauses when hidden
                        vehicle-list.js  left panel
                        map.js        Leaflet: basemaps, markers, route, Esri identify
                        timeline.js   right panel: stops, actions, reorder, locate
                        main.js       orchestrator — owns state and is loaded last
                      Cross-module calls go through DASH.state / DASH.map / DASH.timeline,
                      never by reaching into another file's internals.
```

`templates/` — one HTML page per entry, matching `static/js/` filenames.

**Where to look**: vehicle CRUD → `app/routes/fleet.py`; fuel → `app/routes/fuel.py`;
oil/TTAS scraping → `app/routes/oil.py`; trips/background refresh → `app/routes/trips.py`;
core routes (index, `/api/vehicles`, locations, geocoding, delivery page routes) →
`app.py`; TLP algorithm → `truck_load_planner/engine/` + `geometry/`; delivery logic →
`services/delivery/*.py`; end-of-day export → `services/delivery/export_service.py`;
plate → vehicle resolution → `services/vehicle_identity.py`.

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
  code. Only `locations.js` gets a pass on the legacy global `showToast()` (was 3 pages;
  the other two were deleted 2026-07-31). `delivery-plan-builder.js` is a third case —
  it defines its own local `showToast()` shadowing the global, and also its own
  `fetchJSON()`, because the delivery API returns raw JSON rather than `ApiClient`'s
  `{success: ...}` envelope. Match the file you're in; don't half-migrate one of them.
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

### Dashboard map conventions (learned the hard way, 2026-07-31)

- **Never move the map view except in direct response to a click.** The only automatic
  pan is Follow mode, which is explicitly opted into. Anything that deliberately moves
  the view elsewhere (locating a stop) turns Follow off first, or the next poll undoes it.
- **Leaflet's popup autoPan is a hidden view-mover.** `Popup._adjustPan()` is reached both
  by `popup.setContent()` and by `marker.setLatLng()` firing `move`. Both run on every
  poll for a moving truck with an open popup, and both used to drag the map back onto the
  vehicle. `map.js`'s `withoutAutoPan()` wraps background updates; opening a popup still
  pans, which is intentional.
- **Markers must read on any basemap.** The base is user-switchable between satellite and
  near-white street maps, so marker styling carries both a dark fill/ring and a light
  outer ring. A single-colour outline works on one and disappears on the other.
- **Never make a panel wait on `/api/eta`.** It issues one OpenRouteService call per
  remaining stop, serially, each with a 30s server timeout. Fetch it alongside the fast
  local queries and paint as each lands — never in one `Promise.all`.
- **Panels absolutely positioned over the map** (`.map-controls`, the info bar) and
  Leaflet's own controls compete for corners; check all four before adding another.

### TTAS telemetry conventions (learned the hard way, 2026-08-03)

- **TTAS sends no numeric speed field.** Its `speed` key is a Vietnamese status *phrase*
  — `Chạy 42km/h`, `Dừng 3h30'`, `MTH:6h48'` — so every km/h figure on the dashboard is
  an extraction from prose. Never grab the first number in it: only the running phrase's
  number is a speed, and a stopped one counts how long the vehicle has been parked. That
  exact mistake reported a truck stopped 7h44' as doing 7 km/h.
- **Read the phrase's meaning before its digits.** `_parse_speed_kmh` takes a number only
  when it carries the km/h unit, maps `Dừng` to a known `0.0`, and strips durations before
  any unitless fallback. `app/routes/trips.py:403` (`re.search(r'(\d+(?:\.\d+)?)',
  speed_str)`, feeding `current_speed`) still runs the old first-number-wins regex —
  deliberately untouched, and known to be wrong. Grep for `current_speed` rather than
  trusting the line number.
- **`None` and `0.0` are different facts** and the dashboard renders them differently
  (blank vs a speed). `None` means "no reading we can interpret", not "stopped".
- **TTAS's own declaration beats our inference.** `MTH:6h48'` (*mất tín hiệu*) is TTAS
  stating the tracker is unreachable, which is stronger and earlier than deducing it from
  a stale timestamp — a tracker reporting late is not a tracker that is gone. Hence
  `is_lost_signal()` and the `lost_signal` vehicle status, which the No GPS filter keys
  off. Keep the computed `gps_stale` chip alongside it: two independent paths to the same
  conclusion is what caught this.
- **A lost-signal vehicle still has a position** — the last fix before the signal dropped.
  Any "does it have GPS?" test will therefore say yes. That is precisely why it went
  missing from the No GPS filter.
- **New phrase forms will appear.** This string is scraped, not contracted. Match
  tolerantly (case, spacing, abbreviation) and fall through to "unknown" rather than
  guessing.

## Scope Control

- Only modify files directly related to the requested task — no unrelated cleanup,
  renames, or "while I'm here" fixes.
- If you discover an architectural improvement outside the requested scope, document it
  (in your summary or a note to the user) — do not implement it unless explicitly
  instructed.
- The DB-access-pattern split and the 3-page frontend-namespace gap are deliberately
  incomplete (docs/CODEBASE_ANALYSIS_REPORT.md §9) — don't fix them as a drive-by.
- Ignore root-level non-app files (internship report, Vietnamese process docs,
  `.docx`/`.xlsx`) for code tasks. **`database.sql` is not in that category** — it is real
  production data (see Architecture). Don't ignore it, but don't regenerate, reformat or
  delete it as a drive-by either.

## Definition of Done

A task is done only when:

- The relevant suite passes. For delivery changes run **both** `pytest tests/test_delivery.py -v`
  (223, service layer) and `pytest tests/test_delivery_routes.py -v` (135, route layer) —
  the service suite is structurally blind to bugs inside a request handler or in an
  assembled response, which is where every Critical audit finding lived. For TLP
  scoring/placement, `pytest tests/test_scorer.py -v` (26). `pytest tests/` is 548 total.
  No CI is configured, so running these yourself is the only real verification.
  `test_delivery_routes.py` needs `playwright` importable — it reaches the app through
  `main.py`, which imports it at module level, and all 135 error out with
  `ModuleNotFoundError` without it. It **is** pinned in `requirements.txt`
  (`playwright==1.61.0`), so this means your environment is out of date, not that the
  dependency is undeclared — `pip install -r requirements.txt` fixes it. Note
  `requirements.txt` is UTF-16, so `grep playwright requirements.txt` finds nothing and
  will tell you the opposite.
- **Route-layer suites added 2026-08-06** (see `docs/AUDIT_2026-08-06.md`):
  `tests/test_tlp_routes.py` (8) is the TLP's first; `tests/test_trips_geofence.py` (7)
  is the first coverage of any kind for `app/routes/trips.py`;
  `tests/test_fuel_routes.py` (6) is the first for `app/routes/fuel.py`;
  `tests/test_write_handler_connections.py` (36) covers write handlers across all four
  route modules. The pattern to copy for a new one is `test_delivery_routes.py`.
- Frontend-only changes get no pytest coverage at all. Check syntax with `node --check`,
  and drive the actual module under jsdom rather than reasoning about it — the 2026-07-31
  dashboard work and the 2026-08-02 plan-builder work each found bugs that way that
  inspection had missed. Three suites exist, all run with plain `node`:
  `tests/js/dashboard.test.js` (122) and `tests/js/plan-builder.test.js` (10) need jsdom;
  `tests/js/tlp-escaping.test.js` (5) is deliberately dependency-free so it still runs in
  a checkout with no `node_modules`, because the thing it guards against — escaping being
  dropped from `truck-load-planner.js` again — would recur years from now, and a test that
  needs setup is a test that stops being run. jsdom is dev-only and not vendored: `npm
  install jsdom` at the repo root is enough (Node resolves `node_modules` upward from the
  test file), or `NODE_PATH=/path/to/node_modules node tests/js/<file>`. `node_modules/`
  is gitignored as of 2026-08-06.
  One dashboard ETA case is time-of-day dependent: `a route running past midnight is
  marked, not shown as already late` asserts a 36-hour ETA renders `+1d`, but
  `UI.etaClock()` counts calendar days crossed, so from **12:00 local onwards** 36 hours
  is two dates away and it renders `+2d`. Expect 122/122 before noon and 121/122 after;
  `TZ=UTC node tests/js/dashboard.test.js` gives a clean run from a UTC+7 afternoon.
  Known, and not something you broke.
- Prefer a mutation check over a green run for any bug fix: revert the fix, confirm the
  new tests fail, restore it. Several tests in these suites passed against the broken
  code before this was routine.
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

- `docs/CODEBASE_ANALYSIS_REPORT.md` — whole-codebase audit, roadmap, Priority Action
  Items status (§9). Carries dated addenda; read the newest one first.
- `docs/CHANGELOG.md` — dated entries on what changed and why. Newest at the top.
- `docs/DELIVERY_MODULE.md` — delivery module design/entity/API reference.
- `docs/TRUCK_LOAD_PLANNER.md` — TLP algorithm/scoring/API/frontend reference.
- `docs/DELIVERY_AUDIT_2026-07-31.md` — the delivery-specific audit that drove Phases 1–5.
  A dated snapshot: findings are recorded as they stood on 2026-07-31, with their
  resolution status. Don't read a present-tense "Problem" as a live bug.
- `docs/AUDIT_2026-08-06.md` — whole-workspace audit. Every finding was reproduced
  against live code or data before being written down, and §6 lists what was checked and
  found **clean**, so the same ground isn't re-walked. All findings are now fixed; read it
  for the reasoning, not for open work.
- `docs/BUGFIX_PLAN_2026-08-06.md` — the phased plan those fixes were made under, with the
  scope decisions the operator made (write handlers only; TTAS case-tolerance deferred).
- `docs/CONCURRENCY_PLAN_2026-08-06.md` — WAL and `--workers`, measured. **Recommendation
  only; nothing was changed.** Read before touching `render.yaml` or `journal_mode`.
- `docs/DISPATCH_UX_PLAN.md` — dispatch board UX research and phased plan. Phase 0 shipped;
  Phases 1–2 remain proposed and unapproved.
- `docs/VEHICLE_ROUTING_PLAN.md` — vehicle-constrained routing plan. Phases A–C shipped;
  still running on `type_default` estimates, not registration-certificate data.
- `README.md` — pages, full test-command reference, tech stack (stays at repo root).

The `*_PLAN`/`*_AUDIT` documents are historical records as much as references — their
status headers are current, their bodies preserve what was proposed versus what shipped.
Update the header, not the history. Where a later measurement contradicts an earlier
finding, the correction is added inline as a dated note rather than by editing the
original claim away (see `AUDIT_2026-08-06.md` §2 for the pattern).

## graphify — traverse the graph before reading files

There is a knowledge graph at `graphify-out/` (3,104 nodes · 5,957 edges · 200
communities, rebuilt 2026-08-06 after the audit fixes). **Standing instruction: for any
question about how this codebase fits together, query the graph before grepping or
opening files.** A scoped subgraph is a fraction of the tokens of a directory sweep, and
this repo is large enough (138 files, ~640k words) that the difference is the whole
context budget.

Community *labels* are one rebuild behind: the last `graphify update` renamed 88
communities by their hub node because the community set shifted, and refreshing the names
properly needs `graphify label`, which costs an LLM call. Labels being approximate does
not affect `query`/`path`/`explain`/`affected`, which read edges rather than names.

The CLI is the PyPI package **`graphifyy`** — three y's. The command is `graphify`;
`pip install graphify` gets an unrelated package. In a fresh sandbox:
`pip install --break-system-packages "graphifyy[sql]"` then
`export PATH="$PATH:$HOME/.local/bin"` (the binary is not on PATH by default).

| Question shape | Command |
|---|---|
| "How does X work?" / "what touches Y?" | `graphify query "<question>"` |
| "How does X reach Y?" | `graphify query "<q>" --dfs` |
| "What connects A and B?" | `graphify path "A" "B"` |
| "What is X, and what does it touch?" | `graphify explain "X"` |
| **"What breaks if I change X?"** | `graphify affected "X" --depth N` |
| "What are the hubs here?" | `graphify god-nodes --top N` |

`--budget N` caps output tokens (default 2000). `--graph <path>` overrides the default
`graphify-out/graph.json`.

### Two failure modes, both learned the hard way (2026-08-06)

- **There is no per-subcommand `--help`.** `graphify query --help` does not print help —
  it takes `--help` as the *question*, matches the literal substring "help", and returns
  real-looking noise (it surfaced `.openHelp()` from `truck-load-planner.js` alongside
  unrelated test nodes). Only bare `graphify --help` prints usage.
- **Matching is case-folded substring + IDF. No stemming, no synonyms.** A question
  phrased in different vocabulary than the node labels returns noise *silently*, with no
  "0 results" to warn you. For anything non-obvious, extract the graph's own token
  vocabulary from node labels first and query using only tokens that actually appear in
  it. Never substitute a near-synonym from memory.

**Confidence tags are load-bearing.** Edges are 98% `EXTRACTED` (AST-derived, reliable)
and 2% `INFERRED` (LLM-guessed, avg confidence 0.53). Never report an `INFERRED` edge as
established fact. The graph says what connects to what — not whether the code is correct.
Cite `source_file:source_location` and open the file to confirm anything surprising.

### Keeping it current

`graph.json` carries `built_at_commit`; compare it to `git rev-parse HEAD` before trusting
a result, because a stale graph answers confidently about deleted code. `graphify update .`
re-extracts changed files by AST only — no LLM, no API key, no cost. Use `--force` after a
refactor that deletes code, since the rebuild otherwise refuses to shrink the graph.

Read `graphify-out/GRAPH_REPORT.md` only for broad architecture review, or when
query/path/explain do not surface enough. `graphify-out/wiki/index.md` does not currently
exist in this repo.

**`.sql` files are effectively not in the graph, and installing the `[sql]` extra will not
fix it.** `database.sql` is UTF-16LE (see the note under Architecture), which
tree-sitter-sql cannot parse, so it contributes one bare file node and zero edges. Don't
spend time trying to make SQL indexing work here — read the file directly with an explicit
`encoding='utf-16'`.
