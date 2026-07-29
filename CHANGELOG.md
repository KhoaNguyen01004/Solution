# Changelog

## 2026-07-29 — Architecture Refactor: Frontend Namespace, DatabaseManager, AABB Unification, `app/` Package Extraction

Implements Phase 1 items 1–6, Phase 2 items 7–8, Phase 3 items 13–15, and Phase 4 items 17–20 of `CODEBASE_ANALYSIS_REPORT.md`'s Priority Action Items (see that file's updated status column for the full picture, including what's still pending).

### Added

#### `CLAUDE.md` (project root)
- Lean AI-context file per report §10.1 — project structure, key architectural facts, how to run, common-task pointers. Superseded almost immediately by the `app/` extraction below; kept up to date across this session.

#### Frontend: `ApiClient` + `UI` namespace (`static/js/utils.js`)
- `ApiClient.fetch/get/post/put/del` — centralized `fetch()` wrapper with a single `API_BASE` constant (`/api`), replacing 3 duplicated `apiFetch()` copies (`fuel-efficiency.js`, `oil-change.js`, `vehicle-management.js`)
- `UI.toast()` — replaces 6 divergent `showToast`/`toast` implementations across `map.js`, `fuel-efficiency.js`, `fuel-sync.js`, `vehicle-management.js`, `oil-change.js`, `truck-load-planner.js`; standardizes on `(message, type, duration)` argument order
- `UI.escapeHtml()` — replaces 4 `escapeHtml`/`escHtml` copies, **fixing an XSS gap**: the `fuel-efficiency.js` and `vehicle-management.js` copies didn't escape single quotes
- Deduplicated `todayISO`, `formatDate`, `fmtNum` (from `fuel-efficiency.js` + `oil-change.js`) and `normalizeText`, `getDistanceMeters`, `isPointInPolygon` (shadowed in `map.js`) into `utils.js`
- Backward-compatible global `showToast()` alias kept in `utils.js` — `locations.js`, `trip-history.js`, and `manage-trips.js` (out of this refactor's scope) still call the bare global function
- Added `<script src="/static/js/utils.js">` to 5 templates that never loaded it before (`fuel-efficiency.html`, `oil-change.html`, `vehicle-management.html`, `truck-load-planner.html`, `delivery-plan-builder.html`) — required for `ApiClient`/`UI` to exist on those pages at all

#### `EnginePackage.from_legacy()` (`truck_load_planner/engine/package.py`)
- Single classmethod factory handling both legacy-object (`models.Package`, attribute access) and legacy-dict (plain or underscore-prefixed keys) shapes, replacing 4 inline `EnginePackage(...)` construction sites across `session.py` and `routes.py`

#### `app/db.py` — `DatabaseManager`
- Context-manager connection wrapper: `PRAGMA foreign_keys = ON` by default (fixes a silent data-integrity gap — `services/delivery/image_service.py`'s old `get_conn()` never enabled it), auto-commit on success, auto-rollback + close on exception
- Replaces the 4 duplicated `get_conn()`/`_get_db()` copies in `services/delivery/plan_service.py`, `execution_service.py`, `image_service.py`, and `truck_load_planner/routes.py`
- `truck_load_planner/routes.py` connections use `enable_fk=False` deliberately — that schema has no `ON DELETE CASCADE`, and 3 of its routes (`delete_package`, `delete_shipment_item`, `delete_shipment`) delete a parent row without cleaning up all referencing children; turning FK enforcement on there would newly raise `IntegrityError` on those routes. Flagged as a follow-up, not fixed here.

#### `truck_load_planner/geometry/aabb.py` — unified `AABB`
- Merged the two previously-diverged `AABB` classes (`geometry/aabb.py` basic version, `engine/geometry.py` clearance-aware superset) into one canonical class
- `engine/geometry.py` is now a 15-line re-export (`AABB` + the 4 transform helpers, which were already duplicated verbatim in `geometry/transform.py`) — no import-site changes needed anywhere

#### `truck_load_planner/logistics/adapters.py`
- `check_boundary`, `calculate_total_weight`, `check_weight` now delegate to their `engine/` equivalents instead of duplicating logic; `boundary.py`/`weight.py` re-export from here, public signatures unchanged
- `volume.py`, `constraints.py::get_door_status`, and `placement.py::try_place` were **not** adapted — no engine equivalent exists for the exact same behavior (volume math, live door-status reporting, and `try_place` is confirmed dead code with zero callers), and inventing one was out of scope

#### `app/` package — extracted from the `app.py` monolith
`app.py` shrank from **3,625 lines to 225 lines**. New structure:
| Module | Contents |
|---|---|
| `app/config.py` | Env vars, constants (`DB_PATH`, `ORS_*`, `TTAS_*`, `FLASK_*`) |
| `app/state.py` | Shared mutable runtime state (route cache, locks, `known_locations`, TTAS session) — not in the original report plan, added because the blueprints below can't share plain module globals across files the way one big file could |
| `app/database/schema.py` + `migrations.py` | `init_db()` split into table creation vs. column migrations/backfill |
| `app/utils/geo.py`, `export.py` | Geo math helpers; a genuinely new shared CSV-response helper (oil and fuel exports each had their own copy before) |
| `app/services/ttas_client.py`, `routing.py`, `locations.py` | TTAS session/scraping, ORS routing, manual-location file I/O (the last one also not in the original plan — needed so `create_app()` can populate `state.known_locations` at startup without a circular import against `app.py`) |
| `app/routes/fleet.py`, `fuel.py`, `oil.py`, `trips.py` | The 4 domain Blueprints named in the report, covering all 65+ routes |
| `app/__init__.py` | `create_app()` factory — config, `init_db()`, blueprint registration |

#### `wsgi.py`
- Dedicated Gunicorn entry point. **Required**, not optional: `app.py` (file) and `app/` (package) share the name `app`, and `import app` always resolves to the package. `render.yaml`'s existing `startCommand: gunicorn app:app` would have broken on the next deploy since `app/__init__.py` only exposes `create_app()`, not a module-level Flask instance. `render.yaml` updated to `gunicorn wsgi:app`.

### Fixed
- N+1 query in `execution_service.get_dashboard_data()`: was 1 + 2×N queries (101 for 50 assignments), now a flat 3 queries regardless of N (window-function query for each assignment's current stop, one `GROUP BY` for status counts)
- XSS gap in `UI.escapeHtml()` vs. the two `escapeHtml`/`escHtml` copies that didn't escape `'`
- `image_service.py` connections now enforce `PRAGMA foreign_keys = ON` (previously the only one of the 4 `get_conn()` copies that didn't)
- A bug in this session's own first draft of `UI.toast()`: unconditionally adding a `.toast-container` CSS class to the page's toast container broke positioning on the 3 pages (`oil-change`, `vehicle-management`, `truck-load-planner`) that already had their own `#toast-container` CSS rule — fixed by only adding the shared class when the element isn't already `position: fixed`

### Changed
- `truck_load_planner/session.py` — `_to_engine_pkg()` and `_from_legacy_dict()` now delegate to `EnginePackage.from_legacy()`
- `truck_load_planner/routes.py` — `_get_packages_from_request()` delegates to `EnginePackage.from_legacy()`; all 30 `_get_db()` call sites migrated to `DatabaseManager`
- `services/delivery/plan_service.py`, `execution_service.py`, `image_service.py` — all functions migrated from manual `get_conn()`/`try`/`finally` to `with DatabaseManager(db_path).connect() as conn:`
- `tests/test_delivery.py` — one test called the now-removed `plan_service.get_conn()` directly; updated to use `DatabaseManager` (still tests the same rollback-on-FK-violation behavior)

### Removed
- `services/delivery/tracking_service.py` — 4 dead functions (`get_ttas_vehicles`, `update_ttas_cache`, `find_vehicle_by_plate`, `find_vehicle_by_id`) and their backing module globals (`_ttas_vehicles_cache`, `_cache_timestamp`); `normalize_gps_position()` (the one live function) kept
- Duplicated `mm_to_px`/`px_to_mm`/`compute_scale`/`rotate_dimensions` definitions in `engine/geometry.py` (now re-exported from `geometry/transform.py` instead)

### Verification
Every change above that touched behavior (not just file location) was checked with a recovered-vs-new equivalence test comparing outputs on real data before/after: `init_db()` against a fresh DB and a copy of the production DB (17 and 23 tables, byte-identical schema + row counts), `get_dashboard_data()` (13→3 queries, identical JSON), `EnginePackage.from_legacy()` (10 scenarios incl. zero-weight and empty-input edge cases), the `logistics/adapters.py` delegates, and `csv_response()`. The full test suite (57 tests) and a live server + browser pass (every route, a real write, the background route-refresh thread, and the map/dashboard/TLP pages) were run after each major step, not just at the end.

---

## 2026-07-26 — Phase 1: Delivery Plan Management Rewrite

### Added

#### New Database Schema (6 tables, coexists with legacy `vehicle_trips`)
- `drivers` — driver registry with name, phone, license
- `delivery_plans` — daily delivery plan header (status: draft/confirmed/executing/completed/cancelled)
- `vehicle_assignments` — vehicle-to-plan mapping (FK → plans, vehicles, drivers)
- `delivery_plan_stops` — immutable stop definitions (planned_sequence, station, coords, manager, product, notes)
- `stop_executions` — mutable runtime state (execution_sequence, status: planned/enroute/arrived/completed/skipped/cancelled, timestamps)
- `delivery_stop_images` — per-stop image metadata with categories (loading/delivery/extra), GPS coords, timestamps

All tables use `CREATE TABLE IF NOT EXISTS` with foreign keys (`ON DELETE CASCADE`) and covering indexes. Unique index enforces 1:1 stop→execution.

#### Service Layer (`services/delivery/`)
- **`plan_service.py`** (531 lines) — full CRUD for plans, assignments, stops, drivers; Excel import pipeline (parser → validator → preview → confirm)
- **`execution_service.py`** (235 lines) — current stop derivation (first planned/enroute by execution_sequence), advance (planned→arrived→completed), skip, cancel, reorder, insert temp stop, progress statistics
- **`tracking_service.py`** (49 lines) — TTAS GPS wrapper, vehicle plate lookup, position normalization
- **`eta_service.py`** (102 lines) — ORS-based ETA with Haversine fallback, single-leg and multi-stop cumulative calculations
- **`image_service.py`** (124 lines) — upload with auto folder creation (DeliveryPlans/YYYY/MM/DD/Plate/Station/Category/), list, serve, delete with file cleanup

#### REST API (24 endpoints under `/api`, Flask Blueprint)
- `/drivers` — list, create
- `/plans` — CRUD, confirm, import parse, import save
- `/assignments` — CRUD
- `/stops` — CRUD, skip, cancel, reorder, insert
- `/execution` — current, advance, dashboard, progress
- `/eta` — ETA for remaining stops
- `/stops/<id>/images` — list, upload
- `/images/<id>` — serve file, delete

#### Migration Script (`scripts/migrate_to_delivery.py`)
- One-way, idempotent export from legacy `vehicle_trips` into the new delivery schema
- Handles pickup/waypoints/destination → stops, status mapping, vehicle/driver creation
- Safe to re-run (checks for existing migration plans, `--force` to override)

#### Unit Tests (`tests/test_delivery.py` — 31 tests)
| Area | Tests |
|------|-------|
| ETA calculation | 7 (Haversine, ORS success/failure, multi-stop, empty) |
| Stop progression | 7 (advance lifecycle, skip, cancel, auto-advance on complete) |
| Reordering | 6 (reorder, insert temp, execution sequence updates) |
| Image management | 5 (upload, categories, delete removes file, empty, nonexistent) |
| Progress/dashboard | 5 (all planned, partial, skip counts, empty, dashboard) |
| Transactions | 2 (FK rollback, cascade delete) |

### Fixed
- `image_service.py` relative_path now derived from actual file path instead of `datetime.now()` (folder used `plan_date`, path used `now` — mismatch fixed)
- `image_service.py` orphan files cleaned up if DB insert fails after file save
- `execution_service.get_dashboard_data()` reduced from N+1 connections to single connection (inlined current_stop + progress queries)
- Migration script `import json` moved from loop to top-level
- Migration script now sets `PRAGMA foreign_keys = ON`

### Changed
- `app.py` (+9 lines) — registers delivery blueprint, sets `DB_PATH` in app config, calls `init_delivery_tables()`
- No existing routes, functions, or tables modified — legacy system completely undisturbed

### Changed

#### Simplified Scoring (`engine/scorer.py`)
- Reduced from 14 scoring categories to 4: `package_contact` (1000), `x_preference` (200), `floor_contact` (100), `y_balance` (50)
- Removed: wall_contact, face_contact, compactness, stack_quality, vertical_stability, z_preference, rear_proximity, cluster_cohesion, dead_space_quality, load_profile_stability

#### Simplified Candidate Generation (`engine/candidate_points.py`)
- Removed: `settle_package()`, `generate_slide_candidates()`, `generate_floor_anchors()`
- Candidates now come only from origin + right/front/top faces of placed boxes
- `tighten_position()` simplified — no longer needed as a separate pass

#### Simplified Placement Pipeline (`engine/auto_arrange.py`)
- Removed `ColumnStrategy` (only `LargestFirstStrategy` remains)
- Removed: frontier gap penalty, stack ceiling penalty, Y-slide fallback, gap-filling pass, post-placement compaction pipeline, debug instrumentation

#### Simplified Distribution (`engine/distribution.py`)
- Removed: `compact_placements()`, `compact_stacks()`, `fill_frontier_gaps()`, `fill_interior_gaps()`, `_try_local_rearrangement()`, `balance_fleet_profiles()`
- Only `distribute_across_vehicles()` and `reassign_load_sequences()` remain

#### Simplified Profiles (`engine/profile.py`)
- Removed repair/compaction-related fields; only name, candidate_limit, tighten_step_mm remain

#### Simplified Routes (`routes.py`)
- Default strategy changed from `"column"` to `"largest_first"`
- Removed all repair, consolidation, balance, compaction pipeline calls and imports

#### Simplified Internal Engine (`engines/internal/engine.py`)
- Removed `optimize_layout()`, `consolidate_fleet()` calls
- Only `distribute_across_vehicles()` remains

#### Package Sort Order
- Changed from `volume DESC, weight DESC, footprint DESC` to `(non-stackable first), volume DESC, weight DESC, footprint DESC`
- Non-stackable packages now always sort before stackable ones

### Removed
- `engine/repair.py` (386 lines) — destroy-and-repair optimizer
- `engine/consolidation.py` (197 lines) — near-empty vehicle elimination
- `engine/dead_space.py` (319 lines) — future-packability estimation
- `engine/frontier.py` (106 lines) — 1D Y-strip frontier tracker
- Total: 1,008 lines removed from engine; engine package reduced 51% (5,958 → 2,922 lines)

### Consolidated Test Files
- **Unified 19 script files** into `tests/test_all.py` with 5 subcommands and 16 modes:
  - `benchmark`: distribution, floor_contact, real_data
  - `diagnose`: general, kbf_lc900, candidates, stacking
  - `debug`: py3dbp, stats, validation, vehicles
  - `query`: vehicles, tables, db, shipments
  - `instrument`: trace, bug-trace
- Deleted 17 files from `scripts/`; moved `debug_arrange.py` and `merge_duplicate_vehicles.py` to `tests/`
- All output now saves to `reports/{cmd}_{mode}_{timestamp}.txt`

### Removed Modules (Deleted)
- `engine/repair.py` — destroy-and-repair LNS optimizer
- `engine/consolidation.py` — near-empty vehicle elimination
- `engine/dead_space.py` — future-packability estimation
- `engine/frontier.py` — 1D Y-strip frontier tracker
- `scripts/` directory (17 files unified into `tests/test_all.py`)

## 2026-07-22 — Frontier-Based Gap Prevention, Gap-Filling Pass, Debug Instrumentation

### Added

#### FrontierTracker (`engine/frontier.py`)
- New module implementing a 1D Y-strip frontier for gap-aware placement:
  - `get_frontier_at(y)` — returns the maximum X (depth) of the packed front at a given Y, within a Y-strip of configurable `strip_width_mm` (default 200–250 mm)
  - `gap_distance(x, y, z, w)` — measures how far a candidate is from the frontier at its Y-strip; positive = ahead of frontier, negative = behind (in a gap)
  - `gap_ratio(x, y, z, w)` — gap_distance normalized by `container.length`
  - `update()` / `update_from_placement()` / `reset()` — frontier state management
- Integrated into `LargestFirstStrategy.arrange()` and `ColumnStrategy.arrange()`:
  - Gap penalty during candidate scoring: `-min(gap_distance × (0.5 + gap_ratio × 0.5), 500)`
  - Y-slide fallback after frontier check

#### Frontier Gap-Filling Pass (`fill_frontier_gaps` in `engine/distribution.py`)
- Post-placement pass that detects frontier gaps (packages with xmin > frontier at their Y-strip)
- For each gapped package: tries `settle_package()` first (analytical O(K)), falls back to `tighten_position()` only when settle gives no improvement
- Guard: only re-places when `tx >= pl.x - 1.0` (meaningful forward improvement ≥ 1 mm)
- Replaces `fill_interior_gaps` calls in compaction pipelines
- Immediately updates frontier after each re-placement

#### Detailed Debug Instrumentation (`engine/auto_arrange.py`)
- `all_candidate_details` per debug entry captures every candidate evaluated:
  - Input position, tightened position, validity, raw score, gap penalty, stack ceiling penalty, full breakdown, adjusted score
- `slide_details` per debug entry tracks Y-slide fallback candidates

#### `scripts/debug_arrange.py`
- New comprehensive debugger that logs every step/decision for every package:
  - Sorting order, per-package all-candidate decision log, frontier state, gap check (adjacent with Y-overlap), per-package frontier gap analysis, settle/tighten test, compaction steps, position changes, validation
  - Saves to `reports/debug_<scenario>_<timestamp>.txt`
- Scenarios: `kbf_lc900`, `mixed`, `column-test`, `real` (full 46-package real shipment)
- `--full` flag for per-strip breakdown
- `real` scenario: 46 packages placed, score 100.0, valid, ~10 000-line report

### Fixed

#### Duplicate-Name Bug in Gap-Filling Pass
- `engine/auto_arrange.py`: `list.remove(x)` crashes when `x` appears multiple times in `unplaced_packages`
- Fixed: replaced with `Counter` from `collections` for count-based tracking

### Removed
- `tests/test_auto_arrange.py` — deleted (63 test cases, called "useless")

---

## 2026-07-21 — Load Profile Stability Metric Fix, Floor Anchors, Local Rearrangement, Benchmark Correction

### Changed

#### Load Profile Stability Metric
- **`engine/scorer.py::_score_load_profile_stability()`** — metric fixed from `sum(adjacent_diffs) / ((n-1) × H)` to `max_step / container.height`. Old metric had ~0.1 weighted-point range (negligible) and ranked concentrated towers better than gradual staircases. New metric creates a 4.15 point gap (59× improvement), correctly penalising tall isolated stacks.

#### Floor Anchor Candidates
- **`engine/candidate_points.py::generate_floor_anchors()`** — new function that finds the largest empty floor rectangles via Y-boundary sweep (O(N²) with N ≤ floor packages), generating front/center/rear positions for the top 2 regions. Augments (not replaces) extreme-point candidates to help fill empty floor regions.

#### Tighten Position
- **`engine/candidate_points.py::tighten_position()`** — new function that snaps a candidate back to its nearest extreme point after rotation, fixing candidate drift from floor anchor and right-wall candidates.

#### Top-K Tighten Architecture
- **`engine/distribution.py::find_best_for_pkg()`** — scores all candidates, tightens the top 5, then re-scores before picking the best. Replaces "tighten everything" approach that caused 20–50× runtime blowup. ~1.5–2× overhead vs original.
- **`engine/auto_arrange.py::LargestFirstStrategy.arrange()`** — same top-K tighten applied to both main and gap-filling passes.

#### Local Rearrangement
- **`engine/distribution.py::_try_local_rearrangement()`** — when the only feasible candidate is a stack, identifies which floor packages geometrically block the floor candidate (clearance-aware AABB overlap), removes ≤3, places the current package, re-places blockers, and only accepts if floor score > stack score. Uses full snapshot/restore via `import_placements` for safe rollback. Recursion depth = max 1.
- **Floor-count guard** — rearrangement only fires when `n_floor ≤ 10` to avoid O(N²) overhead on densely-packed large containers (prevented 3× distribution blowup from 17.8s→54.7s).
- `_snapshot_placements()` / `_restore_placements()` — helpers for clean rollback.
- `_find_blocking_floor_packages()` — calculates which floor packages block a candidate position.
- `_best_floor_candidate()` — picks the best floor-level position for a given package.

#### Repair Optimizer
- **`engine/repair.py::_is_better()`** priority 3 flipped from `n_floor > o_floor` to `n_floor < o_floor` (prefer smaller empty floor regions). No impact on current dataset (always returns `Improved: False`).

#### Benchmark Correction
- **Old benchmark was wrong**: loaded 31 DB rows with no quantity expansion (vs web UI 46 instances from PACKAGES with qty). Also omitted `cargo_length_mm`/`cargo_width_mm`/`cargo_height_mm`/`payload_kg` from vinfo dict, so `_vehicle_capacity()` returned 0 for all and vehicles sorted in plate-number order (smallest first) instead of largest-first by capacity.
- **Corrected benchmark**: 46 packages, 32 vehicles sorted by `volume × max(payload, 1)` descending. Largest = V38/V39 (9700×2370×2300mm, 52.9m³). Results: 2 vehicles (was 5), 12 stacks baseline → 9 with rearrangement. Repair remains a no-op (Improved: False).

### Added
- `_count_stacks()` and `_per_vehicle_empty_floor()` helpers in `engine/repair.py` (diagnostic utilities).
- `scripts/benchmark_final.py` — corrected 46-package 3-config benchmark (Run A: baseline, Run B: rearrangement, Run C: rearrangement+repair).

---

## 2026-07-20 — Largest-Vehicle-First Fleet Distribution, Strict Unstackable Enforcement, Door-Aware Animation

### Changed

#### Fleet Distribution: Best-Fit Decreasing → Largest-Vehicle-First
- **`engine/distribution.py:176`** — rewritten `distribute_across_vehicles()`:
  - Sorts vehicles by combined capacity (volume_mm³ × payload_kg) descending
  - For each vehicle (biggest → smallest), tries to place all remaining packages
  - Leftovers roll over to the next (smaller) vehicle
  - Removed waste estimation (`estimate_remaining_after` no longer called)
  - Removed Phase 3 rear-door redirect (no longer needed)
  - Removed per-package BFD cross-vehicle comparison

#### Package Sort: Priority-Grouped → Strict Volume Descending
- **`engine/distribution.py:192-194`**: removed `_pkg_priority()` grouping; sort is now purely `-volume`
- **`engine/auto_arrange.py:48-51`**: same change — no more non-stackable-before-stackable grouping
- Placement sequence within each vehicle is now strictly biggest-first, eliminating `big → small → big → small` patterns

#### Strict Unstackable Enforcement
- **`engine/support.py:60-63`**: added top-package check in `_check_stacking_rules()` — an unstackable package (`stacking_mode=NONE`) cannot be placed on top of another package
- **`engine/package.py:33-35`**: added `__post_init__` to `Package` dataclass — auto-derives `stacking_mode` from `stackable`:
  ```python
  if not self.stackable and self.stacking_mode == StackingMode.NORMAL:
      self.stacking_mode = StackingMode.NONE
  ```
  Previously only `Package.from_dict()` derived `stacking_mode` correctly; all direct `Package(...)` construction sites left it at the default `NORMAL`, so `stackable=False` had no effect on stacking validation.

#### Door-Used Propagation (Animation)
- **`engine/placement.py:14`**: added `door_used: str = "rear"` to `Placement` dataclass
- **`engine/validation.py:27`**: added `door_used: str = "rear"` to `ValidationResult`
- **`engine/validation.py:153`**: captures `door_used` from `check_door_sweep()` result
- **`engine/planner.py:60`**: passes `result.door_used` to `append_placement()`
- **`engine/state.py:63`**: stores `door_used` on the `Placement`
- **`routes.py:718`**: includes `door_used` in the frontend placement dict
- **`static/js/truck-load-planner.js:3126`**: reads `placement.door_used` and selects entry point:
  - `"rear"` → `(d.len + pl, y, z)`
  - `"side_right"` → `(x, y, d.wid + pw)`
  - `"side_left"` → `(x, y, -pw)`

### Removed
- `estimate_remaining_after()` is no longer called by `distribute_across_vehicles` (kept for backward compat)
- BFD waste estimation logic
- Phase 3 rear-door redirect logic

---

## 2026-07-19 — Dead Space Quality (Future-Packability Estimation)

### Added

#### Dead Space Quality Scoring
- **`engine/dead_space.py`** — new module implementing future-packability estimation:
  - `compute_dead_space_quality()` — estimates how usable the remaining free space will be after placing a package
  - **Gap-ray heuristic**: for each of 6 faces, measures distance to nearest obstacle (package or wall) in the outward direction — O(faces × nearby_packages)
  - **Flush-face exclusion**: faces with gap ≤ 10mm are skipped (cannot create dead space)
  - **Difficulty-weighted reference set**: selects the 3 hardest remaining packages (by volume × aspect ratio); harder packages dominate the per-face score
  - **Continuous scoring**: product of clamped sorted-dimension ratios — smooth 0–1, no binary fit/no-fit
  - **Area-weighted**: larger faces contribute more to the final quality score
  - **Spatial index support**: uses `query_aabb_fn` when available for O(nearby) instead of O(all_placements)
- **`dead_space_quality: 10`** added to `SCORING_WEIGHTS` in `engine/scorer.py` (total now 130, clamped to 100)
- `remaining_packages` parameter threaded through `Planner.score_placement()` → `Planner.evaluate_position()` → `scorer.score_placement()`
- `LargestFirstStrategy.arrange()` in `auto_arrange.py` now passes `sorted_packages[i+1:]` as remaining packages at both main-candidate and Y-slide evaluation sites
- `_find_best_for_pkg()` in `routes.py` now accepts and forwards `remaining_pkgs` for all 3 phases

### Changed
- `SCORING_WEIGHTS` total increased from 120 to 130 to accommodate `dead_space_quality: 10`
- `score_placement()` and `Planner.score_placement()` accept optional `remaining_packages` parameter (defaults to None → no dead-space penalty)
- `test_weights_are_configurable` updated for new weight key and sum (120→130)
- `test_score_placement_returns_placementscore` updated to assert `dead_space_quality` in breakdown

---

## 2026-07-19 — Y-Balance, X-Preference, Rear-Proximity Scoring; Combined-Support Stacking; Rear-Door Routing; Y-Slide Fallback

### Added

#### Weight-Balance Scoring (Y-Balance)
- **`_score_y_balance()`** in `engine/scorer.py` — computes Y-centre-of-gravity of all packages (existing + candidate) using actual `weight_kg` values; rewards positions that bring the COG closer to `container.width / 2`
- Weight `y_balance: 15` — new scoring factor for even left-right weight distribution
- Reduced `wall_contact` 15→10 and `z_preference` 20→10 to accommodate

#### X-Preference & Rear-Proximity Scoring
- **`_score_x_preference()`** — rewards low x values (deep placement near front wall); weight 5
- **`_score_rear_proximity()`** — penalizes packages whose rear edge is within 8% (min 300mm) of the rear door; weight 10
- Together these create a strong gradient pushing packages toward the front wall while avoiding the rear door
- Reduced `package_contact` 20→15 and `compactness` 10→5 to accommodate

#### Combined-Support Stacking Model
- **`engine/support.py`** — replaced the per-package footprint area check with a combined-support model:
  - Grid-samples candidate XY footprint (20×20); counts samples inside **any** below package's AABB (union of overlap regions)
  - Requires coverage ≥ 90% of candidate footprint (configurable via `support_threshold` parameter)
  - **Centre-of-mass guard**: candidate's XY footprint centre must lie within at least one below package's XY extent — prevents unstable bridging/overhang
  - Allows realistic stacking across multiple adjacent packages (e.g., wide box on two narrower boxes side-by-side)

#### Right-Wall Candidate
- Added `(0, container.width - pkg.width - clearance, 0)` as a base candidate in both `auto_arrange.py` `arrange()` and `routes.py` `_find_best_for_pkg()`
- Gives the scorer a balanced starting point instead of always biasing to `y=0`

#### Y-Slide Fallback
- **`generate_slide_candidates()`** in `engine/candidate_points.py` — when a package fails all extreme-point candidates, slides each base candidate left/right in Y by steps of 100mm (up to 3 steps each direction)
- Integrated into both `LargestFirstStrategy.arrange()` and `_find_best_for_pkg()` in `routes.py`

#### Phase 3 — Rear-Door Redirect (Vehicle Distribution)
- **`_distribute_across_vehicles()`** now includes Phase 3: if the best position touches the rear wall (`xmax ≥ container.length`), redirect the package to the last vehicle unconditionally (if it can accommodate)
- Fills the last vehicle's unused space with packages that would be unloaded first

#### Clearance Margin
- `clearance_mm: float = 10.0` field added to `Package` dataclass (`engine/package.py`)
- `AABB.from_dimensions()` accepts optionally inflated AABBs via `clearance` parameter (`engine/geometry.py`)
- Spatial AABBs in `state.py` store inflated AABBs; extreme points offset by `+2*clearance`
- Boundary check uses actual AABB; collision uses inflated AABB; support uses actual AABB

### Changed

#### Candidate Priority — Removed Y Bias
- Factor 5 in `_candidate_priority()` changed from origin-proximity (biased to `y=0`) to front-center proximity (no Y bias): `dist = sqrt(x² + (y − width/2)² + z²)`
- Packages are no longer pulled toward the left wall; scorer's `y_balance` handles left-right distribution

#### Scoring Weights Rebalanced
| Category | Old | New |
|----------|-----|-----|
| floor_contact | 25 | 25 |
| wall_contact | 15 | 10 |
| package_contact | 20 | 15 |
| face_contact | 10 | 10 |
| compactness | 10 | 5 |
| stack_quality | 5 | 5 |
| vertical_stability | 10 | 10 |
| z_preference | 20 | 10 |
| x_preference | — | 5 |
| rear_proximity | — | 10 |
| y_balance | — | 15 |
| **Total** | **115** | **120** |

### Fixed
- `_find_best_for_pkg()` now converts `candidates` to a mutable list before inserting the right-wall candidate
- `test_score_placement_corner_best` updated — y_balance makes centre positions competitive with corners
- `test_weights_are_configurable` updated for new weight keys and sum

---

## 2026-07-19 — Best-Fit Decreasing, Candidate Priority, Stacking Defaults, 3D Fullscreen & Labels

### Added

#### Best-Fit Decreasing (Vehicle Selection)
- **`_distribute_across_vehicles()`** in `routes.py` changed from First-Fit Decreasing to **Best-Fit Decreasing (BFD)**:
  - New `_estimate_remaining_after()` helper computes vehicle fullness after placement as three ratios (volume%, floor%, payload%)
  - Primary comparator: sum of three remaining ratios (lower = tighter fit → better)
  - Secondary comparator (tiebreaker): placement score
  - Previously used a blended weighted score; now uses clean two-tier comparison
  - BFD picks the vehicle that will be fullest after accepting the package, rather than the first that fits

#### Candidate Priority (Pre-Validation Ranking)
- **`_candidate_priority()`** in `routes.py` — module-level function that ranks extreme-point candidate positions BEFORE expensive validation:
  - Five factors scored independently (total 0–100):
    - **Touching surfaces** (0–60): counts how many container walls (rear, left, right, floor) the candidate touches; more touching = higher score
    - **Z-height** (0–15): inverse of z-start; lower positions score higher
    - **Wall-contact area** (0–15): package footprint edge length touching container walls, normalised to max possible; rewards wall-hugging
    - **Back-to-front loading** (0–20): prefers low X (rear wall); score drops linearly as X increases; naturally enforces rear-first placement without hard constraints
    - **Origin proximity** (0–10): distance from (0,0,0); closer is better (avoids floating islands)
  - `_find_best_for_pkg()` expands candidates with both rotations, then sorts them by priority descending
  - Validation loop can early-exit as soon as a high-score candidate is validated (since highest-priority + best-scoring so far are checked first)
  - Over 2× reduction in validation calls vs brute-force order

#### Back-to-Front Loading
- Back-to-front priority factor integrated into `_candidate_priority()` (score 0–20)
- No explicit ordering constraint — packages naturally load toward the front (high X) as the rear fills, guided by the priority rank
- Replaces need for a separate `load_sequence` sort on the frontend

#### 3D View Toolbar & Fullscreen
- **`#tlp-3d-toolbar`** with step animation controls (prev/next/play/end/counter) inside the 3D container; visibility toggled by `_sync3DToolbar()`
- **Fullscreen toggle** via `#tlp-3d-btn-fullscreen`: adds `.fullscreen` CSS class (fixed viewport cover, z-index 9999, no-resize) — uses CSS positioning, not the native Fullscreen API
- **Toolbar opacity**: `0` in normal state, `1` on hover or when `.fullscreen`
- **Package labels**: `_makeTextSprite()` creates a THREE.Sprite with the package name rendered on a canvas; displayed 30px above each package in `update3DScene()` and `_stepShowPermanent()`
- **Keyboard shortcuts**: `F` toggles fullscreen; `Escape` exits fullscreen (along with existing deselect)

### Changed

#### Stacking Defaults (`stackable`)
- **`routes.py:830`**: inline-packages branch of `_get_packages_from_request` hardcoded `stackable=True`; now reads dict key
- **`session.py:49`**: `_from_legacy_dict` default changed from `1` (True) → `0` (False)
- **`engine/planner.py:359,372`**: `load_legacy_placements` default changed from `1` (True) → `0` (False)
- **`routes.py:772`**: `_build_placement_dict` now exports both `"stackable"` and `"allow_stacking"` keys for frontend compatibility

#### Candidate Point Rotation
- **`engine/candidate_points.py:28–34`**: standalone `generate_candidate_points` now swaps length/width for rotation 90/270 (was using raw `length_mm`/`width_mm` unchanged)

#### Door Sweep Always Enabled
- **`engine/validation.py:87–98`**: when no door features configured, defaults to `{"rear_door": {"width_mm": container.width, "height_mm": container.height}}` so the sweep check always runs

#### Step Animation Buttons Persist
- `_stepEndMode()` accepts optional `resetStep` param (default `true`); completion paths (`stepEnd`, auto-play finish) pass `false` so toolbar buttons remain visible after animation ends

### Fixed

- **Fullscreen toolbar sync**: `toggle3DFullscreen()` now calls `_sync3DToolbar()` so step buttons appear on entering fullscreen
- **`update3DScene()` step-mode guard**: calls `_stepEndMode(false)` instead of `_stepEndMode()` to prevent hiding buttons on scene refresh
- **Back view left/right inversion**: the 2D back view now correctly renders the container from the rear perspective looking forward — the left wall (Y=0) appears on the right side of the canvas, matching real-world orientation. Updated `_drawPackages`, `_focusOnPackage`, drag-and-drop, `_showPreview`, `_throttledValidate`, `_onDrop`, and `_quickValidate` to consistently flip the X axis for the back view.

---

## 2026-07-18 — Multi-Vehicle Distribution, Door Access Validation, Step Animation

### Added

#### Multi-Vehicle Distribution (First-Fit Decreasing)
- **`_distribute_across_vehicles()`** in `routes.py` rewritten to use **First-Fit Decreasing** bin packing:
  - Maintains `active_indices` — vehicles that already hold packages
  - **Phase 1**: tries active vehicles first (fills them to capacity)
  - **Phase 2**: only opens a new vehicle when no active one can accommodate
  - Result: minimises total vehicle count naturally
- Shared candidate evaluation extracted into `_find_best_for_pkg()` helper
- `new_active` variable prevents premature marking during Phase 2 iteration

#### Door Access Validation (`engine/access.py` — new module)
- **`check_rear_door()`**: validates package cross-section fits through rear door opening AND sweep volume from rear wall to position is clear of placed packages
- **`check_side_door()`**: validates cross-section fits side door, package X-range overlaps door position, sweep from side wall is clear (both left and right walls)
- **`check_door_access()`**: orchestrator — tries rear door → side_right → side_left, returns `door_used` or failure reason
- Integrated into `validate_placement()` — every candidate position in auto-arrange is validated against door access

#### Weight Constraint in Stacking (`engine/support.py`)
- **Rule 5**: top package must be lighter than every package directly below it
- `check_support()` now accepts `package` parameter for weight comparison
- Updated `validation.py` and `planner.py` to pass package to support check

#### Step Animation (Frontend)
- **Fly-in animation**: each package starts outside the rear door (`x = container.length + pl`) and slides into its final position over 500ms with cubic ease-out
- Driven by `requestAnimationFrame` inside `_animate3D()` — mesh position is interpolated via `lerpVectors`
- Step state tracked separately (`_stepPermanentPkgs[]`, `_stepAnimState`) to avoid conflicts with `update3DScene()`
- Auto-cleanup: step mode ends and scene rebuilds when complete or on normal `update3DScene()` call

#### Step UI Controls
- **◀ Prev**: go back one step, re-show all previous packages
- **0/15** counter: current step / total
- **▶ Next**: advance one step (animate next package flying in)
- **▶▶ Play**: auto-play all steps sequentially (700ms per package)
- **⏭ End**: show all packages immediately, exit step mode

#### Arrange Results Panel
- New **Arrange Results** section in left sidebar after auto-arrange
- Lists every vehicle that received packages with its count
- Click any vehicle to switch the viewer to its placements and start step animation
- Auto-enables 3D view if not already on

### Changed
- **Auto-arrange always uses multi-vehicle distribution** — removed `vehicle_id` from payload; the backend distributes across all vehicles with container configs
- **`update3DScene()`**: accepts optional `skipPackages` boolean for step animation mode
- **`_getContainerDims()` fallback**: now handles `currentContainer` being null by reading from `currentVehicle` directly

### Fixed
- **Mesh leak in step animation end**: `stepEnd()` now calls `_stepClearPermanent()` before exiting to properly dispose Three.js meshes
- **Null scene guard in `_stepClearPermanent()`**: checks `this._threeScene` before attempting `scene.remove()`
- **Animation deadlock**: `_stepNext()` fallback path handles case where `_stepCreateAnimMesh()` returns null (shows package immediately instead of hanging)

---

## 2026-07-18 — Phase 4: Auto Arrange Engine (v1)

### Added
- `engine/auto_arrange.py` — Strategy-based automatic package placement
- `LargestFirstStrategy`: non-stackable first, volume/footprint/weight desc, 0/90° rotations, early-exit at 99.99+
- `Planner.auto_arrange()`, `Planner.validate_position()`
- `POST /api/tlp/auto-arrange` endpoint
- UI toolbar button with `app.autoArrange()`
- Multi-vehicle mode when `vehicle_id` is omitted (greedy per-package best-fit)

### Fixed
- Package list not appearing on first load (tab default was "Placed")
- Auto Arrange required a selected vehicle (now supports multi-vehicle)
- `savePackage()` ignored HTTP errors

---

## 2026-07-18 — Phase 3: Placement Evaluation Engine

- `PlacementScore` dataclass with `total`, `breakdown`, `warnings`, `metadata`
- `SCORING_WEIGHTS` (totals 100): floor_contact 25, wall_contact 15, package_contact 20, face_contact 10, compactness 10, stack_quality 5, vertical_stability 10, z_preference 20
- 7 isolated scoring functions + `z_preference` (added in later revision)
- `planner.evaluate_position()`, `evaluate_candidates()`, `evaluate_plan()`

---

## 2026-07-18 — Door Rendering Fixes

- Vehicle management rear door scaling fix (geometry_json/geometry fallback)
- TLP 3D rear door width was hardcoded to 50mm; now uses feature geometry
- Added interior floor plane to vehicle management 3D view

---

## 2026-07-18 — Gravity, Stacking & Engine Refinement

- Gravity simulation in side/back views (snap Z to floor or stackable top)
- `engine/support.py` — area-based stacking validation
- `engine/candidate_points.py` — candidate position generator
- `engine/planner.py` — orchestrator with evaluate APIs
- Package create/edit: Allow Stacking checkbox, Quantity input
- Various coordinate/boundary/drag bug fixes

---

## 2026-07-18 — Inline Package Editor & Canvas UX

- Create/edit packages directly in sidebar
- Weight enforcement on drag-and-drop
- Canvas pan, rotation buttons, undo/redo
- Package centering on palette drag, grab offset preservation

---

## 2026-07-13 — Container Fuel, Anomaly Detection, Vehicle Management

- Fuel Efficiency Dashboard (KPIs, chart, refuel log, anomaly highlighting)
- Container Fuel page with partial-tank support
- Anomaly Detection (moving-average baseline + adjustable multiplier)
- Vehicle Management CRUD with vehicle type presets
- Per-vehicle baseline profiles (normal L/100km)
- Refuel log CRUD with modal and CSV export

---

## 2026-07-11 — Refinements

- All efficiency units consistently L/100km
- Day selector for per-day filtering
- Total Spend KPI card
- No-KM row highlighting with ⚠ badge
- Dynamic month population from actual data
