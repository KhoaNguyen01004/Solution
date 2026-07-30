# Graph Report - .  (2026-07-30)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1536 nodes · 3605 edges · 69 communities (59 shown, 10 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 132 edges (avg confidence: 0.55)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8cf79fe3`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- DatabaseManager
- delivery/routes.py
- test_scorer.py
- _create_plan
- planner.py
- GoogleSheetService
- delivery-plan-builder.js
- AABB
- fuel.py
- auto_arrange.py
- oil.py
- js/map.js
- LoadPlannerApp
- trips.py
- fuel-efficiency.js
- vehicle-management.js
- Package
- adapters.py
- Container
- manage-trips.js
- LoadPlanningSession
- debug_arrange.py
- PlanningState
- models/__init__.py
- app/__init__.py
- Planner
- TestEtaService
- main.js
- timeline.js
- app.py
- locations.js
- fleet.py
- distribute_across_vehicles
- oil-change.js
- UI
- API
- api.js
- dashboard/map.js
- migrations.py
- _MutationLogger
- vehicle-list.js
- utils.js
- eta_service.py
- trip-history.js
- calculate_multi_polygon_centroid
- fuel-sync.js
- grid.py
- polling.js
- opencode.json
- migrate_to_delivery.py
- graphify.js
- routes/__init__.py
- app/services/__init__.py
- utils/__init__.py
- profile.py
- Protocol
- route

## God Nodes (most connected - your core abstractions)
1. `LoadPlannerApp` - 133 edges
2. `DatabaseManager` - 58 edges
3. `UI` - 48 edges
4. `Planner` - 47 edges
5. `Container` - 45 edges
6. `Package` - 44 edges
7. `AABB` - 39 edges
8. `_db()` - 35 edges
9. `LoadPlanningSession` - 31 edges
10. `_create_plan()` - 28 edges

## Surprising Connections (you probably didn't know these)
- `FakeFileStorage` --uses--> `DatabaseManager`  [INFERRED]
  tests/test_delivery.py → app/db.py
- `TestEtaService` --uses--> `DatabaseManager`  [INFERRED]
  tests/test_delivery.py → app/db.py
- `TestImageService` --uses--> `DatabaseManager`  [INFERRED]
  tests/test_delivery.py → app/db.py
- `TestPlanAutoCompletion` --uses--> `DatabaseManager`  [INFERRED]
  tests/test_delivery.py → app/db.py
- `TestProgress` --uses--> `DatabaseManager`  [INFERRED]
  tests/test_delivery.py → app/db.py

## Import Cycles
- 3-file cycle: `app.py -> app/routes/trips.py -> app/services/routing.py -> app.py`

## Communities (69 total, 10 thin omitted)

### Community 0 - "DatabaseManager"
Cohesion: 0.05
Nodes (78): DatabaseManager, Centralized SQLite connection management. Replaces the duplicated…, Encapsulates SQLite connections for a single database file. Each `connect()`…, Path, advance_stop(), cancel_stop(), get_assignment_progress(), get_current_stop() (+70 more)

### Community 1 - "delivery/routes.py"
Cohesion: 0.07
Nodes (47): route, confirm_import(), create_assignment(), create_plan(), create_stop(), delete_plans(), parse_excel_rows(), preview_import() (+39 more)

### Community 2 - "test_scorer.py"
Cohesion: 0.08
Nodes (53): Container, Planner, test_single_vehicle_realistic_shipment_all_placed_with_reasonable_utilization(), test_stack_depth_hard_cap_is_enforced(), test_stacking_used_when_floor_alone_is_insufficient(), _make(), Package, Placement (+45 more)

### Community 3 - "_create_plan"
Cohesion: 0.07
Nodes (26): fixture, normalize_gps_position(), _parse_speed_kmh(), Defensively extracts a numeric km/h reading from TTAS's raw speed text — a…, Flat dict of normalized telemetry — new fields (e.g. heading) can be added here…, _create_plan(), _create_stop(), _create_vehicle_assignment() (+18 more)

### Community 4 - "planner.py"
Cohesion: 0.06
Nodes (43): Door access validation. Ensures packages can be physically inserted through a…, check_boundary(), Boundary validation — checks whether a package fits inside the container., check_collision(), Collision detection — checks whether two packages (via their AABBs) overlap.…, Return True if two AABBs overlap (i.e., a collision exists)., Backward-compatible re-export module. The AABB class previously defined here…, Enum (+35 more)

### Community 5 - "GoogleSheetService"
Cohesion: 0.07
Nodes (36): GoogleSheetService, parse_date_ngay(), parse_float(), parse_int(), parse_time_gio(), Any, Google Sheets Fuel Log Synchronization Service Reads fuel records from a Google…, Parse a spreadsheet date to ``YYYY-MM-DD``. Accepts ``DD/MM/YYYY`` (the… (+28 more)

### Community 6 - "delivery-plan-builder.js"
Cohesion: 0.11
Nodes (49): applyStation(), _bindDriverAutocomplete(), _bindVehicleAutocomplete(), clearAllValidation(), clearValidation(), closeMapPicker(), confirmPlan(), deleteStop() (+41 more)

### Community 7 - "AABB"
Cohesion: 0.06
Nodes (28): check_door_access(), check_door_fit(), check_door_sweep(), check_rear_door(), check_side_door(), Package, Check if package can be placed via a side door. ``right_side=True`` means door…, Cheap check (no sweep): does the package fit through the rear door? Side doors… (+20 more)

### Community 8 - "fuel.py"
Cohesion: 0.08
Nodes (46): api_fuel_log_create(), api_fuel_log_days(), api_fuel_log_delete(), api_fuel_log_export(), api_fuel_log_last_km(), api_fuel_log_list(), api_fuel_log_months(), api_fuel_log_profile_delete() (+38 more)

### Community 9 - "auto_arrange.py"
Cohesion: 0.08
Nodes (27): AutoArrangeResult, AutoArrangeStrategy, _footprint(), _largest_first_order(), LargestFirstStrategy, OptimizedStrategy, Package, Protocol (+19 more)

### Community 10 - "oil.py"
Cohesion: 0.08
Nodes (42): api_oil_fetch_progress(), api_oil_maintenance_create(), api_oil_maintenance_delete(), api_oil_maintenance_export(), api_oil_maintenance_fetch_km(), api_oil_maintenance_list(), api_oil_maintenance_mark_done(), api_oil_maintenance_update() (+34 more)

### Community 11 - "js/map.js"
Cohesion: 0.10
Nodes (43): allLocationLabels, allLocationPolygons, applyFilters(), buildPopup(), buildStatusFilters(), buildTypeFilters(), cancelTripFromMap(), createIcon() (+35 more)

### Community 13 - "trips.py"
Cohesion: 0.11
Nodes (34): api_advance_trip(), api_cancel_trip(), api_geofence_events(), api_refresh_routes(), clear_all_trips(), clear_trip(), do_refresh_route_data(), get_route_data() (+26 more)

### Community 14 - "fuel-efficiency.js"
Cohesion: 0.11
Nodes (36): allEntries, allVehicles, applyFilters(), availableDays, changeDay(), changeMonth(), closeModal(), exportCsv() (+28 more)

### Community 15 - "vehicle-management.js"
Cohesion: 0.10
Nodes (36): allTypes, allVehicles, animate3D(), animateCamera(), attachPreviewListeners(), buildFeaturesFromForm(), bulkDelete(), closeModal() (+28 more)

### Community 16 - "Package"
Cohesion: 0.21
Nodes (27): avg(), cmd_benchmark_distribution(), cmd_benchmark_floor_contact(), cmd_benchmark_real_data(), cmd_debug_py3dbp(), cmd_debug_stats(), cmd_debug_validation(), cmd_debug_vehicles() (+19 more)

### Community 17 - "adapters.py"
Cohesion: 0.08
Nodes (28): Axis-Aligned Bounding Box (AABB) operations. Pure geometry — no business logic.…, calculate_total_weight(), check_boundary(), check_weight(), _PlacementWeightView, Adapters delegating truck_load_planner/logistics/ calls to their…, Adapter: package/container AABBs are already the unified engine AABB type, so…, Minimal read-only adapter exposing what engine.weight functions expect… (+20 more)

### Community 18 - "Container"
Cohesion: 0.15
Nodes (14): ABC, Container, Placement, compute_statistics(), Statistics engine — computes all KPIs from placements and container., Compute loading statistics for the current plan. Returns: { "packages_placed":…, PackingEngine, PackingResult (+6 more)

### Community 19 - "manage-trips.js"
Cohesion: 0.16
Nodes (33): allLocationLabels, allLocationPolygons, calculateDistance(), cancelEditingTrip(), cancelTrip(), clearTrip(), createIcon(), escapeHtml() (+25 more)

### Community 20 - "LoadPlanningSession"
Cohesion: 0.09
Nodes (14): EnginePackage, ContainerConfig, _engine_placement_to_dict(), _from_legacy_dict(), LoadPlanningSession, Placement, Run auto-arrange for a set of packages. Accepts either a list of shipment items…, Convert a legacy Package (from models) to engine Package. (+6 more)

### Community 21 - "debug_arrange.py"
Cohesion: 0.15
Nodes (25): build_real_shipment(), fmt_breakdown(), fmt_candidate_detail(), hr(), log(), main(), pl_dim(), Package (+17 more)

### Community 23 - "PlanningState"
Cohesion: 0.12
Nodes (14): PlanningState, Package, Placement, setter, Insert a placement at *index* and rebuild extreme points + grid., Return extreme points sorted by z, x, y — no regeneration., Replace all placements from saved data and rebuild indices., Return (placement, aabb) pairs whose grid cells overlap *aabb*. Used by the… (+6 more)

### Community 24 - "models/__init__.py"
Cohesion: 0.09
Nodes (8): _extract_doors(), Extract rear_door from features list (side doors ignored)., ContainerFeature, LoadPlan, Package, Placement, Shipment, ShipmentItem

### Community 25 - "app/__init__.py"
Cohesion: 0.13
Nodes (15): Application configuration — environment variable reads and constants. Extracted…, init_db(), Database initialization orchestrator. init_db() preserves app.py's original…, create_tables(), Table definitions (CREATE TABLE IF NOT EXISTS statements). Extracted from…, create_app(), Flask app factory (Section 6.4.1, Phase 1). app.py (the project's entry point,…, load_known_locations() (+7 more)

### Community 27 - "Planner"
Cohesion: 0.13
Nodes (8): Planner, setter, Coordinates all subsystems for a single loading session., Validate a single candidate position without placing., Package, Run all validation checks in progressive order (cheapest first). Checks:…, validate_placement(), ValidationResult

### Community 28 - "TestEtaService"
Cohesion: 0.14
Nodes (4): Exception, patch, Tests for eta_service.py: Haversine fallback and ORS integration., TestEtaService

### Community 29 - "main.js"
Cohesion: 0.27
Nodes (19): applyFilters(), bindFilterEvents(), bindManagePlansEvents(), bindMapControls(), clearAllPlans(), deleteSelectedPlans(), escapeHtml(), getCurrentStopId() (+11 more)

### Community 30 - "timeline.js"
Cohesion: 0.24
Nodes (18): bindActionDelegation(), bindPhotosToggle(), buildActionsHtml(), buildDetailHtml(), clear(), confirmReason(), createStop(), escapeHtml() (+10 more)

### Community 31 - "app.py"
Cohesion: 0.23
Nodes (18): api_clear_all_locations(), api_delete_location(), api_geocode(), api_known_locations(), api_manual_locations(), api_save_location(), api_update_location(), api_vehicles() (+10 more)

### Community 32 - "locations.js"
Cohesion: 0.29
Nodes (18): clearAllLocations(), clearMapLayers(), clearPendingCorners(), closeEditPanel(), deleteLocation(), escapeHtml(), getDistanceMeters(), handleMapClick() (+10 more)

### Community 34 - "fleet.py"
Cohesion: 0.18
Nodes (17): api_vehicle_set_container(), api_vehicle_types_create(), api_vehicle_types_delete(), api_vehicle_types_list(), api_vehicles_bulk_delete(), api_vehicles_create(), api_vehicles_delete(), api_vehicles_list() (+9 more)

### Community 35 - "distribute_across_vehicles"
Cohesion: 0.16
Nodes (20): _build_engine_packages(), build_placement_dict(), _load_db(), _log_instrument(), _pp_placement(), _print_engine_stats(), Manual test: define packages below, run full pipeline with instrumentation.…, Match the _build_placement_dict from routes.py. (+12 more)

### Community 36 - "oil-change.js"
Cohesion: 0.18
Nodes (14): allVehicles, closeModal(), deleteVehicle(), fetchKmData(), filteredVehicles, filterTable(), handleOverlayClick(), loadVehicles() (+6 more)

### Community 37 - "UI"
Cohesion: 0.26
Nodes (17): clearNormal(), deleteEntry(), editNormal(), formatDateTime(), loadDashboard(), loadProfiles(), onVehicleInput(), renderProfiles() (+9 more)

### Community 39 - "api.js"
Cohesion: 0.26
Nodes (14): advance(), cancel(), clearPlans(), dashboard(), deletePlans(), drivers(), eta(), fetchJSON() (+6 more)

### Community 40 - "dashboard/map.js"
Cohesion: 0.21
Nodes (6): escapeHtml(), statusColor(), stopPopupHtml(), updateStops(), updateVehicles(), vehiclePopupHtml()

### Community 41 - "migrations.py"
Cohesion: 0.22
Nodes (12): add_missing_fuel_columns(), add_missing_vehicle_trips_columns(), backfill_vehicles_from_fuel_log(), migrate_legacy_vehicle_trips_schema(), migrate_tlp_extensions(), Column migrations and data backfill for existing databases. Extracted from…, Rename+recreate vehicle_trips if it predates the id-primary-key schema. Must…, Backfill vehicles + fuel_log.vehicle_id from existing fuel_log entries. (+4 more)

### Community 43 - "vehicle-list.js"
Cohesion: 0.35
Nodes (11): attentionReasonText(), _bindAttentionToggle(), computeAttention(), createCard(), _formatTime(), _patchCard(), render(), _renderAttentionStrip() (+3 more)

### Community 45 - "utils.js"
Cohesion: 0.24
Nodes (7): calculateMultiPolygonCentroid(), calculatePolygonCentroid(), getDistanceMeters(), getLocationCentroid(), isPointInLocation(), isPointInPolygon(), showToast()

### Community 46 - "eta_service.py"
Cohesion: 0.39
Nodes (8): calculate_eta(), calculate_etas_for_stops(), calculate_travelled_distance_km(), _compute_etas_for_stops(), get_distance_meters(), Same computation as _compute_etas_for_stops, with an optional in-memory cache…, Approximate straight-line distance already covered on this assignment: sums…, _stops_cache_key()

### Community 47 - "trip-history.js"
Cohesion: 0.44
Nodes (8): clearAllTrips(), closeEditModal(), deleteTrip(), escapeHtml(), loadTrips(), openEditModal(), renderTrips(), saveTrip()

### Community 48 - "calculate_multi_polygon_centroid"
Cohesion: 0.40
Nodes (6): calculate_multi_polygon_centroid(), calculate_polygon_centroid(), get_location_centroid(), Get centroid from a location object, handling single polygon, multi-polygon, or…, Calculate centroid (center) of a polygon given as list of [lat, lng] points.…, Calculate centroid of a multi-polygon (multiple polygons), returns weighted…

### Community 49 - "fuel-sync.js"
Cohesion: 0.60
Nodes (5): fmtDuration(), loadLastSync(), refreshDashboard(), triggerSync(), updateSyncBadge()

### Community 50 - "grid.py"
Cohesion: 0.40
Nodes (5): Grid snapping utilities. Pure geometry — no business logic., Snap both x and y coordinates to the grid., Snap a coordinate to the nearest grid step., snap_point(), snap_to_grid()

### Community 51 - "polling.js"
Cohesion: 0.60
Nodes (3): refreshNow(), setStatus(), stop()

### Community 52 - "opencode.json"
Cohesion: 0.50
Nodes (3): plugin, $schema, .opencode/plugins/graphify.js

### Community 53 - "migrate_to_delivery.py"
Cohesion: 0.67
Nodes (3): get_conn(), migrate(), Migration script: export old vehicle_trips data into the new delivery schema.…

## Knowledge Gaps
- **29 isolated node(s):** `allEntries`, `filteredEntries`, `allVehicles`, `availableDays`, `MAP_CENTER` (+24 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Package` connect `Package` to `DatabaseManager`, `test_scorer.py`, `distribute_across_vehicles`, `planner.py`, `GoogleSheetService`, `Container`, `LoadPlanningSession`, `debug_arrange.py`, `PlanningState`, `Planner`?**
  _High betweenness centrality (0.121) - this node is a cross-community bridge._
- **Why does `DatabaseManager` connect `DatabaseManager` to `_create_plan`, `TestEtaService`?**
  _High betweenness centrality (0.105) - this node is a cross-community bridge._
- **Why does `GoogleSheetService` connect `GoogleSheetService` to `fuel.py`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `DatabaseManager` (e.g. with `FakeFileStorage` and `TestEtaService`) actually correct?**
  _`DatabaseManager` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `Planner` (e.g. with `AutoArrangeResult` and `StrategyRegistry`) actually correct?**
  _`Planner` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `Container` (e.g. with `Planner` and `PlanningState`) actually correct?**
  _`Container` has 10 INFERRED edges - model-reasoned connections that need verification._
- **What connects `allEntries`, `filteredEntries`, `allVehicles` to the rest of the system?**
  _29 weakly-connected nodes found - possible documentation gaps or missing edges._