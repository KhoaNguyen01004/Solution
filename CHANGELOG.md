# Changelog

## 2026-07-30 — Truck Load Planner Phase 6: Frontend Fidelity Fixes

Final phase of the 6-phase truck-load-planner improvement plan (Phases 1-5 above). Closes the "is it the algorithm or the UI" question the investigation opened with: the frontend independently recomputed some metrics, misrendered rotated packages in 3D, and let manual edits bypass backend validation entirely — meaning some of what looked like "the algorithm produced instability" was actually the UI, not the backend. `static/js/truck-load-planner.js` only.

### Fixed
- **Floor-utilization stat counted every placement, including stacked ones** (`updateStatus()`) — a package stacked on top of another doesn't occupy new floor space, but the client-side calculation summed every placement's footprint regardless of `z`, inflating the floor % once anything was stacked. Volume and weight stats were checked too and are mathematically identical to the backend's `volume_used_pct`/weight sum already (same simple formula, no real divergence) — left as-is rather than force a backend round-trip for numbers that were already correct. Fixed to only count `z === 0` placements, matching `engine/statistics.py::compute_statistics`'s `floor_used_pct` exactly.
- **3D view ignored package rotation** (`update3DScene()`) — the package mesh loop always built box geometry from raw length/width regardless of `rotation`, while the 2D top/side/back views already correctly swap them for 90°/270° (`_drawPackages()`). A validly-placed rotated package rendered with the wrong box extents in 3D only, making a correct backend placement look wrong. Fixed to swap length/width for 90°/270°, matching `_drawPackages()`. Verified in-browser: forced a placement to `rotation: 90` and confirmed via the actual THREE.js mesh geometry that its box dimensions swapped (`1200×1000` vs. an unrotated same-type package's `1000×1200`) and repositioned correctly.
- **Manual drag/rotate edits were never re-validated against the backend** (`_validateAllPlacements()`) — the method was a literal stub (comment: "For comprehensive validation, we'd call the batch endpoint / For now, just update the UI based on status calculation") that only re-ran the client-only checklist, which has no support/stacking check at all. A dispatcher could drag a package into an unsupported or otherwise backend-invalid position and the UI would still show "All checks passed." No new backend endpoint was needed — wired to the existing single-placement `/api/tlp/session/validate` route (already used for new-package-from-palette drops), called with the moved placement's new position against the rest of the plan. `updateValidationUI(result)`'s `result` parameter existed but was dead code (never passed by any caller) — now actually used: when the backend rejects a placement, the status bar shows its real reason instead of just "Issues detected".
  - Ordering fix found during this same change: `updateStatus()` calls its own no-arg `updateValidationUI()` internally, so the backend-informed call had to run *after* it in the `dragend` handler, or it would be immediately overwritten by the client-only recompute.

### Testing
- Started the dev server (`python app.py`) and drove the actual Truck Load Planner page in-browser against a real fleet vehicle (50E-18463, 13 real packages) rather than a synthetic fixture.
- Auto Arrange: 13/13 placed, all 5 client-side checks passed, no console errors.
- Forced a rotation via the console and confirmed the 3D mesh geometry swap directly (not just visually) — see above.
- Dragged a package into a real collision with a neighbor: validation panel flagged "No collision" ✗ and the status bar showed the actual backend reason ("Collision with nearby package") pulled through `updateValidationUI(result)` — confirms the stub replacement works end-to-end, not just in isolation. Undid the drag; re-confirmed "All checks passed" and zero console errors throughout.
- One pre-existing console exception (`filterPackages`, `this.placements is not iterable`, fires during `init()` before a vehicle is selected) was observed but not touched — present before this phase's changes and outside its scope.
- Backend suite unaffected by this phase (no Python changes): `pytest tests/test_scorer.py tests/test_auto_arrange_e2e.py -v` — 31/31 passing.

## 2026-07-30 — Truck Load Planner Phase 5: Regression Test Coverage (+ 2 stacking bugs it caught)

Phase 5 of the 6-phase truck-load-planner improvement plan (Phases 1-4 above). `tests/test_scorer.py`'s 26 tests are real but narrow (0-2 packages, unit-level); `tests/test_all.py` matches pytest's `test_*.py` discovery but contains zero `test_*` functions, so it silently contributes nothing despite having real end-to-end logic. Neither covered utilization, stacking correctness, or multi-vehicle truck-count behavior at realistic scale — exactly the properties Phases 1-4 changed. New file: `tests/test_auto_arrange_e2e.py`, 5 tests, deterministic (fixed dimensions, no randomness), ~3.4s total.

### Fixed (found while writing these tests, not part of the original plan)
Writing a real end-to-end stacking test — with no explicit `max_stack_layers` set on any package, the common case — finally exercised the Phase 1 hard-cap path under realistic conditions and surfaced two bugs in it:
- **The Phase 1 hard cap didn't actually limit tower height.** `max_stack_layers`/`_count_above` enforces *breadth* (how many separate packages can share one base's top surface), not *depth* — a linear single-file column never has more than one package directly on any given package, so the breadth check can never block it from growing. A tall single-column test towered until it hit the container's physical height boundary, not the intended cap (16 packages stacked in a 5000mm-tall container before this fix). Added `_tower_depth()` and a real column-depth check in `check_support` — an actual hard constraint on how many packages deep a single-file stack can go, independent of the breadth check.
- **`_count_above` wasn't scoped to XY overlap with the specific base package** — it counted *any* placement in the entire plan sharing the same Z-height, not ones actually stacked on that base. A 2000-candidate check found this was mostly dormant before Phase 1 (only triggered for packages with an explicit non-zero `max_stack_layers`, which is rare), but Phase 1's fallback made it load-bearing for the ~100% of packages that don't set one — meaning it could reject a valid stack because an unrelated package happened to share its height elsewhere in the container. Fixed to require actual XY overlap with the base, matching its docstring's original intent. (A related bug in `check_support`'s "packages directly below" collection has the same root cause but was deliberately left alone during Phase 3 — see that phase's entry — since it wasn't something this session's changes newly activated.)

### Added
- `test_single_vehicle_realistic_shipment_all_placed_with_reasonable_utilization` — 20-package fixed shipment, asserts full placement and a utilization floor (catches a catastrophic regression, not tuned to an exact number).
- `test_stacking_used_when_floor_alone_is_insufficient` — a scenario sized so floor space alone can't fit everything; asserts stacking is actually used.
- `test_stack_depth_hard_cap_is_enforced` — the tall single-column scenario above; asserts no column exceeds `_SYSTEM_MAX_STACK_LAYERS`. Would have caught the depth-cap bug fixed above.
- `test_distribute_across_vehicles_prefers_single_smallest_fitting_truck` — small shipment, asserts only the smallest van gets used (Phase 4's single-truck preference).
- `test_distribute_across_vehicles_minimizes_truck_count_for_multi_truck_shipment` — a shipment sized to genuinely need multiple vehicles; asserts the two smallest vans are never touched. Would have caught a regression back to Phase 4's fixed smallest-first fallback.

### Testing
- `pytest tests/test_scorer.py tests/test_auto_arrange_e2e.py -v` — 31/31 passing, 3.66s total.
- Test parameters (package/container dimensions, counts) were empirically calibrated against the real algorithm rather than computed from theoretical volume — real packing efficiency for large-relative-to-container boxes came in well under naive volume-ratio estimates during calibration, which is itself a useful data point for anyone tuning `usable_space`/candidate generation further.

## 2026-07-30 — Truck Load Planner Phase 4: Vehicle Candidate Selection to Minimize Truck Count

Phase 4 of the 6-phase truck-load-planner improvement plan (Phases 1-3 above). Prompted by a scope addition: fixing per-truck packing quality doesn't help if the system picks more/larger trucks than necessary for a shipment — more trucks means higher operating cost. While investigating, found uncommitted, untracked WIP already sitting in the working tree (`engine/vehicle_selection.py`, wired live as the default via `distribution.py`) attempting exactly this, with two real defects fixed here rather than reverted (per direction, treated as scratch — structure kept, logic redesigned).

### Fixed
- **Multi-truck fallback filled small vehicles before large ones** (`engine/vehicle_selection.py::SmallestVehicleThatFitsStrategy`) — when no single vehicle could hold an entire shipment, the fallback reused ascending (smallest-first) order for the incremental multi-vehicle loop, which tends to *increase* the number of trucks needed compared to largest-first. Now falls back to descending (largest-first) order; the placement loop's existing `if not remaining_pkgs: break` naturally stops recruiting more vehicles once everything is placed, so this is enough to minimize truck count without needing a separate capacity-estimation step.
- **Single-vehicle-fits-all probe ran the full 15-pass `optimized` strategy per candidate vehicle** before any real placement decision — now probes with a single fast pass (`largest_first`) instead, only spending the expensive `optimized` pass once, on the vehicle that already proved feasible, to refine the final layout.
- **Added a cheap feasibility prefilter** (`_cheap_could_fit_all`) — total package volume/weight vs. vehicle capacity, and each package's footprint (with rotation) vs. cargo cross-section — to skip an arrangement attempt against a vehicle that obviously can't work, before spending any real placement cost on it.
- **Consolidated the duplicated per-vehicle placement loop** (`engine/distribution.py::distribute_across_vehicles`) — it previously maintained a second, independently-written copy of the single-vehicle path's placement loop (`find_best_for_pkg` + inline `place_package` calls). Now delegates to the same `auto_arrange.py::_run_ordered_pass` pipeline the single-vehicle strategies use, so scoring/stacking fixes (Phases 1-2) and performance fixes (Phase 3) apply identically to both paths instead of needing to be ported twice. `find_best_for_pkg` itself is left in place (unused internally now, but still part of the module's public surface — imported by `routes.py`).

### Fixed during verification (not part of the original plan, found while testing)
- **Duplicate placement bug**: the refinement re-run (`largest_first` probe succeeds → re-run `optimized` for a better layout) initially called `auto_arrange` a second time on the *already-populated* planner without resetting it first. `OptimizedStrategy` captures "already placed" as its baseline and adds new placements on top of it — so the second call placed every package a second time at new positions instead of refining the first placement (an 8-package test shipment came back with `placed=16`). Fixed by resetting the planner to its true empty baseline (`planner.import_plan(initial_states[...])`) before the refinement call. Caught by a small functional verification script, not the unit test suite — none of the 26 existing tests exercise this multi-call path.

### Testing
- `pytest tests/test_scorer.py -v` — 26/26 passing.
- Small functional scripts (not the full multi-seed sweep, per direction to avoid slow verification loops going forward): an 8-package shipment sized to fit one small van correctly used only that van (1 truck, not falling back to a larger default); a 60-package shipment across a 6-vehicle mixed fleet (2 vans, 2 mid trucks, 2 large containers) correctly used only the 2 large containers rather than spreading across smaller trucks, all 60 placed, no failures. Both confirmed against the duplicate-placement bug fix above.
- Not yet cross-checked against a full statistical sweep (Phase 3's lesson: this kind of change benefits from one, but those are slow — deferred to Phase 5's regression suite rather than run ad hoc again this pass).

## 2026-07-30 — Truck Load Planner Phase 3: Performance (reduced scope)

Phase 3 of the 6-phase truck-load-planner improvement plan (Phases 1-2 above). Originally scoped to 3 items; 2 were found unsafe/out-of-reach for a performance-only pass during implementation and deferred rather than shipped half-verified.

### Fixed
- **`OptimizedStrategy` discarded the caller's `candidate_limit` on every trial** (`truck_load_planner/engine/auto_arrange.py`) — removed the unconditional `planner._candidate_limit = None` before each of the 15 trials. In practice this only affects requests that explicitly pass `profile=fast` together with `strategy=optimized`, since the default `balanced` profile never sets a limit in the first place (`routes.py`'s `if profile.candidate_limit and ...` guard) — but in that combination, the "fast" profile's speed/quality tradeoff was being silently ignored.

### Attempted and reverted (documented, not shipped)
- **Spatial-index-narrowed `check_support`** — tried routing the "packages directly below" scan through the existing `UniformGrid` spatial index (already used for collision checks) to cut its O(n) scan. A 2000-candidate randomized equivalence check against the un-narrowed version found 167 mismatches: the *original* algorithm matches "below" packages by Z-height alone across the **entire** plan, not scoped to XY proximity — a same-height package anywhere in the container gets checked against stacking-mode/weight/footprint rules before the XY-overlap coverage/centroid check runs later. Narrowing by XY first (the natural way to use the spatial index) silently changed real accept/reject outcomes. This may itself be a latent bug (a valid stack position could be rejected due to a rule conflict with an unrelated package that merely shares its height, not one actually underneath it) worth investigating separately, but fixing it wasn't this pass's goal, and a safety-critical validation path isn't the place for an unplanned behavior change. Reverted; the reasoning is now recorded directly in `engine/support.py::check_support`'s docstring so it isn't re-attempted blind.
- **Spatial-index for `scorer._build_others_with_layers`** — assessed but not attempted. Unlike collision/support, this needs full-plan layer info for every candidate (contact-area scoring checks all 6 faces against every neighbor, not just "nearby" ones), so a grid query alone doesn't reduce it the same way; a real fix would mean maintaining layer info incrementally as packages are placed (similar to how `PlanningState` already maintains extreme points incrementally) rather than recomputing from scratch per candidate — a bigger change than this pass's scope. Deferred.
- **Early-exit tuning for the 15-trial `OptimizedStrategy` sweep** — deferred. Phase 2's verification already showed this specific 15-trial ensemble is sensitive enough to weight/scoring changes that an untested tuning change regressed aggregate placement rate before being caught; without Phase 5's regression suite in place yet, a similar change to trial/exit logic couldn't be verified with confidence in the time available.

### Testing
- `pytest tests/test_scorer.py -v` — 26/26 passing.
- 2000-candidate randomized equivalence check (see above) — used to catch the `check_support` regression before it shipped, not to validate a change that was kept.

## 2026-07-30 — Truck Load Planner Phase 2: Fixed Empty-Space/Utilization Scoring

Phase 2 of the 6-phase truck-load-planner improvement plan (Phase 1: stacking, above). Targets "leaves too much empty space" — `x_position` never actually measured row/slice completion despite being described that way, and `usable_space` (the only real gap-awareness term) could be outweighed by `contact_area` alone.

### Fixed
- **`x_position` was a flat "prefer small X" bias, not a slice-completion signal** (`truck_load_planner/engine/scorer.py`) — replaced with `_score_x_position()`, which rewards a candidate that closes out the container width at the deepest X reached so far (within its own height band, so a stack elsewhere at a different height doesn't count against a floor candidate's row). Weight sign flipped from `-200` to `+200` to match the new higher-is-better raw value; `OptimizedStrategy`'s `dense`/`stack_friendly` profile overrides updated the same way (`-350`/`-300` → `350`/`300`).
- **`usable_space`'s dead-strip penalty could be outweighed by `contact_area` alone** — boosted its base weight from `1` to `3` so a placement that leaves an unusable gap for remaining packages can no longer be rescued by a merely-good contact score.

### Fixed during verification (not part of the original plan, found while testing)
- **Over-eager fix**: initially scaled the `dense`/`stack_friendly` weight-profile `usable_space` overrides proportionally with the base change (`2.0`/`2.5` → `6.0`/`7.5`), reasoning they were multipliers relative to base. A 36-scenario random sweep (mixed container sizes, 25-45 packages each) showed this measurably regressed `OptimizedStrategy`'s aggregate placement rate (966/1293 baseline → 910/1293), even though the standalone `LargestFirstStrategy` improved (586/1293 → 709/1293) as intended. Root cause: those overrides are independently pre-tuned absolute values, not ratios — scaling them re-applied the same fix twice and overweighted `usable_space` within those two profiles. Reverted to the original absolute values (`2.0`/`2.5`); see `SORTING_STRATEGY.md` Section 4 for the note against repeating this mistake.

### Testing
- `pytest tests/test_scorer.py -v` — 26/26 passing throughout.
- Full before/after sweep (3 containers × 12 seeds × 25-45 packages, `largest_first` + `optimized`) comparing pre-Phase-1 baseline against the corrected Phase 1+2 code was run to validate the fix above; a follow-up full-scale re-run to confirm the final numbers after the profile-override correction was interrupted partway (slow — itself evidence for the Phase 3 performance fix) and not completed. A smaller 8-scenario version of the same sweep post-fix showed `optimized` placing 77.9% with the corrected profiles (vs. 70.4% with the over-tuned version), consistent with the fix working, but this wasn't cross-checked against baseline at the same small scale. Flagged for confirmation once Phase 5's regression suite exists; user has opted to verify manually in the meantime rather than block further phases on more sweep runs.

## 2026-07-30 — Truck Load Planner Phase 1: Fixed Stacking Scoring Bias + Hard Height Cap

Root-cause investigation into "auto-arrange is slow, leaves empty space, doesn't stack when it should, and sometimes stacks too high" found `SORTING_STRATEGY.md` was stale (doesn't match `engine/scorer.py`'s actual weights) and that the scoring algorithm itself had two real defects driving the stacking complaints specifically. This is Phase 1 of a 6-phase plan (see `SORTING_STRATEGY.md` for current-state doc, updated in this pass); performance, empty-space, multi-vehicle/fleet-size, regression-test, and frontend-fidelity fixes are tracked as later phases.

### Fixed
- **Scoring categorically favored an empty floor tile over stacking, regardless of context** (`truck_load_planner/engine/scorer.py::_score_stack_and_tower`) — a fresh floor spot scored `stack_level:1000 + tower_height:500 = 1500` raw combined vs. `300 + 300 = 600` for stacking one layer up, a ~900-point gap under the base scoring weights (both terms carry weight `1`). This meant the algorithm would pick available floor space over a stacking position essentially unconditionally, even when stacking was clearly the more space-efficient choice. Rebalanced to `200/100` (floor) vs. `150/60` (layer 1) — floor is still the default tiebreak, but the gap is now small enough that `contact_area`/`usable_space` can tip a genuinely-better stack position into winning. Confirmed on a realistic 20-package/box-truck scenario: stacked-package count went from 2/20 to 5/20 with identical total-placed and utilization (i.e. more stacking, not fewer packages placed).
- **`max_stack_layers=0` was treated as literally unlimited** (`truck_load_planner/engine/support.py::_check_stacking_rules`) — this is documented (README.md, SORTING_STRATEGY.md, DB default) as "no explicit per-package override," not "physically unlimited," but the code had no fallback, so most packages (which don't set an explicit override) had no stack-height ceiling at all beyond the soft `tower_height` scoring penalty. Added `_SYSTEM_MAX_STACK_LAYERS = 3` as a hard cap applied when a package's own `max_stack_layers` is 0; an explicit tighter per-package value still takes precedence.

### Changed
- `SORTING_STRATEGY.md` rewritten to match verified, actual behavior: real `SCORING_WEIGHTS` (6 terms, not the doc's old fabricated 4-term/10000-weight scheme), the real default strategy (`OptimizedStrategy`, not `LargestFirstStrategy`), the real (and currently in-flux) multi-vehicle selection behavior, and corrected the `candidate_limit`/`tighten_step_mm` config-points table (the latter is dead config — `tighten_position()` hardcodes its own step and never reads it).

### Testing
- `pytest tests/test_scorer.py -v` — 26/26 passing (3 tests asserting exact `stack_level`/`tower_height` raw values updated to match the new calibration; no other test changes needed).
- Manual: realistic 20-package/box-truck scenario (before/after comparison via `Planner.auto_arrange`, both `largest_first` and `optimized` strategies) — confirmed increased stacking with no placement-count or utilization regression.
- Noted for Phase 5 (regression test coverage): an artificial exact-fit edge case (container dimensions sized to a knife-edge multiple of package dimensions) showed one fewer package placed under `OptimizedStrategy` post-fix (7/8 vs. 8/8) — traced to tie-breaking sensitivity between the base scoring weights and `OptimizedStrategy`'s pre-existing `dense`/`stack_friendly` weight-profile trials (`auto_arrange.py::_weight_profiles`), not reproduced in the realistic scenario above. Flagged as a case worth covering explicitly once Phase 5's regression suite exists, rather than chased further on a hand-built degenerate scenario now.

## 2026-07-30 — Site-Wide Navigation: Fixed Dispatch Dropdown Bug + Reorganized Structure

Two related complaints: the Dispatch page's nav dropdowns were visually broken, and the overall nav "doesn't follow any rules or best practice." No shared nav template exists anywhere in this app — all ~9 pages fully copy-paste the identical `<nav>` block — so both were investigated and fixed per-file rather than via a new shared-template refactor (explicitly deferred, see below).

### Fixed
- **Dispatch page's nav dropdowns were invisible and unclickable** (`static/css/delivery-dashboard.css`) — `.dashboard-header .header-nav` had an *unguarded* `overflow-x: auto`, while every other page correctly wraps the identical rule in `@media (max-width: 768px)`. Setting `overflow-x` forces the browser to also compute `overflow-y: auto` (CSS spec behavior), so the dropdown menus — `position:absolute`, opening below the nav's ~34px height — were being clipped to zero visible height at *every* screen width, with no scrollbar cue since `scrollbar-width: none` hides it. The click handler fired correctly the whole time; the menu just never rendered. Moved the rule into the existing mobile-only media query, matching every other page.
- **Dispatch was also missing the click-outside-to-close script** (`templates/delivery-dashboard.html`) present on every other page (`document.addEventListener('click', ...)` closing any open `.fleet-dropdown`). Added it.
- Verified live in-browser: dropdown now has real height, is clickable, and closes on an outside click; zero console errors.

### Changed — nav reorganization (applied identically across 9 templates: `index.html`, `delivery-dashboard.html`, `delivery-plan-builder.html`, `manage-trips.html`, `trip-history.html`, `locations.html`, `oil-change.html`, `vehicle-management.html`, `fuel-efficiency.html`)
- **New top-level order**: `Map | Dispatch | Plan Builder | Trips ▾ | Locations | Load Planner | Fleet ▾` (previously `Map | Trips ▾ | Delivery ▾ | Locations | Load Planner | Fleet ▾`).
- **Dispatch promoted to a top-level link** — previously two clicks deep (`Delivery ▾ → Dispatch`) despite being the most-used page.
- **"Delivery ▾" removed** — once Dispatch moved out, it only had one item left (Plan Builder); a one-item dropdown added a click for no reason, so Plan Builder became a bare top-level link instead.
- **"Trips ▾" and "Fleet ▾" kept as dropdowns** — both still group 2-4 genuinely related destinations.
- **Active-page highlighting added** — each page hardcodes `active` (the pre-existing `.btn-nav.active` style, previously unused in this header) on its own corresponding link/button, since there's no shared template to compute this dynamically. For pages under a dropdown (Trip Management/History → Trips ▾; Oil Change/Vehicles/Fuel/Container → Fleet ▾), the dropdown's own button gets the active state. This required removing the inline `background:none;border:none;color:#c9d1d9;` from those specific buttons, since inline styles otherwise override the `.active` class's background.

### Considered and explicitly not done
- **Consolidating the 9 copy-pasted nav blocks into one shared Jinja include/macro** — this is *why* Dispatch could drift and break without affecting any other page in the first place, but the user asked to reorganize the existing per-page pattern first, not take on a template refactor in the same pass.
- **Adding a full nav to `truck-load-planner.html`** — initially assessed as a navigation dead-end, but on inspection it already has a `← Dashboard` back-link (`templates/truck-load-planner.html:1052`); left as-is rather than forcing the full multi-item nav onto a deliberately minimal, focused full-screen tool.

### Testing
- `pytest tests/test_delivery.py` — 49/49 passing (no backend touched).
- Manual: dev server + browser — verified the Dispatch dropdown renders/clicks/closes correctly, verified active-state highlighting on Dispatch (dispatch page), Trips ▾ (manage-trips page), and Fleet ▾ (oil-change page), zero console errors on each.

### Remaining Technical Debt
- The no-shared-template problem itself remains — any future nav change still means editing 9 files by hand. Flagged as a candidate for a later pass if this drift recurs.

## 2026-07-30 — Dispatch Module Post-Phase-3: Plan Auto-Completion + Live Speed Signal

Two of three items from a production-usage planning review (real dispatcher feedback after tagging `dispatch-phase-3`): the dashboard never removed old/test plans because nothing ever transitioned a plan out of `confirmed`/`executing`, and TTAS's live speed telemetry (crawled from the tracking site) was being discarded entirely. A third item (manual "Archive Plan" action) was explicitly deferred pending observation of production usage after auto-completion ships. No schema change, additive only, backward compatible.

### Added
- **Plan auto-completion** (`services/delivery/execution_service.py`) — a plan's `status` now automatically transitions to `completed` once every stop across *every* vehicle assignment under it has reached a terminal state (`completed`/`skipped`/`cancelled`). Wired into the three call sites that produce a terminal stop status: `advance_stop()`'s `arrived→completed` branch, and `_update_execution()` (used by both `skip_stop()`/`cancel_stop()`) — the latter only runs the (more expensive) full-plan check when the status being written is itself terminal. Uses the `completed` value the schema already documents for `delivery_plans.status`; no migration needed.
  - **Safeguard**: `insert_temp_stop()` now reverts a plan from `completed` back to `executing` if a new pending stop is added to it — otherwise a dispatcher inserting a stop into an already-auto-completed plan would silently hide that pending work from the dashboard, which would be a worse bug than the one being fixed.
- **Live speed as a supplementary signal only** (`services/delivery/tracking_service.py::normalize_gps_position()`) — TTAS's raw `speed_status` is Vietnamese status text (e.g. "Chạy 42km/h"), not a clean number, exactly as flagged before implementation. Added `_parse_speed_kmh()`, a defensive regex extraction (mirroring the one already proven in `app/routes/trips.py`, not duplicating its exact behavior — this one returns `None` rather than defaulting to `0` when nothing numeric is found, since "unknown" and "confirmed stopped" are different facts). The new `speed_kmh` field is additive on the existing flat GPS dict — by design, this flat/`.get()`-based shape already accommodates future telemetry (e.g. `heading`) without another contract change, so no restructuring was needed to satisfy that ask.
  - **Explicitly not used for ETA or routing** — the existing ORS route-based ETA (Phase 2) remains the sole ETA authority. Instantaneous `distance ÷ speed` is a known bad pattern (a vehicle stopped at a red light would read speed=0 → ETA→∞).
  - Surfaced in the vehicle info bar (`#vibarSpeed`) and map marker popup as read-only context.
  - Feeds a new, third attention proxy in `vehicle-list.js::computeAttention()`: `reported_stopped` — live speed ≤2 km/h while GPS is fresh (not stale) and the vehicle isn't already parked at a stop. Purely corroborating/informational, same as the existing `stuck`/`gps_stale` proxies from Phase 3.

### Deferred (explicit decision, not forgotten)
- Manual "Archive Plan" action — holding off to observe whether auto-completion alone resolves the dashboard-clutter complaint in real usage before adding a manual escape hatch.
- A default rolling date-window filter was considered and rejected during planning: a plan can legitimately span into the next day, and filtering by `plan_date === today` risked hiding real, still-active work.

### Testing
- 9 new tests: `TestPlanAutoCompletion` (4 — single-assignment completion, partial-completion no-op, multi-assignment requirement, revert-on-insert-into-completed-plan) and `TestTrackingService` (5 — embedded-speed parsing, unparseable→`None`, missing-field→`None`, decimal speed, and explicitly distinguishing a genuine `0` reading from "unknown"). Full suite: 49/49 passing.
- Manual: dev server + browser (console-mocked `DASH.api.*`, same technique as the Phase 3 QA pass) — confirmed the info bar and map popup render the parsed speed, the `reported_stopped` attention chip/dot fire at low speed and clear at normal speed, no console errors. Auto-completion itself was verified via the isolated pytest suite rather than against the real `routing_system.db`'s existing plans, to avoid irreversibly mutating that data during a manual check.

## 2026-07-30 — Dispatch Module Phase 3 QA Pass: Two Bugs Fixed

Final QA pass on Phase 3 before tagging, covering: Follow mode over an extended session, attention chips crossing real thresholds, photo gallery under multiple-images/missing/slow-network conditions, inline-reason-edit durability under polling and rapid interaction, listener/memory growth, and browser performance over a simulated 30-minute session. Verified via a console-level mock harness driving `DASH.api.*` with realistic synthetic data (moving GPS, threshold-crossing timestamps, multi-image responses, artificial network delay) since this sandbox has no live TTAS/ORS credentials. Two real bugs found and fixed in `static/js/dashboard/timeline.js`; everything else confirmed correct.

### Fixed
- **Duplicate photo-gallery fetches under slow network** (`timeline.js::bindPhotosToggle`) — rapid toggle clicks while a fetch was in flight (`loaded` was still `false`) triggered a second concurrent request to `/api/stops/<id>/images`. Reproduced with 4 rapid clicks during a 3s artificial delay → confirmed 2 fetch calls. Added a `loading` guard alongside the existing `loaded` one; re-tested identically → confirmed 1 call.
- **Abandoned reason edit permanently blanked a stop's content** (`timeline.js::render`) — the `openReasonStopIds` guard added to protect an in-progress skip/cancel edit from being wiped by a background poll was never cleared. If a dispatcher opened Skip/Cancel on a stop and navigated away (selected a different vehicle, or deselected) without confirming or cancelling, that stop's `.timeline-detail-wrap` — including its Advance/Skip/Cancel buttons — stayed permanently empty on every future render for the rest of the session, even after a full rebuild created a brand-new DOM node for it (reproduced and confirmed: `detailWrapInnerHtmlLength: 0` after abandon-and-return). Fixed by clearing `openReasonStopIds` at the two points where stale reason-row state can no longer correspond to real DOM: the empty-list branch and the full-rebuild branch of `render()`. Re-verified the original in-progress-edit-survives-polling behavior still holds (30 consecutive same-assignment polls) after this change.

### Verified, no changes needed
- **Follow mode**: `panTo`-based re-centering tracked 20 simulated GPS-movement cycles smoothly with zero jitter, and correctly preserved a dispatcher's manually-set zoom level (tested at zoom 10, forced there by the user, vs. the manual "Zoom to Vehicle" button's zoom-14) throughout — confirming it never fights a manual pan/zoom.
- **Attention chips**: fired and cleared correctly against realistic threshold-crossing data for both proxies independently (stuck-at-stop crossing 20min, GPS-stale crossing 15min) and returned to hidden when both dropped back under threshold.
- **Photo gallery**: multiple images, zero images, and slow-network (3s artificial delay) scenarios all rendered the correct state once the duplicate-fetch fix above was applied.
- **Listener/memory growth over ~150 simulated poll cycles** (≈30min at the real 12s interval) mixed with UI interactions: DOM node count grew by only 3 (not scaling with cycle count), heap usage was flat (0MB measured growth via `performance.memory`), and an instrumented `addEventListener` audit found every element outside the attention strip bound its listener exactly once — no rebinding anywhere. The attention strip's repeated rebind count is many distinct short-lived chip elements (each bound once, each discarded together with its listener on the next full-innerHTML rebuild) rather than the same node being bound repeatedly — already a documented, deliberate Phase 3 simplification given the strip's small size, and confirmed non-leaking by the flat DOM/heap metrics, so left unchanged per "fix only issues found."
- `pytest tests/test_delivery.py` — 40/40 passing throughout (no backend touched by either fix).

### Remaining Known Limitations (unchanged from Phase 3)
- Attention thresholds (20min stuck, 15min GPS-stale) remain untuned against real fleet data.
- True SLA-based delay still requires a schema column, out of scope per the earlier decision.
- Could not test Follow mode / attention chips / photo gallery against real TTAS GPS or real uploaded images in this sandbox — verified via realistic synthetic data instead.

## 2026-07-30 — Dispatch Module Phase 3: Operational Workspace

Frontend-only workflow improvements to the Dispatch dashboard, based on a workflow analysis grounded in the actual code (not `docs/PHASE_3_Dispatcher_Workspace.md`'s aspirational layout). No grid/layout redesign, no new backend logic beyond the pre-existing image API, no schema change. All changes additive to `static/js/dashboard/{vehicle-list,timeline,map,main}.js`, `templates/delivery-dashboard.html`, `static/css/delivery-dashboard.css`, plus one method added to `api.js`.

### Added
- **Attention proxies** (`vehicle-list.js`) — since no scheduled/promised time exists anywhere in the schema, "delay" is approximated from data already available every poll: a vehicle `arrived` at a stop for more than 20 minutes without advancing ("stuck"), or a vehicle whose GPS hasn't updated in 15+ minutes ("GPS stale"). Surfaced as a small dot on the vehicle card, a dismissed-when-empty attention strip at the top of the vehicle list, and an "Attention first" sort toggle — all pure client-side derivation, no schema change.
- **Pinned current-stop card** (`timeline.js`, new `#currentStopCard` element) — the selected vehicle's current stop (contact name, address, phone, ETA) is now always visible at the top of the Timeline panel regardless of scroll position, with mirrored Advance/Skip/Cancel actions so the single most common action never requires scrolling.
- **Click-to-call** — `manager_phone` is now a `tel:` link in both the pinned card and each per-stop detail body (previously plain text).
- **Read-only photo gallery** (`timeline.js` + `api.js::stopImages()`) — a "📷 Photos" toggle per stop lazily fetches `/api/stops/<id>/images` (backend untouched, this endpoint already existed with zero consumers anywhere in the app before this) and shows a thumbnail strip; clicking a thumbnail opens the original in a new tab. Lives in its own DOM node outside the diffed detail content so its open/loaded state survives every poll.
- **Follow-vehicle map mode** (`map.js::followVehicle()`, new `#followVehicleBtn`) — `panTo` (no forced zoom, no popup) re-centers on the selected vehicle every poll while active; resets automatically on deselection or switching to a different vehicle.

### Changed
- **Skip/Cancel no longer use `prompt()`/`alert()`** (`timeline.js`) — clicking either swaps the action buttons for an inline reason input (Confirm/Enter to submit, × to abort), with `UI.toast()` reporting errors and enforcing "cancel requires a non-empty reason" (previously a silent `if (!reason) return`). Shared between the per-stop body and the pinned card via one `bindActionDelegation()`/`handleStopAction()` implementation, avoiding duplicate logic.
- Added `<script src="/static/js/utils.js">` to `delivery-dashboard.html` — first use of `UI.toast()`/`UI.escapeHtml()` on this page, per `CLAUDE.md`'s convention for new fetch/toast/escape code. The page's own `DASH.api` fetch wrapper (a different response contract than `ApiClient`) was kept as-is, matching the module it was already established in.

### Fixed (self-consistency issue caught during implementation)
- Because the new reason row is non-blocking (unlike the old native `prompt()`, which paused all JS until dismissed), a background poll can now legitimately fire while a dispatcher is mid-typing a skip/cancel reason. Content diffing for a stop with an open reason row is suppressed (`openReasonStopIds` set) until it closes, so an in-progress edit is never silently wiped — the exact kind of state-loss bug this dashboard's Phase 1 work was about eliminating.

### Testing
- `pytest tests/test_delivery.py -v` — 40/40 passing, unaffected (no backend logic changed).
- Manual: dev server + browser — verified the pinned card renders with a working `tel:` href, the inline reason row appears/confirms/cancels with zero native dialogs, the required-reason toast fires correctly, the photo gallery lazy-fetches and shows the correct empty state, and the Follow toggle switches to its active visual state. Could not visually trigger an actual attention chip/dot, since no vehicle in this sandbox's data currently has live GPS or a long-arrived stop meeting either threshold — the toggle and empty-strip behavior were confirmed, the firing condition itself was not.

### Remaining Technical Debt / Deferred
- Attention thresholds (20 min stuck, 15 min GPS-stale) are reasonable defaults, not tuned against real fleet data — may need adjustment once used in production.
- True SLA-based delay (vs. a promised/scheduled time) remains unavailable — would need a schema column, explicitly deferred per this phase's scope decision.

### Out of Scope
- A few other pre-existing dead-for-the-same-reason status-map entries in `vehicle-list.js`/CSS (noted in the Phase 0 entry) remain untouched.
- Alerts, WebSockets, routing/backend redesign — reserved for later phases per `docs/MASTER_PLAN.md`.

## 2026-07-30 — Dispatch Module Phase 2: Route Intelligence

Extends the existing ORS integration (`services/delivery/eta_service.py`, `services/delivery/routes.py`) to surface road geometry, remaining/travelled distance, and avoid redundant ETA recalculation; updates the map's route rendering (`static/js/dashboard/map.js`, `main.js`) to draw it. No new endpoints, no schema change, no new routing provider, polling interval unchanged.

### Added
- **Road-following route geometry** — `eta_service.calculate_eta()` now parses the `geometry.coordinates` ORS was already returning (previously discarded) and converts GeoJSON `[lng, lat]` to Leaflet's `[lat, lng]`. Each leg in `calculate_etas_for_stops()`'s output now carries this as `"geometry"` (`None` for haversine/fallback legs, where no real road path exists).
- **In-memory route cache** (`eta_service.py`, module-level `_route_cache` + `threading.Lock`) — `calculate_etas_for_stops(..., assignment_id=...)` reuses the previous result when the remaining stop set/order/coordinates are unchanged AND the vehicle has moved less than `ROUTE_CACHE_GPS_THRESHOLD_M` (50m, filters GPS jitter without masking real movement). Invalidates on assignment change (different cache key), stop order/destination change (stop-id+lat+lng tuple differs), stop completion/skip (changes which stops are "remaining"), and significant GPS movement. Kept local to `eta_service.py` rather than `app/state.py` — that module's docstring scopes it to the fleet/fuel/oil/trips blueprints + TTAS session, a different package/concern than `services/delivery`. `assignment_id` defaults to `None`, which bypasses the cache entirely (existing callers/tests unaffected).
- **Remaining/travelled/total distance** — `/api/eta` now also returns `remaining_distance_km` (from the last remaining leg's new `cumulative_km`), `travelled_distance_km` (new `calculate_travelled_distance_km()` — a straight-line, best-effort sum across already-passed stops, intentionally not ORS-routed to avoid extra API calls for a secondary figure), and `total_distance_km`. Surfaced in the dashboard's vehicle info bar via a new `#vibarDistance` span.

### Changed
- `map.js::updateRoute(eta, stops)` (signature changed, both call sites in `main.js` updated) — now builds the polyline by concatenating each remaining leg's road geometry in order; falls back to a straight segment only for the specific leg(s) missing geometry, and to the old straight-line-through-all-stops behavior only when there's no live ETA at all (GPS offline) — never blanks the route. Solid line when real road geometry was used, dashed when it's a straight-line fallback, so dispatchers can tell the difference at a glance. The existing "skip redraw if the path is unchanged" check (from Phase 1) is unchanged, now comparing the richer coordinate list.
- Vehicle info bar's "ETA:" label is unchanged (still time-to-next-stop, from `etas[0].eta_seconds`, per Phase 0's established contract) — the new distance figures are additive, not a replacement, to avoid an unrequested semantic change.

### Testing
- 9 new tests in `tests/test_delivery.py::TestEtaService`: geometry coordinate-order conversion, `geometry: None` on non-ORS legs, `cumulative_km` tracking, cache hit (ORS mock called once across two identical calls), cache invalidation by GPS move / stop-set change, cache tolerating sub-threshold GPS jitter, cache bypass when `assignment_id` is omitted, and `calculate_travelled_distance_km` (zero when nothing passed, positive sum otherwise). Full suite: 40/40 passing.
- Manual: dev server + browser — confirmed no console errors and correct graceful fallback (old straight-line-through-stops behavior, unchanged) in this sandbox, which has no TTAS/ORS credentials configured so `/api/eta` returns `{"error": "Vehicle GPS not available", "etas": []}` for every vehicle. The road-geometry/caching logic itself could only be exercised through the mocked unit tests in this environment.

### Remaining Technical Debt / Deferred
- `travelled_distance_km` is straight-line (haversine), not road-following — an intentional trade-off to avoid extra ORS calls for a secondary metric; flagged in case a later phase wants it more precise.
- Route cache has no eviction/TTL — acceptable at this fleet's scale (40 vehicles' worth of tiny cache entries), not worth the complexity here.

### Out of Scope
- Alerts, WebSockets, new routing providers, backend/database redesign — reserved for later phases per `docs/MASTER_PLAN.md`.
- Could not visually confirm real road polylines rendering in this sandbox (no ORS/TTAS credentials available) — recommend a manual check against the live Render deployment or a local `.env` with real credentials before considering this phase fully verified end-to-end.

## 2026-07-30 — Dispatch Module Phase 1: Incremental Live Updates

Rendering-only pass on the Dispatch dashboard's poll-driven refresh (`static/js/dashboard/{vehicle-list,map,timeline}.js`, small `main.js` call-site changes). No new endpoints, no schema change, no WebSockets, polling interval (12s) unchanged. Verified against the live code, not `SYSTEM.md`/`DELIVERY_MODULE.md`.

### Fixed
- **Vehicle list rebuilt from scratch every 12s poll** (`vehicle-list.js`) — `container.innerHTML = html` destroyed and recreated every card (and rebound every click listener) regardless of whether anything changed, resetting scroll position and hover/focus state. Now keeps a `Map<assignment_id, cardElement>`: creates only new cards, patches text/class/width on existing ones by comparing old vs. new values, removes cards for ids no longer present, and reorders via targeted `insertBefore` only when order actually changed. Click listeners are bound once per card at creation.
- **Vehicle markers cleared and recreated every poll** (`map.js`) — `vehicleMarkerLayer.clearLayers()` + full rebuild destroyed marker identity (and any open popup) every 12s. Now diffs by assignment id: moves existing markers via `setLatLng`, patches the label/border color by writing directly to the existing icon's DOM node (no `setIcon`), and updates popup content via `popup.setContent()` — which Leaflet applies live even while the popup is open, instead of closing it. Same approach for the selected assignment's stop markers (full rebuild only when the stop-id set changes, i.e. on selection switch); the route polyline is skipped entirely when its coordinates haven't changed.
- **Found and fixed while implementing the above**: `map.js::updateVehicles` read `gps.latitude`/`gps.longitude`, but `tracking_service.normalize_gps_position()` (`services/delivery/tracking_service.py`) has always output `lat`/`lng` — so vehicle markers were never actually placed on the map, independent of any rendering-strategy concern. Corrected to `gps.lat`/`gps.lng`.
- **Timeline rebuilt from scratch on every poll while a vehicle was selected** (`timeline.js`) — same `innerHTML` replacement pattern, plus a real state-loss bug: `collapsed = isCompleted ? '' : 'open'` was recomputed from status on every render, so a dispatcher's manual expand/collapse of a stop was silently reverted on the next poll (≤12s later). Now keeps a `Map<stop_id, element>` scoped to the selected assignment: full rebuild only when the stop-id set changes (selection switch, or a stop inserted); otherwise patches the header (seq/name/status badge) directly and swaps only the detail/action-button body content when its generated HTML actually differs. The collapse/expand toggle and Advance/Skip/Cancel actions are bound once per stop via delegated listeners on creation, so they never need rebinding and are unaffected by later body-content patches — this is what fixes the collapse-state loss.
- `main.js`'s `renderAll()` "no selection" branch bypassed the timeline module by setting `#timeline`'s `innerHTML` directly, which would have left `timeline.js`'s new node cache pointing at detached DOM. Added `DASH.timeline.clear()` (an alias for `render([], null, null)`) and routed that branch through it.

### Remaining Technical Debt / Deferred
- Timeline/vehicle-list reordering only handles add/remove/patch; if the *same* set of ids arrives in a different order on a same-key poll (structurally shouldn't happen — backend order is a stable `ORDER BY`, and stop order only changes via explicit reorder/insert actions that go through `refreshNow()`), the timeline won't reorder. Vehicle list already handles this case via `insertBefore` reconciliation; timeline was left simpler since its stop order is more stable. Flagged for Phase 3 if it ever surfaces.
- `map.js::currentZoomAssignment` remains an unused variable (pre-existing, out of scope).

### Out of Scope
- Alerts, routing changes, WebSockets, polling-interval changes — reserved for Phases 2/4/5 per `docs/MASTER_PLAN.md`.
- No new automated frontend tests were added (no JS test harness exists in this repo); verified manually via a running dev server + browser (see below) plus the existing `pytest tests/test_delivery.py` (unaffected, backend untouched except the one-line GPS field fix, which is frontend-only).

## 2026-07-30 — Dispatch Module Phase 0: Bug Fixes

Bug-fix-only stabilization pass on the Dispatch/delivery-dashboard module (`templates/delivery-dashboard.html`, `static/js/dashboard/*.js`, `services/delivery/*.py`), verified against actual code rather than the (partly stale) `SYSTEM.md`/`DELIVERY_MODULE.md` docs. No UI redesign, no schema change, no new features.

### Fixed
- **ETA contract mismatch** (`services/delivery/eta_service.py::calculate_etas_for_stops`) — backend never returned the `stop_id`/`eta_seconds` fields the dashboard frontend (`main.js`, `timeline.js`) reads, so stop ETAs never rendered and the summary bar showed `NaN`. Added both fields (mirroring existing `id`/`cumulative_sec`) without removing the originals.
- **Dead header refresh button** — `#refreshNowBtn` in `delivery-dashboard.html` had no event listener. Bound it to the existing `DASH.state.refreshNow()` (same mechanism `#refreshGPSBtn` already used).
- **Status/Plan filters could never return results** — `get_dashboard_data()` (`execution_service.py`) never selected a `plan_status` field at all (every card silently defaulted to "confirmed"), and separately its `WHERE dp.status IN ('confirmed','executing')` scope (intentional — an active-ops board) meant "Draft/Completed/Cancelled" could never match. Added `dp.status AS plan_status` to the query, removed the three unreachable options from `#filterStatus`, and filtered the Plan dropdown (`main.js::populateFilterPlans`) to only list confirmed/executing plans.
- **Driver source duplication** — the dashboard showed only `vehicles.current_driver` (a generic default edited in Vehicle Management), ignoring the dispatcher-assigned, per-delivery `vehicle_assignments.driver_id → drivers.name` that Plan Builder already treats as authoritative and override-capable. `get_dashboard_data()` now `LEFT JOIN`s `drivers` and returns `COALESCE(NULLIF(d.name,''), v.current_driver)` under the same `current_driver` field name (no frontend change needed).
- **Dead `enroute` UI handling** — `execution_service.advance_stop()` only ever implements `planned → arrived → completed`; nothing sets `status = 'enroute'`, confirmed by the existing passing test `test_advance_planned_to_completed` and by `CHANGELOG.md`'s own prior description of `advance_stop`. Removed the unreachable `enroute` branches from `vehicle-list.js`, `timeline.js`, `map.js` status maps and their corresponding `delivery-dashboard.css` classes. Backend `IN ('planned', 'enroute', 'arrived')` clauses left untouched (harmless, matches the schema's documented status domain).

### Known Issues / Out of Scope
- `SYSTEM.md`/`DELIVERY_MODULE.md` still document a 4-state `planned → enroute → arrived → completed` lifecycle that doesn't match the shipped 2-step `advance_stop`; docs were not updated as part of this bug-fix-only pass.
- `docs/dispatch/PHASE_0_BUG_FIXES.md` / `DISPATCH_ARCHITECTURE.md` referenced by the originating ticket don't exist in this repo — only `docs/MASTER_PLAN.md` + `docs/PHASE_1..5_*.md` (phases 1–5, no Phase 0 doc).
- `vehicle-list.js::statusClass()` and `delivery-dashboard.css` still contain a few other status-map entries (`arrived`, `skipped`, `planned` on `plan_status`-scoped elements) that are dead for the same reason `enroute` was — out of scope since only `enroute` was flagged.

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
