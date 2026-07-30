# Graph Report - .  (2026-07-30)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1480 nodes · 3614 edges · 73 communities (66 shown, 7 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 129 edges (avg confidence: 0.53)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d1b8b2aa`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- _create_plan
- delivery/routes.py
- GoogleSheetService
- delivery-plan-builder.js
- fuel.py
- js/map.js
- Package
- fuel-efficiency.js
- validation.py
- Container
- trips.py
- vehicle-management.js
- manage-trips.js
- Planner
- LoadPlannerApp
- truck_load_planner/routes.py
- fleet.py
- test_all.py
- DatabaseManager
- manual_test.py
- PlanningState
- oil.py
- LoadPlanningSession
- API
- auto_arrange.py
- models/__init__.py
- app/__init__.py
- app.py
- ApiClient
- debug_arrange.py
- TestEtaService
- timeline.js
- ttas_client.py
- locations.js
- adapters.py
- .from_dimensions
- vehicle_cost.py
- UniformGrid
- AABB
- execution_service.py
- main.js
- dashboard/map.js
- ContainerConfig
- api.js
- UI
- _MutationLogger
- constraints.py
- vehicle-list.js
- utils.js
- logistics/placement.py
- image_service.py
- trip-history.js
- tighten_position
- calculate_multi_polygon_centroid
- fuel-sync.js
- grid.py
- polling.js
- migrate_to_delivery.py
- routes/__init__.py
- app/services/__init__.py
- utils/__init__.py
- profile.py

## God Nodes (most connected - your core abstractions)
1. `LoadPlannerApp` - 133 edges
2. `DatabaseManager` - 78 edges
3. `Package` - 72 edges
4. `UI` - 71 edges
5. `Planner` - 55 edges
6. `Container` - 51 edges
7. `AABB` - 47 edges
8. `_db()` - 33 edges
9. `Placement` - 31 edges
10. `LoadPlanningSession` - 31 edges

## Surprising Connections (you probably didn't know these)
- `get_current_stop()` --calls--> `DatabaseManager`  [EXTRACTED]
  services/delivery/execution_service.py → app/db.py
- `get_stop_execution()` --calls--> `DatabaseManager`  [EXTRACTED]
  services/delivery/execution_service.py → app/db.py
- `reorder_stops()` --calls--> `DatabaseManager`  [EXTRACTED]
  services/delivery/execution_service.py → app/db.py
- `delete_image()` --calls--> `DatabaseManager`  [EXTRACTED]
  services/delivery/image_service.py → app/db.py
- `FakeFileStorage` --uses--> `DatabaseManager`  [INFERRED]
  tests/test_delivery.py → app/db.py

## Import Cycles
- 3-file cycle: `app.py -> app/routes/trips.py -> app/services/routing.py -> app.py`

## Communities (73 total, 7 thin omitted)

### Community 0 - "_create_plan"
Cohesion: 0.08
Nodes (22): fixture, _create_plan(), _create_stop(), _create_vehicle_assignment(), db_path(), FakeFileStorage, Tests for tracking_service.py: TTAS speed_status is a Vietnamese status phrase,…, Tests for execution_service.py: current stop, advance, skip, cancel. (+14 more)

### Community 1 - "delivery/routes.py"
Cohesion: 0.10
Nodes (49): calculate_eta(), calculate_etas_for_stops(), calculate_travelled_distance_km(), _compute_etas_for_stops(), get_distance_meters(), Same computation as _compute_etas_for_stops, with an optional in-memory cache…, Approximate straight-line distance already covered on this assignment: sums…, _stops_cache_key() (+41 more)

### Community 2 - "GoogleSheetService"
Cohesion: 0.07
Nodes (36): GoogleSheetService, parse_date_ngay(), parse_float(), parse_int(), parse_time_gio(), Any, Google Sheets Fuel Log Synchronization Service Reads fuel records from a Google…, Parse a spreadsheet date to ``YYYY-MM-DD``. Accepts ``DD/MM/YYYY`` (the… (+28 more)

### Community 3 - "delivery-plan-builder.js"
Cohesion: 0.11
Nodes (49): applyStation(), _bindDriverAutocomplete(), _bindVehicleAutocomplete(), clearAllValidation(), clearValidation(), closeMapPicker(), confirmPlan(), deleteStop() (+41 more)

### Community 4 - "fuel.py"
Cohesion: 0.08
Nodes (46): api_fuel_log_create(), api_fuel_log_days(), api_fuel_log_delete(), api_fuel_log_export(), api_fuel_log_last_km(), api_fuel_log_list(), api_fuel_log_months(), api_fuel_log_profile_delete() (+38 more)

### Community 5 - "js/map.js"
Cohesion: 0.10
Nodes (43): allLocationLabels, allLocationPolygons, applyFilters(), buildPopup(), buildStatusFilters(), buildTypeFilters(), cancelTripFromMap(), createIcon() (+35 more)

### Community 6 - "Package"
Cohesion: 0.14
Nodes (38): _make(), Package, Placement, test_auto_arrange_uses_remaining_packages_for_rotation_choice(), test_determinism(), test_empty_placements_list(), test_generate_candidates_adds_rotation_aware_right_wall_anchor(), test_optimized_strategy_registered_and_restores_weights() (+30 more)

### Community 7 - "fuel-efficiency.js"
Cohesion: 0.11
Nodes (42): allEntries, allVehicles, applyFilters(), availableDays, changeDay(), changeMonth(), clearNormal(), closeModal() (+34 more)

### Community 8 - "validation.py"
Cohesion: 0.08
Nodes (35): check_door_access(), check_door_fit(), check_door_sweep(), check_rear_door(), check_side_door(), Package, Door access validation. Ensures packages can be physically inserted through a…, Check if package can be placed via a side door. ``right_side=True`` means door… (+27 more)

### Community 9 - "Container"
Cohesion: 0.14
Nodes (17): ABC, Container, _next_placement_uid(), Placement, Planner — single entry point for all planning operations. The UI should never…, Uniform Grid spatial index. Divides the container into fixed-size cells. Each…, PlanningState — holds all mutable state for a single loading session. Manages…, compute_statistics() (+9 more)

### Community 10 - "trips.py"
Cohesion: 0.11
Nodes (34): api_advance_trip(), api_cancel_trip(), api_geofence_events(), api_refresh_routes(), clear_all_trips(), clear_trip(), do_refresh_route_data(), get_route_data() (+26 more)

### Community 11 - "vehicle-management.js"
Cohesion: 0.10
Nodes (35): allTypes, allVehicles, animate3D(), animateCamera(), attachPreviewListeners(), buildFeaturesFromForm(), bulkDelete(), closeModal() (+27 more)

### Community 12 - "manage-trips.js"
Cohesion: 0.16
Nodes (33): allLocationLabels, allLocationPolygons, calculateDistance(), cancelEditingTrip(), cancelTrip(), clearTrip(), createIcon(), escapeHtml() (+25 more)

### Community 13 - "Planner"
Cohesion: 0.09
Nodes (13): test_placement_score_to_dict(), Deprecated: kept for backward compatibility during migration., Planner, Package, setter, Score a single placement position. This is the preferred API for external…, Coordinates all subsystems for a single loading session., Score and rank candidate positions for a package. Each candidate is a dict or… (+5 more)

### Community 15 - "truck_load_planner/routes.py"
Cohesion: 0.15
Nodes (31): add_feature(), clear_all_packages(), create_container_config(), create_package(), create_plan(), create_shipment(), delete_container_config(), delete_feature() (+23 more)

### Community 16 - "fleet.py"
Cohesion: 0.10
Nodes (29): add_missing_fuel_columns(), add_missing_vehicle_trips_columns(), backfill_vehicles_from_fuel_log(), migrate_legacy_vehicle_trips_schema(), migrate_tlp_extensions(), Column migrations and data backfill for existing databases. Extracted from…, Rename+recreate vehicle_trips if it predates the id-primary-key schema. Must…, Backfill vehicles + fuel_log.vehicle_id from existing fuel_log entries. (+21 more)

### Community 17 - "test_all.py"
Cohesion: 0.25
Nodes (28): _build_engine_packages(), _load_db(), avg(), cmd_benchmark_distribution(), cmd_benchmark_floor_contact(), cmd_benchmark_real_data(), cmd_debug_py3dbp(), cmd_debug_stats() (+20 more)

### Community 18 - "DatabaseManager"
Cohesion: 0.13
Nodes (24): DatabaseManager, Encapsulates SQLite connections for a single database file. Each `connect()`…, bulk_create_stops(), confirm_import(), create_assignment(), create_driver(), create_plan(), create_stop() (+16 more)

### Community 19 - "manual_test.py"
Cohesion: 0.12
Nodes (19): build_placement_dict(), _log_instrument(), _pp_placement(), _print_engine_stats(), Manual test: define packages below, run full pipeline with instrumentation.…, Match the _build_placement_dict from routes.py., Run the benchmark with the specified engine and print results., Run both engines and print side-by-side comparison. (+11 more)

### Community 20 - "PlanningState"
Cohesion: 0.11
Nodes (13): PlanningState, Package, Placement, setter, Insert a placement at *index* and rebuild extreme points + grid., Return extreme points sorted by z, x, y — no regeneration., Replace all placements from saved data and rebuild indices., Return (placement, aabb) pairs whose grid cells overlap *aabb*. Used by the… (+5 more)

### Community 21 - "oil.py"
Cohesion: 0.12
Nodes (24): api_oil_fetch_progress(), api_oil_maintenance_create(), api_oil_maintenance_delete(), api_oil_maintenance_export(), api_oil_maintenance_fetch_km(), api_oil_maintenance_list(), api_oil_maintenance_mark_done(), api_oil_maintenance_update() (+16 more)

### Community 22 - "LoadPlanningSession"
Cohesion: 0.10
Nodes (13): EnginePackage, _engine_placement_to_dict(), _from_legacy_dict(), LoadPlanningSession, Placement, Run auto-arrange for a set of packages. Accepts either a list of shipment items…, Convert a legacy Package (from models) to engine Package., Build an engine Package from a legacy dict (underscore keys). (+5 more)

### Community 24 - "auto_arrange.py"
Cohesion: 0.17
Nodes (12): Protocol, AutoArrangeResult, AutoArrangeStrategy, _footprint(), _largest_first_order(), LargestFirstStrategy, OptimizedStrategy, Package (+4 more)

### Community 25 - "models/__init__.py"
Cohesion: 0.09
Nodes (8): _extract_doors(), Extract rear_door from features list (side doors ignored)., ContainerFeature, LoadPlan, Package, Placement, Shipment, ShipmentItem

### Community 26 - "app/__init__.py"
Cohesion: 0.12
Nodes (15): Application configuration — environment variable reads and constants. Extracted…, init_db(), Database initialization orchestrator. init_db() preserves app.py's original…, create_tables(), Table definitions (CREATE TABLE IF NOT EXISTS statements). Extracted from…, create_app(), Flask app factory (Section 6.4.1, Phase 1). app.py (the project's entry point,…, load_known_locations() (+7 more)

### Community 27 - "app.py"
Cohesion: 0.21
Nodes (19): api_clear_all_locations(), api_delete_location(), api_geocode(), api_known_locations(), api_manual_locations(), api_save_location(), api_update_location(), api_vehicles() (+11 more)

### Community 28 - "ApiClient"
Cohesion: 0.16
Nodes (17): populateMonthSelect(), selectVehicle(), allVehicles, closeModal(), deleteVehicle(), fetchKmData(), filteredVehicles, filterTable() (+9 more)

### Community 30 - "debug_arrange.py"
Cohesion: 0.18
Nodes (19): build_real_shipment(), fmt_breakdown(), fmt_candidate_detail(), hr(), log(), main(), pl_dim(), Package (+11 more)

### Community 31 - "TestEtaService"
Cohesion: 0.14
Nodes (4): Exception, patch, Tests for eta_service.py: Haversine fallback and ORS integration., TestEtaService

### Community 32 - "timeline.js"
Cohesion: 0.24
Nodes (18): bindActionDelegation(), bindPhotosToggle(), buildActionsHtml(), buildDetailHtml(), clear(), confirmReason(), createStop(), escapeHtml() (+10 more)

### Community 33 - "ttas_client.py"
Cohesion: 0.18
Nodes (17): ensure_session(), fetch_live_vehicle_data(), _fetch_ttas_report_page(), fetch_vehicle_data(), get_session_cookies(), LiveVehicleFetchError, load_last_json_document(), load_sample_data() (+9 more)

### Community 34 - "locations.js"
Cohesion: 0.29
Nodes (18): clearAllLocations(), clearMapLayers(), clearPendingCorners(), closeEditPanel(), deleteLocation(), escapeHtml(), getDistanceMeters(), handleMapClick() (+10 more)

### Community 37 - "adapters.py"
Cohesion: 0.18
Nodes (13): calculate_total_weight(), check_weight(), Weight validation — tracks running total and checks against payload. No…, calculate_total_weight(), check_boundary(), check_weight(), _PlacementWeightView, Adapters delegating truck_load_planner/logistics/ calls to their… (+5 more)

### Community 38 - ".from_dimensions"
Cohesion: 0.15
Nodes (12): Enum, StackingMode, _check_stacking_rules(), check_support(), _count_above(), _footprint_centre(), Package, Stacking support validation. Ensures packages are placed on adequate support… (+4 more)

### Community 39 - "vehicle_cost.py"
Cohesion: 0.18
Nodes (12): compute_fleet_cost(), compute_vehicle_floor_mm2(), compute_vehicle_volume_mm3(), _get_fuel_consumption(), Vehicle Cost Model — computes estimated transportation cost for a vehicle. Kept…, Quick pre-packing feasibility check. Returns (is_feasible, reason) where reason…, Compute actual transportation cost for a vehicle after packing. Uses actual…, Compute total transportation cost for a fleet solution. Sums the post-packing… (+4 more)

### Community 41 - "UniformGrid"
Cohesion: 0.19
Nodes (8): Placement, 3D uniform grid for fast AABB overlap queries. Cell size is auto-tuned from…, Register a placement and its AABB in the grid., Remove a placement (linear scan — only called on user operations)., Return (placement, aabb) pairs whose cells overlap *aabb*. Returns each…, Fast check whether anything overlaps *aabb* (early exit)., Return all grid cell keys that *aabb* overlaps., UniformGrid

### Community 42 - "AABB"
Cohesion: 0.12
Nodes (5): AABB, An axis-aligned bounding box defined by min/max corners., Check if two AABBs overlap in 3D space., Check if this AABB fully contains another., Check if point is strictly inside (exclusive on max boundaries). A point on the…

### Community 43 - "execution_service.py"
Cohesion: 0.20
Nodes (14): advance_stop(), cancel_stop(), get_assignment_progress(), get_current_stop(), get_dashboard_data(), _get_plan_id_for_stop(), get_stop_execution(), insert_temp_stop() (+6 more)

### Community 44 - "main.js"
Cohesion: 0.34
Nodes (14): applyFilters(), bindFilterEvents(), bindMapControls(), escapeHtml(), getCurrentStopId(), init(), loadAssignmentDetail(), loadPlans() (+6 more)

### Community 45 - "dashboard/map.js"
Cohesion: 0.21
Nodes (6): escapeHtml(), statusColor(), stopPopupHtml(), updateStops(), updateVehicles(), vehiclePopupHtml()

### Community 46 - "ContainerConfig"
Cohesion: 0.13
Nodes (13): ContainerConfig, auto_arrange(), _build_placement_dict(), _distribute_across_vehicles(), _get_packages_from_request(), _load_vehicle_session(), Validate a single placement without saving. Body: { vehicle_id, package_id, x,…, Convert an engine Placement to a frontend-compatible dict. (+5 more)

### Community 47 - "api.js"
Cohesion: 0.29
Nodes (12): advance(), cancel(), dashboard(), drivers(), eta(), fetchJSON(), planDetail(), plans() (+4 more)

### Community 48 - "UI"
Cohesion: 0.21
Nodes (9): editNormal(), onVehicleInput(), onVehicleInput(), UI, addVehicleType(), deleteVehicleType(), loadTypes(), populateTypeSelect() (+1 more)

### Community 50 - "constraints.py"
Cohesion: 0.19
Nodes (10): Axis-Aligned Bounding Box (AABB) operations. Pure geometry — no business logic.…, check_constraints(), feature_to_aabb(), get_constraint_aabbs(), get_door_status(), Constraint system — generic container feature detection. Replaces door.py with…, Return accessible/blocked status for each door-like feature., Convert a container feature to an AABB constraint region. Feature types and… (+2 more)

### Community 51 - "vehicle-list.js"
Cohesion: 0.35
Nodes (11): attentionReasonText(), _bindAttentionToggle(), computeAttention(), createCard(), _formatTime(), _patchCard(), render(), _renderAttentionStrip() (+3 more)

### Community 52 - "utils.js"
Cohesion: 0.24
Nodes (7): calculateMultiPolygonCentroid(), calculatePolygonCentroid(), getDistanceMeters(), getLocationCentroid(), isPointInLocation(), isPointInPolygon(), showToast()

### Community 53 - "logistics/placement.py"
Cohesion: 0.23
Nodes (10): Placement orchestrator — coordinates all validation checks before accepting a…, Validate whether a package can be placed at (x, y, z). Args: placements:…, try_place(), calculate_occupied_m3(), check_volume(), container_volume_m3(), Volume validation — computes occupied and remaining volume from dimensions.…, Compute container cargo volume from dimensions in m³. (+2 more)

### Community 54 - "image_service.py"
Cohesion: 0.28
Nodes (7): Centralized SQLite connection management. Replaces the duplicated…, Path, delete_image(), ensure_folder(), get_image(), list_images(), upload_image()

### Community 55 - "trip-history.js"
Cohesion: 0.44
Nodes (8): clearAllTrips(), closeEditModal(), deleteTrip(), escapeHtml(), loadTrips(), openEditModal(), renderTrips(), saveTrip()

### Community 56 - "tighten_position"
Cohesion: 0.57
Nodes (7): _effective_floor_dimensions(), generate_candidates(), _is_valid(), Package, _slide_lower_axis(), tighten_position(), find_best_for_pkg()

### Community 57 - "calculate_multi_polygon_centroid"
Cohesion: 0.40
Nodes (6): calculate_multi_polygon_centroid(), calculate_polygon_centroid(), get_location_centroid(), Get centroid from a location object, handling single polygon, multi-polygon, or…, Calculate centroid (center) of a polygon given as list of [lat, lng] points.…, Calculate centroid of a multi-polygon (multiple polygons), returns weighted…

### Community 58 - "fuel-sync.js"
Cohesion: 0.60
Nodes (5): fmtDuration(), loadLastSync(), refreshDashboard(), triggerSync(), updateSyncBadge()

### Community 59 - "grid.py"
Cohesion: 0.40
Nodes (5): Grid snapping utilities. Pure geometry — no business logic., Snap both x and y coordinates to the grid., Snap a coordinate to the nearest grid step., snap_point(), snap_to_grid()

### Community 60 - "polling.js"
Cohesion: 0.60
Nodes (3): refreshNow(), setStatus(), stop()

### Community 61 - "migrate_to_delivery.py"
Cohesion: 0.67
Nodes (3): get_conn(), migrate(), Migration script: export old vehicle_trips data into the new delivery schema.…

## Knowledge Gaps
- **27 isolated node(s):** `allEntries`, `filteredEntries`, `allVehicles`, `availableDays`, `MAP_CENTER` (+22 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Package` connect `Package` to `GoogleSheetService`, `.from_dimensions`, `validation.py`, `Container`, `Planner`, `truck_load_planner/routes.py`, `test_all.py`, `manual_test.py`, `PlanningState`, `LoadPlanningSession`, `auto_arrange.py`, `tighten_position`, `debug_arrange.py`?**
  _High betweenness centrality (0.134) - this node is a cross-community bridge._
- **Why does `DatabaseManager` connect `DatabaseManager` to `_create_plan`, `execution_service.py`, `ContainerConfig`, `truck_load_planner/routes.py`, `image_service.py`, `TestEtaService`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Why does `UI` connect `UI` to `timeline.js`, `delivery-plan-builder.js`, `.updateStatus`, `js/map.js`, `._getViewDims`, `fuel-efficiency.js`, `.renderCanvas`, `vehicle-management.js`, `vehicle-list.js`, `utils.js`, `API`, `fuel-sync.js`, `ApiClient`, `.update3DScene`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `DatabaseManager` (e.g. with `FakeFileStorage` and `TestEtaService`) actually correct?**
  _`DatabaseManager` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `Package` (e.g. with `AutoArrangeResult` and `AutoArrangeStrategy`) actually correct?**
  _`Package` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `Planner` (e.g. with `AutoArrangeResult` and `StrategyRegistry`) actually correct?**
  _`Planner` has 10 INFERRED edges - model-reasoned connections that need verification._
- **What connects `allEntries`, `filteredEntries`, `allVehicles` to the rest of the system?**
  _27 weakly-connected nodes found - possible documentation gaps or missing edges._