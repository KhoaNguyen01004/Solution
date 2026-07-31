# Changelog

## 2026-07-31 — Removed dispatcher authentication; stop reordering on the dashboard; Plans panel positioning

Three operator-requested changes to the delivery/dispatch module.

### Removed — the dispatcher password (reverses audit C-04)

The shared-password gate added earlier the same day was removed at the operator's request: anyone who can reach the app can now change a plan. This is a deliberate reversal of a security fix, recorded plainly rather than buried — the trade accepted is that `POST /api/plans/clear`, which cascade-deletes every plan, assignment, stop, execution record and image row, is again reachable by anyone who can resolve the host. The app binds `0.0.0.0`. **If this is ever exposed beyond the internal network, this decision needs revisiting.**

- Deleted `app/auth.py` and `templates/login.html`. `/login`, `/logout` and `/api/auth/status` no longer exist.
- Dropped all 22 `@login_required` decorators from `services/delivery/routes.py` and the import behind them.
- `app/config.py`: `DISPATCH_PASSWORD` and `SESSION_LIFETIME` removed (with the now-unused `timedelta` import). `SECRET_KEY` and the `SESSION_COOKIE_*` hardening stay — they are app-wide defaults, and no route reads the session today.
- Frontend: `handleAuthFailure()` gone from `static/js/utils.js`, and the 401-redirect / 503-message branches gone from `static/js/dashboard/api.js` and `static/js/delivery-plan-builder.js`. Non-OK responses fall through to the same error path they always did — verified `ApiClient.fetch`'s behaviour for a non-OK, non-auth response is byte-for-byte what it was.
- `.env` still carries a `DISPATCH_PASSWORD` line. It is gitignored and now unread; harmless, but worth deleting by hand.
- `docs/DELIVERY_AUDIT_2026-07-31.md` was left as written. It is a record of what the audit found, not a statement of current configuration.

### Added — reorder stops from the dashboard

`POST /api/stops/reorder` has existed since the delivery module was built and **no UI had ever called it** — resequencing a live route meant editing the plan in the builder. The timeline panel now has up/down controls on each stop.

- Up/down buttons rather than drag-and-drop: the plan builder's Step 3 already has HTML5 drag, but those events don't fire on touch, and this panel is used on a phone in the cab.
- **Terminal stops are immovable, and nothing moves across one.** A completed / skipped / cancelled stop's position is a record of what happened; renumbering around it would rewrite history. A direction is disabled when the neighbour in that direction is terminal.
- **Optimistic.** The new order paints before the request goes out — a dispatcher resequencing a route does several stops at a time and a round trip plus an ETA recompute per click is unusable. Moves are POSTed strictly in click order through a promise chain (`state.reorderStops` in `dashboard/main.js`), because the server rewrites every `execution_sequence` on each call and two racing requests would settle on whichever finished last, not on what was clicked last. Exactly one refresh runs when a burst settles.
- A poll landing mid-reorder is suppressed (`pendingReorders` guard in `loadAssignmentDetail`), and `detailGeneration` is bumped on each move so a load already in flight is dropped. Without both, a background poll a second later visibly snaps the list back to the old order.
- **`timeline.js`'s rebuild key is now order-independent** (sorted stop ids). It was `list.map(s => s.id).join(',')`, so a reorder counted as a new set and wiped the container — collapsing every stop and closing any open photo gallery, which is precisely the state a dispatcher is mid-way through using when they resequence. Nodes are now moved with `insertBefore` instead.
- **Sequence badges now show `execution_sequence`, falling back to `planned_sequence`.** The whole dashboard *orders* by `execution_sequence`; `planned_sequence` is fixed at plan-build time. Showing the latter meant a reordered route rendered as 1, 3, 2 — the list order was right and the numbers on it disagreed. Fixed in the timeline badge, the pinned current-stop card, and the map's stop popup.

### Fixed — the Plans (⚙) panel opened off-screen

`.manage-plans-dropdown` was `position: absolute; right: 0` against `.manage-plans-wrap`, pinning the panel's *right* edge to the button's right edge. `.dashboard-header` is `flex-wrap: wrap`, so at narrower widths the button moves; once it sits near the left of a wrapped row, a 320px panel extends past the left edge of the viewport and only part of it is visible. `.dashboard-shell`'s `overflow: hidden` separately clipped the bottom.

Now `position: fixed`, placed by `positionManagePlans()` from the button's `getBoundingClientRect()`: right-aligned to the button where there is room, then clamped to the viewport on every side, with `max-height` set to the space actually remaining below the button so the Delete/Clear row stays reachable. Repositions on `resize`; Escape closes it. `.manage-plans-list` lost its fixed `max-height: 280px` in favour of `flex: 1; min-height: 0` so the panel height governs.

### Fixed — the map snapped back to the selected vehicle on every poll

Panning away to look at a street was impossible: within ~12 seconds the map dragged itself back onto the vehicle. Nothing in this codebase was calling `setView`/`panTo` on a poll — it was Leaflet's `Popup._adjustPan()`, which pans the map to keep an open popup in view and is on by default. `zoomToVehicle()` opens the selected vehicle's popup, and for a moving truck **two** separate paths reached `_adjustPan()` on every single poll:

1. `popup.setContent()` → `DivOverlay.update()` → `_adjustPan()` — the popup text carries GPS coordinates and speed, so it differs every poll.
2. `marker.setLatLng()` → fires `move` → `Layer._movePopup()` → `popup.setLatLng()` → `_adjustPan()`.

`updateVehicles`/`updateStops` now run both through a `withoutAutoPan()` helper that flips `popup.options.autoPan` off for the duration and restores it. Suppressed for background updates only — opening a popup still auto-pans (`Popup.onAdd` → `update` → `_adjustPan`), which is what keeps a popup readable when its marker sits near the edge of the map.

Automatic view changes are now limited to Follow mode (`panTo`, explicitly opted into). Zoom-on-select is unchanged: it fires from `selectAssignment()`, which is a direct response to a click and already returns early if the assignment is already selected.

Verified against real Leaflet 1.9.4 under jsdom rather than by inspection: two simulated polls produce four `_adjustPan()` calls (two per poll — confirming both paths were live), all with `autoPan` false, and the map centre after panning away is bit-identical before and after. The same harness with the helper neutered reproduces the bug — centre moves from 10.95/106.90 to 10.874/106.675, i.e. back onto the truck.

### Fixed — map control buttons became unreadable on hover

`.map-control-btn:hover` was `background: rgba(255,255,255,0.12)`. The base state is opaque `--surface-2`, so hovering *replaced* it with 12% white — effectively transparent, letting the OSM tiles through under near-white `--text-primary` text. Zoom Vehicle / Follow / Google Maps / GPS were least readable exactly when pointed at. Hover is now opaque `--surface-3` with an accent border, and `.active:hover` (Follow when engaged) darkens to `--accent-hover` instead of dropping to the neutral hover, which read as "turning off".

### Fixed — the timeline panel would not scroll

Expanding a few stops pushed the rest out of sight with no scrollbar. `.timeline` is a flex column with `overflow-y: auto`, but `.timeline-item` never set `flex-shrink`, so it defaulted to `1`: once the items were collectively taller than the panel the browser squashed them to fit rather than overflowing, and `overflow-y: auto` had nothing to scroll. Each item also carries `overflow: hidden`, so the squashed bodies were clipped rather than merely cramped — which is why the content looked like it had vanished instead of looking compressed. `.timeline-item` is now `flex-shrink: 0`.

**The same defect exists in `.vehicle-list` / `.vehicle-card` in the left panel** (same flex-column-plus-`overflow-y:auto` shape, no `flex-shrink` on the card). It is more visible there because there is no `overflow: hidden` on the card, so text spills between cards instead of being clipped. Left alone per scope control — noted here for whoever picks it up.

### Testing
- `pytest tests/` — **254 passed, 0 failed.** (258 before: the 8 removed authentication tests were replaced by 4 open-access ones.)
- `tests/test_delivery_routes.py`: the `auth_client` fixture is gone, all 82 uses now take the plain `client`. `TestAuthentication` became `TestOpenAccess` — the inverse regression guard, failing if any of the 22 mutating endpoints ever returns 401/403/503 again, plus an assertion that `/login` 404s. The existing reorder-validation tests were already route-level and needed no change.
- All modified JavaScript checked with `node --check`.
- `create_app()` verified to build and register 107 routes with no `/login` among them.

### Not done
- No confirmation step was added in front of the now-ungated destructive endpoints beyond the `confirm()` dialogs already in the UI.
- The plan builder's Step 3 reordering was left alone — the operator confirmed it is already workable.

## 2026-07-31 — Removed the Trip Management / Trip History pages (superseded by Dispatch)

Both pages were the original dispatch UI. The delivery dashboard was later built as a separate implementation rather than reusing them, leaving two pages doing the same job. Dispatch is the one that matches current requirements, so the older pair is gone.

### Removed
- `templates/manage-trips.html`, `templates/trip-history.html`
- `static/js/manage-trips.js`, `static/js/trip-history.js`
- Page routes `/manage-trips` and `/trip-history`
- The "Trips ▾" nav dropdown from all 7 remaining templates (removed whole, not just its two links — otherwise an empty dropdown button would be left behind)
- Eight endpoints whose only callers were those two pages, verified by scanning every surviving `static/js/**` and `templates/*.html` file rather than by assumption: `/api/set-destination`, `/api/trips/history`, `/api/trip-history`, `/api/clear-trip`, `/api/update-trip`, `/api/clear-all-trips`, `/api/geofence-events`. `app/routes/trips.py` drops from 782 to ~500 lines.
  - This also closes the duplicate-endpoint item at `docs/CODEBASE_ANALYSIS_REPORT.md:183` — `/api/trips/history` and `/api/trip-history` both routed to the same function; both are now gone.

### Kept, deliberately
- **`/api/route-data`, `/api/advance-trip`, `/api/cancel-trip`** — these are *not* trip-page endpoints. `static/js/map.js` on the main fleet map calls all three, so removing `app/routes/trips.py` wholesale would have broken the landing page. This was the main risk in the request and the reason the module was narrowed rather than deleted.
- **`/api/refresh-routes` and the background route-refresh thread** — left untouched pending a decision (see below). `/api/refresh-routes` now has no in-app caller, but `app.py` documents it as the external-scheduler entry point for production, which is exactly the mechanism a fix would use.

### Consequence worth knowing
`/api/set-destination` was the **only** way to create a `vehicle_trips` row, and it lived on the Trip Management page. Nothing can create a trip any more, so the main map's surviving route-line / advance / cancel code operates on a table that is empty and can no longer be populated through the UI. Those code paths are effectively vestigial. `map.js` was left alone — it is the landing page and its cleanup was not part of this request. Recorded here rather than actioned silently.

### Not touched
- `vehicle_trips` and `geofence_events` tables — both are empty (0 rows), harmless, and `scripts/migrate_to_delivery.py` still reads `vehicle_trips`. Dropping them is a separate decision.
- The Vietnamese internship report at repo root still documents the removed pages; it is explicitly out of scope per `CLAUDE.md`.
- `graphify-out/` still lists the deleted files — regenerate with `graphify update .`.

### Documentation
- `CLAUDE.md`: the "3 pages still use the legacy global `showToast()`" note is now 1 page (`locations.js`) — the other two were the deleted files.
- `README.md`: `trips.py`'s description narrowed to what it actually does now.

### Testing
- `pytest` — **258 passed, 0 failed**, unchanged. No test referenced the removed pages or endpoints, which is itself a data point: the route-layer suite added in Phase 5 covers delivery, not trips.
- Verified `create_app()` still builds and registers 110 routes, that none of the removed paths resolve, and that the four intended survivors do.

## 2026-07-31 — Delivery Module Phases 4 & 5: Frontend Hardening + Route-Layer Test Suite

Final remediation phases against `docs/DELIVERY_AUDIT_2026-07-31.md`. Each Phase 4 finding was re-verified by execution before implementation, following the C-06 retraction in Phase 3. All three held.

### Fixed — frontend
- **Stale responses could overwrite the current selection (F-05)** — `loadAssignmentDetail()` wrote `state.selectedStops` / `selectedEta` unconditionally once its three requests resolved. The 12-second poll calls it too, so a click landing mid-poll was the common case: the previously-selected vehicle's detail could resolve *after* the newly-clicked one and overwrite it, leaving the vehicle list highlighting one truck while the timeline, map stops and info bar showed another. Added a monotonic generation token — a load writes only if it is still the newest and the assignment is still selected.
- **Unknown ETAs displayed as "ETA: 0 min" (L-10)** — `Math.round(null / 60)` is `0` in JavaScript, and `eta_service` sets `eta_seconds: None` for any stop without coordinates. The info bar therefore told a dispatcher the truck was arriving *now* when the truth was "unknown". `timeline.js` already guarded this with a `typeof` check; `main.js` did not. Verified in Node before fixing.
- **A throwing error-handler could kill polling permanently (F-06)** — `isPolling = false` sat after the try/catch rather than in a `finally`, so anything thrown from the catch block latched the flag and disabled both the 12-second poll and manual refresh for the rest of the session, with the status pill frozen on its last value. Now in `finally`; verified by driving a tick whose error handler itself throws and confirming subsequent ticks still run.
- **Refreshes after an action were silently dropped (F-04)** — `refreshNow()` returned immediately if a poll was in flight, so the refresh chained onto a successful Advance/Skip/Cancel was thrown away and the dispatcher saw no change for up to 12 seconds *on an action they had just taken*. This directly undermined the Phase 3 double-tap fix: the first tap succeeded, nothing visibly happened, and a second tap was the natural response. Requests are now coalesced — a refresh arriving mid-poll runs when the in-flight tick finishes. Verified: three refreshes fired during one slow tick produce exactly one catch-up run, with no overlap.
- **Background tabs polled forever (P-08)** — added `visibilitychange` handling; the interval is cleared while the tab is hidden and resumes with an immediate catch-up tick. Dispatchers leave this page open all day.
- **No client-side request timeout (P-08)** — `/api/eta` issues one ORS call per remaining stop, serially, each with a 30-second server timeout, so a slow route could hang well past the poll interval and freeze the dashboard behind a green "Live" pill. `api.js` now aborts at 20 seconds with a clear message.

### Added — route-layer test suite (T-01)
**`tests/test_delivery_routes.py`, 92 tests.** The audit's most consequential structural finding was that all 49 existing tests imported service modules directly and **nothing exercised the route layer** — which is exactly where every Critical bug lived. C-01 was one line inside a request handler; C-02/C-03 were only observable in an assembled response; C-04 is a property of routes; C-05's duplicate write sat behind an endpoint. A service-level suite is structurally incapable of catching any of them.

Coverage, driving real HTTP through `app.test_client()` with TTAS mocked:
- **GPS pipeline** — GPS reaching the dashboard, telemetry parsed from raw TTAS keys, all five plate formats matching one vehicle, unknown plates not matching, 0,0 reported as no-fix, malformed coordinates not 500-ing, failures surfaced rather than hidden, and ETA not double-normalized.
- **Authentication** — all 22 mutating endpoints parametrized and asserted to reject anonymous callers; read endpoints asserted to stay open; wrong password, logout, and the fail-closed 503 when `DISPATCH_PASSWORD` is unset.
- **Execution lifecycle** — full progression, the double-tap 409 leaving `actual_departure_at` unset, skip/cancel with reasons, current-stop advancement, plan auto-completion, temp-stop insertion reopening a completed plan, and empty-assignment progress.
- **Reorder validation** — full, partial and foreign-id cases, including an assertion that no duplicate `execution_sequence` values are left behind.
- **Excel import** — plate variants collapsing to one assignment with no new vehicles, unknown plates rejected with nothing written, and that no request flag can turn the import into a vehicle-creation path.
- **Uploads** — accepted image types, rejected `.html`/`.svg`/`.php`/`.txt`/extensionless, oversized and empty rejection, traversal in `category` confined to the upload root, two same-second uploads both surviving, and round-tripping an uploaded file back through `send_file`.

### Fixed — test isolation
**The image tests were writing into the repository.** `image_service` derives `UPLOAD_ROOT` from its own file location, so every run left real `.jpg` files in `DeliveryPlans/`; dozens had accumulated. It also made `test_delete_image_removes_file` depend on the checkout being writable — which is why that test failed on every run throughout this work. An autouse fixture in both delivery test files now redirects `BASE_DIR`/`UPLOAD_ROOT` to a per-test temp directory.

**The suite is fully green for the first time: 258 passed, 0 failed.** The single failure reported in the Phase 1-3 entries above was this, not a code defect.

### Testing
- `pytest tests/` (excluding the non-pytest helper scripts) — **258 passed, 0 failed**, up from a 48-passed baseline before this work.
- Polling behaviour verified by executing the module under a browser-like shim rather than by inspection: refresh coalescing, no overlapping ticks, and survival of a throwing error handler.
- All modified JavaScript checked with `node --check`.

### Still open (not in scope for these phases)
- **P-01 / P-02 remain the biggest risk.** Fixing C-01 restored the synchronous TTAS fetch and serial ORS calls into the request path. With 36 vehicles the dashboard will be slower than the broken version was. The audit's Phase 3 proposal — a GPS adapter with a background refresher and parallel/batched ORS — is unimplemented.
- `_route_cache` in `eta_service` is still unbounded (T-10); `get_plan` still N+1 (P-03); missing indexes D-03/D-04 and the duplicate index D-02 are untouched.
- Vehicle identity is centralized for delivery and fuel only; `oil.py` and `fleet.py` keep their own inline plate handling.
- **Verify the Render persistent disk (D-10).** Still the cheapest high-value check available, and everything above is moot without it.

## 2026-07-31 — Delivery Module Phase 3: Execution Correctness (and one retracted audit finding)

Third remediation phase against `docs/DELIVERY_AUDIT_2026-07-31.md`. Before implementing, each Phase 3 finding was re-verified by running it. Two held, one did not.

### Retracted — audit findings C-06 and F-01 were wrong

The audit claimed the dashboard's rebuild cache key `list.map(s => s.id).join(',')` "encodes set membership, not order", so reordering stops produced an identical key and the UI never re-rendered. Rated High / Confirmed.

`Array.prototype.join` preserves order. `[10,11,12].join(',')` is `"10,11,12"`; `[11,10,12].join(',')` is `"11,10,12"`. The key is order-sensitive, a reorder changes it, and both `timeline.js` and `map.js` do rebuild. Verified in Node against the exact expression, and end-to-end: `list_stops()` returns `[3,2,1]` after reordering `[1,2,3]`.

Compounding it, **no frontend code calls `POST /api/stops/reorder` at all** — the only "reorder" match in `static/js/` is a drag handle in the plan *builder*, which reorders locally before save. The dashboard has no reorder UI, so the scenario could not arise either way.

Root cause of the mistake: the "set key" phrasing in the surrounding source comments was taken at face value rather than checked against what `join` does, and the finding was rated Confirmed without executing anything. Both entries are struck through in place in the audit with the disproving evidence, and the document now carries a warning that any remaining "Confirmed" label is provisional until re-verified by execution.

### Fixed
- **A double-tap on Advance marked a stop delivered with no arrival record (C-07)** — confirmed by execution: two calls took a stop `planned` → `arrived` → `completed`, stamping `actual_arrival_at` and `actual_departure_at` **in the same second** and destroying dwell time. If it was the last stop, `_maybe_complete_plan` fired and the plan left the dashboard's active view entirely. On a mobile dispatch UI an impatient second tap is routine, not an edge case.
  - `advance_stop()` now takes an optional `expected_status` — the status the dispatcher's screen was actually showing. When it no longer matches, the move is refused with a message telling them to refresh.
  - The UPDATE additionally carries `AND status = ?`, so if two requests do arrive together only one can affect a row; the loser sees `rowcount == 0` and reports the conflict instead of double-stepping. This closes the genuine race, not just the double-click.
  - `POST /api/execution/advance` returns **409** with `conflict: true` for a stale advance, so the client can distinguish "you're out of date, refresh" from "malformed request".
  - `timeline.js` renders the button with `data-expected-status`, disables it for the duration of the request, and holds an in-flight token per stop+action so a second tap is dropped client-side before it ever becomes a request.
  - `expected_status` is optional throughout — callers that omit it keep the previous behaviour.
- **Assignments with no stops reported "1 remaining" (C-09)** — `total = sum(counts.values()) or 1` put a division guard on the total rather than the division, so an empty assignment showed `total: 1, remaining: 1` on its vehicle card and info bar, and a dispatcher went looking for a stop that did not exist. Only the division needed guarding.
  - The seven-line progress computation existed **twice, verbatim including the bug**, in `get_assignment_progress` and `get_dashboard_data`. Extracted to `_progress_from_counts()` — one home, one fix (audit duplicate-logic cluster 5).
- **`reorder_stops` validated nothing (recorded as C-06b)** — the real bug in the function C-06 wrongly accused. It accepted any list and applied it stop-by-stop:
  - a **partial** list renumbered only the stops it named, producing `execution_sequence` values of `[1, 1, 2]`. Nothing enforces uniqueness on that column, so `ORDER BY execution_sequence LIMIT 1` in `get_current_stop` became non-deterministic — **the dashboard could show the wrong next stop**;
  - ids from a **different** assignment matched no row yet the function returned `True`, so the caller got a silent no-op.

  It now requires the list to name every stop of the assignment exactly once, returns `(ok, message)` matching `advance_stop`'s convention, and names precisely what's wrong (`missing stop(s) [...]` / `stop(s) [...] not in this assignment`). The route surfaces that message instead of a generic "Reorder failed".

### Already done
Phase 3 item 4 (L-06, the plan-status UPDATE inside the per-vehicle loop) was completed in Phase 2 — restructuring that loop made leaving the bug in place indefensible.

### Testing
- `pytest tests/test_delivery.py` — **98 passed, 1 failed**, up from 86. The failure remains the sandbox `unlink` permission artifact documented in the Phase 1 entry.
- 12 new tests across `TestAdvanceAtomicity`, `TestReorderValidation` and `TestProgressWithoutStops`, including assertions that the deliberate two-step progression still works and that a failed double-tap leaves `actual_departure_at` unset.
- 12 end-to-end checks through `app.test_client()`: the double-tap returning 409 with the stop still `arrived`, the genuine second step still succeeding, partial and full reorders, and an empty assignment reporting zero through the dashboard endpoint.
- **`test_progress_empty` was rewritten.** It asserted `total == 1` with the comment *"fallback to avoid div-by-zero"* — it encoded C-09 as intended behaviour, the same category of problem as the GPS contract tests corrected in Phase 1. Two of the three tests changed in these phases were wrong rather than merely outdated.

## 2026-07-31 — Core Fleet Data Is Now Read-Only to Background Processes

Follow-on to Phase 2, at the user's direction and widened beyond the delivery module. The rule: **`vehicles` is the source of truth, and only a human editing Vehicle Management may change it.** New data flowing into the system may read and link to a vehicle, never create one, and never silently alter core fields — plate number, vehicle type, dimensions, or driver name.

Phase 2 stopped the delivery import from creating vehicles. This entry removes every remaining path.

### Fixed
- **Logging fuel created vehicles and overwrote the driver name (`app/routes/fuel.py`)** — the worst of the remaining offenders, and live on every fuel entry. `INSERT INTO vehicles ... ON CONFLICT(plate_number) DO UPDATE SET current_driver = ...` meant:
  - a plate not stored byte-identically created a new vehicle, so logging fuel for `50E18463` while the fleet held `50E-18463` produced a duplicate truck — the same root cause as C-05, still shipping;
  - whatever name was typed on the fuel form silently became the vehicle's official `current_driver`. A relief driver covering one shift would permanently overwrite the assigned driver, with nothing shown to anyone.

  Both removed. The plate is now resolved through `services.vehicle_identity` (exact → canonical → 5-digit serial) and the fuel row is stored under the fleet's canonical plate. The same check was added to the edit path, so an edit can't introduce an unknown plate either.
- **The boot migration re-ran that upsert across all fuel history on every startup (`app/database/migrations.py`)** — `backfill_vehicles_from_fuel_log` is now **link-only**: it resolves unlinked `fuel_log` rows onto existing vehicles and normalises their plate, and never inserts or edits a vehicle. Plates matching nothing are left alone and named in a warning log rather than conjured into existence.
- **`scripts/migrate_to_delivery.py` created a vehicle for any key it couldn't find** — now resolves everything up front and aborts with the full list of unregistered plates, refusing to run rather than inventing rows.

### Changed — unknown vehicle now prompts instead of failing
Rejecting an entry outright would block someone standing at a petrol station. Instead, an unrecognised plate returns **409** with a structured body, and the UI offers to go register it:
- `services/vehicle_identity.unknown_vehicle_response()` returns `error_code`, a plain-language `message`, a `redirect_to` URL, and an `unknown_vehicle` block carrying what's already known.
- `suggest_plate_format()` turns `51D99999` into `51D-99999` (two province digits, one-or-two series letters, 4-5 digit serial) so the form arrives with a well-formed plate. It is a *suggestion in an editable field* — it never rewrites stored data, and returns the input unchanged when the shape isn't recognised.
- `static/js/fuel-efficiency.js` catches the rejection, confirms with the user, and redirects. `static/js/vehicle-management.js` reads `?new=1&plate=…&driver=…`, opens the Add Vehicle dialog pre-filled, focuses the type field, and clears the query string so a refresh doesn't reopen it. If the vehicle turns out to already exist it opens it for editing instead of offering a duplicate.
- **Dimensions are deliberately not pre-filled.** Nothing upstream knows them, and guessing core specs is the behaviour being removed.
- `ApiClient.fetch` (`static/js/utils.js`) now attaches the response body and status to the thrown `Error` (`err.data`, `err.status`). Callers reading only `err.message` are unaffected.

Because matching is loose, this prompt fires only for a truck genuinely not in the fleet — not for a formatting difference. `50E-18463`, `50E18463`, `50E 18463`, `50e-18463`, `18463` and a padded ` 18463 ` all resolve to the same vehicle, verified by test.

### Reviewed and left alone
- **`app/routes/fleet.py`** — Vehicle Management. The legitimate owner; creating and editing a vehicle is the explicit point of the request.
- **`services/google_sheet_service.py`** — already correct. It resolves on the 5-digit serial and skips unknown plates with a warning; its docstring already said *"the system never creates new vehicles from sync data."*
- **`truck_load_planner/routes.py`** — writes `container_configs`, which is user-driven container spec management, not automatic.
- **The one-time `tlp_trucks` → `container_configs` migration** (`migrations.py`) is the single remaining place outside Vehicle Management that writes a core field (`container_config_id`, i.e. dimensions). Kept: it does not act on new data, it relocates dimensions the user already entered from a retired table, and it is double-guarded to run once per database lifetime. It now **logs a warning naming what it changed** — the objection was to silent alteration, not to migration.

### Added
- **`tests/test_vehicle_core_data.py`** — 36 tests asserting the invariant directly, so it can't quietly regress:
  - the boot migration links fuel history without modifying `vehicles`, and does not overwrite `current_driver` from a fuel form;
  - a static scan of ten modules for `INSERT INTO vehicles` and for `UPDATE vehicles SET` touching `plate_number` / `vehicle_type` / `current_driver`;
  - an assertion that `container_config_id` is written in exactly one file;
  - `vehicle_identity` exposes no write helper of any kind;
  - the loose-match sweep, so the "new vehicle" prompt can't start false-firing on a format variant.

### Testing
- `pytest tests/test_delivery.py tests/test_vehicle_core_data.py tests/test_scorer.py` — **148 passed, 1 failed**. The single failure is the sandbox `unlink` permission artifact documented in the Phase 1 entry, unrelated and expected to pass on Windows.
- 15 end-to-end checks through `app.test_client()` confirming the vehicles table is byte-identical before and after fuel logs submitted under a *different* driver name — the exact scenario that previously rewrote `current_driver`.
- Two bugs were caught by the new tests rather than by review: the dimension-writing migration above, and (during Phase 2) a mis-grouped bare serial.

### Note
While editing `app/routes/fuel.py` I initially split its `from app import config, state` import and briefly broke the module; caught by a syntax/import check before any test run. Flagging it because the file is large and worth a skim on your side.

## 2026-07-31 — Delivery Module Phase 2: Vehicle Identity Service

Second remediation phase against `docs/DELIVERY_AUDIT_2026-07-31.md`. Closes C-05 (Excel import silently creating duplicate vehicle rows), L-03 (one truck split across two assignments), T-12 (the duplicate-merge script gone stale), and — unavoidably, see below — L-06.

The audit found seven plate-identity implementations with five incompatible semantics, and a canonical normalizer (`services/plate_utils.py`) that the delivery module had never imported. Phase 1 pointed delivery's GPS matching at it; this phase gives the whole concern a home.

### Added
- **`services/vehicle_identity.py`** — resolution only. **The module has no write path at all**: there is no `create_vehicle()`, no insert, no upsert. `resolve()` returns a `VehicleRef` or `None`, and adding a truck to the fleet is a Vehicle Management action (`app/routes/fleet.py`), never a side effect of importing a spreadsheet. A test asserts the module never grows a write helper.
  - Match precedence, strictest first: exact `plate_number` → canonical (case/separator-insensitive, matching what `ttas_client.py` already does for TTAS report dropdowns) → 5-digit serial via `normalize_plate`. `matched_by` on the result records which strategy won, so a dispatcher can be told *why* a plate matched. Confirmed against real fleet data: `50E-18463`, `50E18463`, `50E 18463`, `50e-18463`, `18463` and even an en-dash `50E–18463` all resolve to the same vehicle row.
  - **Ambiguity is refused, not guessed.** Two genuinely different full plates sharing a serial (`50H-18463` / `51C-18463`) disable serial matching for that serial and log a warning, rather than attaching stops to whichever truck happened to be indexed first.
  - **Bare-serial duplicate rows lose to full plates**, including on exact match. A row whose `plate_number` is just `09473` is a known artifact of the old Google Sheet sync that `tests/merge_duplicate_vehicles.py` exists to delete; new assignments must not attach to a row a future merge will remove. This surfaced as a genuine test failure during the phase and the resolver was corrected, not the test.
  - `VehicleIndex` is built once per operation rather than per lookup — `app/routes/fuel.py` currently re-scans the whole `vehicles` table on every insert (audit P-06) and this is the seam to fix that behind later.
  - **Deliberately not built: a `vehicle_aliases` table.** `normalize_plate` already collapses every variant present in this fleet's data, so an alias registry would be an empty table solving a problem that does not exist yet. `resolve()` is the seam if genuinely arbitrary aliases ever appear.

### Fixed
- **Excel import created duplicate vehicles on any plate-format variance (C-05)** — `confirm_import` built `{plate_number: id}` and did exact-string lookup; a miss ran `INSERT INTO vehicles`. A spreadsheet saying `50E18463` against a stored `50E-18463` produced a 37th vehicle with no type, no driver and no GPS association, polluting `/api/fleet/vehicles`, the TLP picker and fuel/oil reporting — and the delivery assignment attached to the phantom, so it could never match GPS even after Phase 1. Import now resolves through `vehicle_identity`; an unrecognised plate raises `UnknownVehicles` and the whole import rolls back with nothing written.
  - **Imports never create vehicles, under any circumstance.** There is no override flag. An unknown plate in a plan is a typo or an unregistered truck — not a format this resolver can't handle, since it already matches on the 5-digit serial regardless of how the sheet spelled it. `confirm_import`'s signature is asserted in tests to have no creation escape hatch.
  - `POST /api/plans/import/save` returns **409** (not 400 — the request is well-formed, it conflicts with fleet state) carrying `unknown_vehicles`, naming exactly which plates to check.
- **One truck imported as two assignments (L-03)** — grouping keyed on the raw spreadsheet string, so a file mixing `50E-18463` and `50E18463` split one driver's stops across two dashboard rows. Rows now group by *resolved vehicle id*. **Unresolved identifiers group by their 5-digit serial**, since that is what distinguishes a vehicle in this fleet — so `51D-77777`, `51D77777` and a bare `77777` are reported as one problem to fix rather than three. (Caught by a test written for this phase: canonical-form grouping collapsed the first two but not the bare serial.)
- **`preview_import` now reports resolution** when given a `db_path` — each assignment carries `resolved`, `resolved_plate`, `matched_by`, and the response carries `unknown_vehicles`. Unknown plates surface at preview time rather than as a failure at save time. The parameter is optional and the old behaviour is preserved without it.
- **`tests/merge_duplicate_vehicles.py` was stale (T-12)** — `INTEGER_FK_TABLES` listed only `fuel_log` and `tlp_load_plans`. The delivery module shipped after that script was written, so merging a duplicate would either abort on the `vehicles` DELETE (`vehicle_assignments.vehicle_id` has no `ON DELETE` action, and `DatabaseManager` enables FK enforcement) or, with FKs off, leave every assignment pointing at a deleted vehicle. Added `("vehicle_assignments", "vehicle_id")`.
- **Plan status UPDATE ran inside the per-vehicle loop (L-06)** — scheduled for Phase 3, but this phase restructured that exact loop and leaving a known bug in freshly-written code was indefensible. It now runs once after the loop, and only when at least one assignment was created: an empty import used to return success while the plan silently stayed `draft` and never reached the dashboard. **Phase 3 item 4 is therefore already complete.**

### Changed
- `confirm_import` returns a summary dict (`assignments_created`, `stops_created`, `plan_confirmed`) instead of a bare `True`, and the route passes it through. `plan_confirmed: false` is how an empty import now reports itself honestly.

### Still open: other paths that auto-create vehicles
Delivery no longer writes to `vehicles`. Three other places still do, and two of them can create the same duplicates C-05 created. Documented, not changed — they are outside this phase's scope and touch live fuel/oil data.
- **`app/routes/fuel.py:437`** — logging fuel upserts the vehicle by exact `plate_number`. `ON CONFLICT(plate_number)` only matches a byte-identical string, so recording fuel against `50E18463` while the fleet holds `50E-18463` **creates a duplicate row today**. Same root cause as C-05, still live, and the highest-value next target for `vehicle_identity`.
- **`app/database/migrations.py:179`** — `backfill_vehicles_from_fuel_log` upserts vehicles from `fuel_log` on every boot, with its own inline copy of the last-5-digit logic.
- **`scripts/migrate_to_delivery.py:84`** — one-off migration script, same exact-match-then-insert pattern.
- `app/routes/fleet.py:65` is the legitimate one: Vehicle Management, where adding a truck is the explicit point of the request.

### Testing
- `pytest tests/test_delivery.py` — **86 passed, 1 failed**, up from 59 after Phase 1. The single failure is the same analysis-sandbox `unlink` permission artifact documented in the Phase 1 entry; unchanged by this phase and expected to pass on Windows.
- 27 new tests across `TestVehicleIdentity`, `TestImportVehicleResolution` and `TestPreviewImportResolution`, including a parametrized sweep of all seven stored/lookup format combinations, the ambiguous-serial refusal, the bare-serial-duplicate preference, an assertion that a rejected import writes **nothing** (vehicle count unchanged, plan still `draft`), and a signature assertion that `confirm_import` cannot be talked into creating a vehicle.
- 12 end-to-end checks through `app.test_client()` covering the strict-import behaviour, plus the earlier full merge-script scenario: a delivery assignment pointing at a duplicate `09473` row is correctly repointed to `50H-09473` and the duplicate deleted — the exact operation that would have silently orphaned data before the FK-list fix.

### Notes
- **The Excel import pipeline has no frontend consumer.** `delivery-plan-builder.js` builds plans manually through the already-correct `vehicle_id` path and never calls `/api/plans/import/*`. The 409 change therefore has no UI blast radius.
- `merge_duplicate_vehicles.py` still has no guard for missing tables (it would already fail this way on `tlp_load_plans`). Any database the app has booted against will have `vehicle_assignments`, since `create_app()` calls `init_delivery_tables()` unconditionally, so the added entry does not create a new realistic failure path. Left as-is rather than widen this phase's footprint.
- Vehicle identity is now centralized *for the delivery module only*. `fleet.py`, `fuel.py`, `oil.py` and `migrations.py` still carry their own inline variants (audit duplicate-logic cluster 1). Migrating them is deliberately deferred — delivery had zero production rows and was a zero-risk proving ground; fuel and oil have live data and working reports.

## 2026-07-31 — Delivery Module Phase 1: GPS Pipeline Repair + Security Hardening

First remediation phase against `docs/DELIVERY_AUDIT_2026-07-31.md` (68 findings). Closes the five Critical items and the two highest-severity security findings. The audit's central conclusion drove the ordering: the dashboard's GPS was not "unreliable", it was **dead**, and had been since the module was written — four defects stacked on top of each other, only the last of which was the plate-format mismatch the team had identified.

### Fixed

- **GPS pipeline was entirely non-functional (C-01)** — `services/delivery/routes.py` did `from app import fetch_vehicle_data` inside a bare `except Exception`. That name resolves to the `app` **package**, which has never exported it (it lives in `app/services/ttas_client.py`; `app.py` and `app/routes/trips.py` both import it correctly). Every call raised `ImportError`, was swallowed, and returned `([], "error", ...)` — so `/api/execution/dashboard` never attached a `gps` key to any assignment, `/api/eta` always returned "Vehicle GPS not available", no map marker was ever created, and Zoom/Follow/Open-in-Google-Maps were permanent no-ops. Now imported at module scope from `app.services.ttas_client`, so a regression of this kind aborts `create_app()` instead of silently degrading one request at a time. `_ttas_vehicles()` keeps a narrow `except` but logs a traceback rather than flattening it into an empty list.
- **GPS normalization read the wrong dict schema (C-02)** — `tracking_service.normalize_gps_position()` read `speed_status` / `vehicle_status` / `engine_status` / `last_update` / `driver_name`, which are the *output* key names of `normalize_vehicle()`, from *raw* TTAS DevList items whose keys are `speed` / `ad3` / `trktime` / `driver` / `biensoxe`. Every one of those resolved to its default, and no `device_name` was emitted at all — so even with C-01 fixed there was nothing to match a position to a vehicle on. Rewritten to delegate raw-key parsing to `normalize_vehicle()` rather than reimplement it: that function already owns the six-key plate fallback chain, the Vietnamese speed-phrase → status derivation, and `safe_float`/`clean_text` coercion, and duplicating it would create a second source of truth for TTAS's field names. Also emits `plate_key` (the normalized 5-digit serial) so callers never have to re-derive it.
  - Related, same root cause: `routes.py`'s ETA handler called `normalize_gps_position()` a **second** time on an already-normalized dict, whose keys are `lat`/`lng` rather than `latitude`/`longitude` — coercing both to `0.0` and placing the vehicle at 0°N 0°E. Removed.
  - `safe_float()` returns `0.0` (not `None`) for missing coordinates, so an exact 0,0 reading is now reported as `lat: None, lng: None` — "no fix" rather than a position in the Gulf of Guinea. The frontend's existing `if (!gps || gps.lat == null)` guard already handles it.
- **Plate matching (C-03)** — `.strip().lower()` on both sides matched only byte-identical strings, and was also inconsistent with the rest of the codebase (`fleet.py`/`fuel.py`/`oil.py` all use `.upper()`). Both sides now go through `services.plate_utils.normalize_plate` — the canonical, already-documented normalizer that `google_sheet_service.py` and `merge_duplicate_vehicles.py` use but which the delivery module had never imported. `50E-18463`, `50E18463`, `50E 18463`, `50e-18463` and `18463` now all resolve to the same vehicle. New `_gps_by_plate_key()` helper indexes positions once per request and warns on serial collisions instead of silently keeping an arbitrary one.
- **No authentication on any endpoint (C-04)** — including `POST /api/plans/clear`, which cascade-deletes every plan, assignment, stop, execution record and image row, and was reachable unauthenticated on a publicly-deployed host. New `app/auth.py`: session-based login against a shared `DISPATCH_PASSWORD`, `hmac.compare_digest` comparison, `@login_required` applied to all **22** mutating endpoints. GET endpoints deliberately left open so the 12-second dashboard poll keeps working — locking reads risked taking dispatch dark for less exposure removed than it sounds (stop addresses and manager phone numbers remain readable without auth; tracked as follow-up, not fixed here).
  - **Fails closed**: with `DISPATCH_PASSWORD` unset, mutating endpoints return 503 rather than allowing access. An unset secret must not silently reopen the hole. **This means the variable has to be set before deploying** — see Deployment note below.
  - Session cookies hardened in `create_app()`: `HttpOnly`, `SameSite=Lax` (which also blocks the cross-site POSTs that would be the CSRF vector against the newly-protected endpoints — a mitigation, not a substitute for CSRF tokens), `Secure` outside debug, 14-day lifetime.
- **Stored XSS in the dispatcher dashboard (S-02)** — `map.js`, `timeline.js` and `main.js` each carried a private `escapeHtml` that built a text node and read back `.innerHTML`. Per the HTML fragment-serialization algorithm that escapes only `&`, `<`, `>` and NBSP — **not quotes** — while the canonical `UI.escapeHtml` in `utils.js` (already loaded by the same page, already used correctly by `vehicle-list.js`) does escape both quote characters. All three sinks were attribute-context: `map.js` `title="${escapeHtml(s.station_name)}"` and `timeline.js` `title=`/`alt="${escapeHtml(img.category)}"`, where `station_name` comes from Excel import or `POST /api/stops` and `category` comes straight from an unvalidated form field. All three private copies replaced with `UI.escapeHtml`. This is the same class of bug the 2026-07-29 refactor fixed elsewhere — these three files were missed then.
- **Stored XSS via plan status (S-03)** — `main.js`'s manage-plans list interpolated raw `p.status` into both a `class` attribute and a text node with no escaping, and `PUT /api/plans/<id>` accepts arbitrary strings for it (no `CHECK` constraint on the column). The class now maps onto a known-status allowlist and the display value is escaped. The server-side status enum remains open — deferred to Phase 4 where it belongs with the other schema constraints.
- **Path traversal to arbitrary in-repo file write (S-04)** — `image_service.ensure_folder()` interpolated `station_code` and `category` straight into the upload path, both attacker-controlled, so `../../../static/js` let `mkdir(parents=True)` + `save()` write into served static directories. New `_safe_path_segment()` strips separators and traversal sequences, falls back to a constant when a value reduces to nothing, and caps length; `ensure_folder()` additionally re-checks containment under `UPLOAD_ROOT` after resolution. `serve_image` re-checks containment too, since rows written before this fix could still point outside.
- **Unrestricted upload type and size (S-05)** — no extension allowlist, no size cap, no MIME check, and `serve_image` hands the stored path to `send_file()`, which infers `Content-Type` from the extension — so an uploaded `.html` or `.svg` was served as `text/html`/`image/svg+xml` from the application's own origin. Added `ALLOWED_EXTENSIONS` (SVG excluded deliberately: it is an image format that can execute script), a 10 MB per-file limit sized without buffering the payload, and a 25 MB `MAX_CONTENT_LENGTH` ceiling on all request bodies. Rejections surface as 400 with a readable message via the new `UploadRejected` exception.
- **Image filename collisions destroyed evidence (C-08)** — not in the Phase 1 brief, but fixed here because it is a two-line change inside the exact function being hardened for S-05. Filenames were `{unix_seconds}{ext}`, so two photos of the same stop and category in the same second silently overwrote each other, leaving two DB rows pointing at one file. Now suffixed with 8 hex chars of a UUID, keeping the sortable timestamp prefix.

### Added
- `app/auth.py`, `templates/login.html` (styled from the existing `style.css` variables), `GET /api/auth/status` so the frontend can show a login/logout control without probing a mutating endpoint.
- `app/config.py`: `DISPATCH_PASSWORD`, `SESSION_LIFETIME`, `MAX_UPLOAD_MB`. Deliberately **not** added to `required_env_vars` — that would make the app refuse to boot for every existing deployment; `app/auth.py` fails closed per-request instead, so the failure is visible and scoped rather than silent or total.
- `api.js` now redirects to `/login` on a 401 (preserving the return path) and surfaces the 503 "auth not configured" message verbatim rather than as a bare `HTTP 503`.
- `/api/execution/dashboard` returns `gps_matched` and `gps_available`. The dashboard already received `gps_source`/`gps_error` and displayed neither — had the status pill shown "GPS: error" instead of a green "Live" over an empty map, C-01 would have been caught on day one. Wiring these into the UI is Phase 4.

### Testing
- `pytest tests/test_delivery.py` — **59 passed, 1 failed**, up from a 48-passed baseline. The single failure (`test_delete_image_removes_file`) is an analysis-sandbox artifact: the mounted filesystem returns `Operation not permitted` on `unlink`. Verified as environmental by re-running the identical delete flow with `UPLOAD_ROOT` pointed at a writable temp dir — passes there. **Expected to pass on Windows.**
- 22 end-to-end checks driven through a real `app.test_client()` with a mocked TTAS payload: GPS reaching the dashboard, a `50E18463`-vs-`50E-18463` mismatch resolving, telemetry parsed from raw keys, coordinates not 0,0, every auth boundary (open GET, blocked POST/PUT/DELETE, wrong password, correct password, unconfigured 503), path-traversal neutralisation, and the upload allowlist and size cap. 22/22.
- The three `TestTrackingService` GPS tests that the audit flagged as encoding the *wrong* contract (T-02) were rewritten rather than patched — they fed `speed_status`-keyed dicts and so passed against a function that could never work in production. Now built on a raw-TTAS fixture and expanded from 5 tests to 13, including a parametrized sweep of the five plate formats.
- `FakeFileStorage` in the test suite gained a `.stream`, which a real Werkzeug `FileStorage` always has. Its absence had let the fake pass tests a real upload could not.

### Deployment note
**`DISPATCH_PASSWORD` must be set before the next deploy** or every mutating delivery endpoint will return 503 (reads and the rest of the app are unaffected). Not added to `render.yaml` — it is a secret and should be set in the Render dashboard, not committed.

### Known limitations / deliberately not fixed here
- Fixing C-01 restores the synchronous TTAS fetch and serial ORS calls into the request path — audit P-01/P-02. Phase 1 makes GPS *correct*, not *fast*; under 36 vehicles this will be slower than the broken version was. Ship to staging first; Phase 3 addresses it.
- `tests/test_delivery.py`'s image tests write into the real `DeliveryPlans/` upload root rather than a temp dir, and have left ~30 stray `.jpg` files there across previous runs. Test-infrastructure fix, deferred.
- `services/delivery/tracking_service.py` now transitively imports `app.config` (via `ttas_client`), which raises when `.env` is absent. Kept out of module scope via a deferred import so the pure-function tests still work without a configured environment, but the coupling is new.
- Route-layer tests exist only as the ad-hoc verification script above; the permanent suite is Phase 5.

## 2026-07-30 — Documentation Reorganization: Consolidated into docs/

Prompted directly by the redundancy this session's TLP work kept running into: the algorithm was documented three times (`SORTING_STRATEGY.md`, `SYSTEM.md`'s "Sorting Algorithm" section, `README.md`'s "Algorithm Reference" section) and had drifted — only `SORTING_STRATEGY.md` was kept current through Phases 1-6 above, so the other two were actively wrong (still describing the pre-Phase-1 4-term scorer, `LargestFirstStrategy`-only single-vehicle default, and pure `LargestVehicleFirstStrategy` multi-vehicle distribution). The delivery module was documented twice (`DELIVERY_MODULE.md`, and a smaller duplicate inside `SYSTEM.md`). User asked for all docs reorganized into a `docs/` folder with redundant/repetitive content removed, keeping documentation minimal.

### Changed
- **New canonical TLP doc**: `docs/TRUCK_LOAD_PLANNER.md` — merges the (kept-current) `SORTING_STRATEGY.md` with `SYSTEM.md`'s non-duplicated TLP content (3D step-animation controls, 2D canvas coordinate mapping, TLP database schema, auto-arrange API request/response shape, frontend validation-panel behavior). Root `SORTING_STRATEGY.md` and `SYSTEM.md` deleted — their content isn't lost, it's here, once, current.
- **Moved into `docs/`, unchanged content**: `CHANGELOG.md` (this file), `CODEBASE_ANALYSIS_REPORT.md`, `DELIVERY_MODULE.md` (already the more complete of the two delivery docs — `SYSTEM.md`'s duplicate section was simply dropped, not merged, since it had nothing `DELIVERY_MODULE.md` lacked).
- **`README.md`** (stays at repo root — universal convention): removed its stale "Algorithm Reference" and "Engine Architecture" sections (now pointers to `docs/TRUCK_LOAD_PLANNER.md`), updated the TLP test-count/command reference for `tests/test_auto_arrange_e2e.py` (added this session, Phase 5).
- **`CLAUDE.md`**: Reference Documents section updated to the new `docs/` paths; removed the `INSTRUCTIONS.md` entry (file doesn't exist — a stale reference to an already-retired original delivery-module spec, confirmed no-longer-needed).
- Fixed path references in code comments that pointed at the old root locations: `truck_load_planner/engine/support.py`, `app.py`.

### Removed
- `docs/MASTER_PLAN.md` + `docs/PHASE_1_Live_Updates.md` through `PHASE_5_Real_Time.md` — the original pre-build planning specs for the Dispatch module, which per this file's own history is already built and shipped (Phases 1-3 QA'd, see the dated entries below). Same category as the retired `INSTRUCTIONS.md`: a historical spec superseded by what's actually in the code and in this changelog, not living reference documentation.

### Not touched (explicitly out of scope)
- The two Vietnamese internship-report files at repo root — personal academic documents unrelated to the app, already flagged as out-of-scope in `CLAUDE.md`.
- `CLAUDE.md`/`AGENTS.md` themselves — agent-instruction/config files auto-loaded by tooling, not documentation-about-the-codebase; moving them would break the mechanism that reads them.

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
