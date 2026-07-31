# Graph Report - Solution  (2026-07-31)

## Corpus Check
- 118 files · ~226,161 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1947 nodes · 4140 edges · 115 communities (106 shown, 9 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 135 edges (avg confidence: 0.53)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f10cc6cd`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- truck_load_planner/routes.py
- delivery/routes.py
- test_scorer.py
- _create_plan
- planner.py
- GoogleSheetService
- delivery-plan-builder.js
- AABB
- fuel.py
- vehicle_capacity
- oil.py
- js/map.js
- LoadPlannerApp
- trips.py
- fuel-efficiency.js
- vehicle-management.js
- test_all.py
- adapters.py
- Package
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
- Container
- ApiClient
- UI
- API
- api.js
- dashboard/map.js
- migrations.py
- _MutationLogger
- vehicle-list.js
- Delivery Module — Documentation
- utils.js
- Truck Load Planner — Algorithm, API & Frontend Reference
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
- DatabaseManager
- Changelog
- BÁO CÁO KIẾN TẬP THỰC TẾ
- ttas_client.py
- check_support
- vehicle_cost.py
- Fleet Fuel Management — AI Context
- execution_service.py
- Added
- 6. Architectural Refactoring Roadmap — 4 Pillars
- Added
- 3. Python Backend Redundancies
- Added
- 2026-07-26 — Phase 1: Delivery Plan Management Rewrite
- Added
- Changed
- Codebase Analysis Report — Fleet Fuel Management System
- 4. JavaScript Frontend Redundancies
- Fleet Fuel Management
- BÁO CÁO KIẾN TẬP THỰC TẾ
- Added
- Changed
- 7. Scalability Concerns
- image_service.py
- 1.1. Tổng quan cơ sở lý thuyết
- 4.1. Mô tả chi tiết giải pháp phần mềm
- 4.2. Học hỏi từ nơi thực tập
- 2026-07-30 — Dispatch Module Phase 1: Incremental Live Updates
- auto_arrange
- Phụ lục A: Cấu trúc cơ sở dữ liệu
- Changed
- 2026-07-30 — Dispatch Module Phase 3: Operational Workspace
- 2. Redundant Files & Dead Code
- CHƯƠNG 2: MÔ TẢ CƠ QUAN THỰC TẬP THỰC TẾ
- KẾT LUẬN VÀ KIẾN NGHỊ
- 2026-07-30 — Dispatch Module Phase 2: Route Intelligence
- 2026-07-30 — Site-Wide Navigation: Fixed Dispatch Dropdown Bug + Reorganized Structure
- 9. Priority Action Items
- 5. Database & Query Redundancies
- 2026-07-19 — Dead Space Quality (Future-Packability Estimation)
- 2026-07-30 — Dispatch Module Phase 3 QA Pass: Two Bugs Fixed
- 2026-07-30 — Documentation Reorganization: Consolidated into docs/
- 2026-07-30 — Truck Load Planner Phase 1: Fixed Stacking Scoring Bias + Hard Height Cap
- 2026-07-30 — Truck Load Planner Phase 2: Fixed Empty-Space/Utilization Scoring
- 2026-07-30 — Truck Load Planner Phase 3: Performance (reduced scope)
- 2026-07-30 — Truck Load Planner Phase 4: Vehicle Candidate Selection to Minimize Truck Count
- AGENTS.md

## God Nodes (most connected - your core abstractions)
1. `LoadPlannerApp` - 133 edges
2. `Package` - 82 edges
3. `DatabaseManager` - 80 edges
4. `UI` - 73 edges
5. `Planner` - 59 edges
6. `Container` - 56 edges
7. `AABB` - 48 edges
8. `_db()` - 35 edges
9. `LoadPlanningSession` - 33 edges
10. `Placement` - 31 edges

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

## Communities (115 total, 9 thin omitted)

### Community 0 - "truck_load_planner/routes.py"
Cohesion: 0.13
Nodes (35): add_feature(), clear_all_packages(), create_container_config(), create_package(), create_plan(), create_shipment(), delete_container_config(), delete_feature() (+27 more)

### Community 1 - "delivery/routes.py"
Cohesion: 0.09
Nodes (52): calculate_eta(), calculate_etas_for_stops(), calculate_travelled_distance_km(), _compute_etas_for_stops(), get_distance_meters(), Same computation as _compute_etas_for_stops, with an optional in-memory cache…, Approximate straight-line distance already covered on this assignment: sums…, _stops_cache_key() (+44 more)

### Community 2 - "test_scorer.py"
Cohesion: 0.07
Nodes (59): _make(), Package, Placement, test_auto_arrange_uses_remaining_packages_for_rotation_choice(), test_determinism(), test_empty_placements_list(), test_generate_candidates_adds_rotation_aware_right_wall_anchor(), test_optimized_strategy_registered_and_restores_weights() (+51 more)

### Community 3 - "_create_plan"
Cohesion: 0.09
Nodes (19): _create_plan(), _create_stop(), _create_vehicle_assignment(), FakeFileStorage, Tests for tracking_service.py: TTAS speed_status is a Vietnamese status phrase,…, Tests for execution_service.py: current stop, advance, skip, cancel., Tests for execution_service.py: a plan auto-completes once every stop across…, Tests for execution_service.py: reorder_stops and insert_temp_stop. (+11 more)

### Community 4 - "planner.py"
Cohesion: 0.08
Nodes (29): Door access validation. Ensures packages can be physically inserted through a…, check_boundary(), Boundary validation — checks whether a package fits inside the container., check_collision(), Collision detection — checks whether two packages (via their AABBs) overlap.…, Return True if two AABBs overlap (i.e., a collision exists)., Backward-compatible re-export module. The AABB class previously defined here…, Planner — single entry point for all planning operations. The UI should never… (+21 more)

### Community 5 - "GoogleSheetService"
Cohesion: 0.07
Nodes (37): GoogleSheetService, parse_date_ngay(), parse_float(), parse_int(), parse_time_gio(), Any, Google Sheets Fuel Log Synchronization Service Reads fuel records from a Google…, Parse a spreadsheet date to ``YYYY-MM-DD``. Accepts ``DD/MM/YYYY`` (the… (+29 more)

### Community 6 - "delivery-plan-builder.js"
Cohesion: 0.11
Nodes (49): applyStation(), _bindDriverAutocomplete(), _bindVehicleAutocomplete(), clearAllValidation(), clearValidation(), closeMapPicker(), confirmPlan(), deleteStop() (+41 more)

### Community 7 - "AABB"
Cohesion: 0.08
Nodes (20): check_door_access(), check_door_fit(), check_door_sweep(), check_rear_door(), check_side_door(), Package, Check if package can be placed via a side door. ``right_side=True`` means door…, Cheap check (no sweep): does the package fit through the rear door? Side doors… (+12 more)

### Community 8 - "fuel.py"
Cohesion: 0.08
Nodes (46): api_fuel_log_create(), api_fuel_log_days(), api_fuel_log_delete(), api_fuel_log_export(), api_fuel_log_last_km(), api_fuel_log_list(), api_fuel_log_months(), api_fuel_log_profile_delete() (+38 more)

### Community 9 - "vehicle_capacity"
Cohesion: 0.14
Nodes (11): _vehicle_capacity(), _cheap_could_fit_all(), LargestVehicleFirstStrategy, Package, Protocol, Original behaviour: largest-capacity vehicles first., Fast necessary-condition check, no arrangement attempted. Rejects a vehicle…, Protocol for vehicle-selection strategies. ``select_vehicles`` receives the… (+3 more)

### Community 10 - "oil.py"
Cohesion: 0.13
Nodes (22): api_oil_fetch_progress(), api_oil_maintenance_create(), api_oil_maintenance_delete(), api_oil_maintenance_export(), api_oil_maintenance_list(), api_oil_maintenance_mark_done(), api_oil_maintenance_update(), _compute_oil_metrics() (+14 more)

### Community 11 - "js/map.js"
Cohesion: 0.10
Nodes (43): allLocationLabels, allLocationPolygons, applyFilters(), buildPopup(), buildStatusFilters(), buildTypeFilters(), cancelTripFromMap(), createIcon() (+35 more)

### Community 13 - "trips.py"
Cohesion: 0.11
Nodes (34): api_advance_trip(), api_cancel_trip(), api_geofence_events(), api_refresh_routes(), clear_all_trips(), clear_trip(), do_refresh_route_data(), get_route_data() (+26 more)

### Community 14 - "fuel-efficiency.js"
Cohesion: 0.11
Nodes (42): allEntries, allVehicles, applyFilters(), availableDays, changeDay(), changeMonth(), clearNormal(), closeModal() (+34 more)

### Community 15 - "vehicle-management.js"
Cohesion: 0.10
Nodes (35): allTypes, allVehicles, animate3D(), animateCamera(), attachPreviewListeners(), buildFeaturesFromForm(), bulkDelete(), closeModal() (+27 more)

### Community 16 - "test_all.py"
Cohesion: 0.22
Nodes (30): _build_engine_packages(), _load_db(), Run both engines and print side-by-side comparison., run_comparison(), avg(), cmd_benchmark_distribution(), cmd_benchmark_floor_contact(), cmd_benchmark_real_data() (+22 more)

### Community 17 - "adapters.py"
Cohesion: 0.08
Nodes (32): calculate_total_weight(), check_weight(), Weight validation — tracks running total and checks against payload. No…, Axis-Aligned Bounding Box (AABB) operations. Pure geometry — no business logic.…, calculate_total_weight(), check_boundary(), check_weight(), _PlacementWeightView (+24 more)

### Community 18 - "Package"
Cohesion: 0.14
Nodes (13): ABC, Package, _next_placement_uid(), Placement, PackingEngine, PackingResult, Package, ValidationFailure (+5 more)

### Community 19 - "manage-trips.js"
Cohesion: 0.16
Nodes (33): allLocationLabels, allLocationPolygons, calculateDistance(), cancelEditingTrip(), cancelTrip(), clearTrip(), createIcon(), escapeHtml() (+25 more)

### Community 20 - "LoadPlanningSession"
Cohesion: 0.07
Nodes (24): EnginePackage, build_placement_dict(), _log_instrument(), _pp_placement(), _print_engine_stats(), Manual test: define packages below, run full pipeline with instrumentation.…, Match the _build_placement_dict from routes.py., Run the benchmark with the specified engine and print results. (+16 more)

### Community 21 - "debug_arrange.py"
Cohesion: 0.18
Nodes (19): build_real_shipment(), fmt_breakdown(), fmt_candidate_detail(), hr(), log(), main(), pl_dim(), Package (+11 more)

### Community 23 - "PlanningState"
Cohesion: 0.07
Nodes (22): Placement, 3D uniform grid for fast AABB overlap queries. Cell size is auto-tuned from…, Register a placement and its AABB in the grid., Remove a placement (linear scan — only called on user operations)., Return (placement, aabb) pairs whose cells overlap *aabb*. Returns each…, Fast check whether anything overlaps *aabb* (early exit)., Return all grid cell keys that *aabb* overlaps., UniformGrid (+14 more)

### Community 24 - "models/__init__.py"
Cohesion: 0.09
Nodes (8): _extract_doors(), Extract rear_door from features list (side doors ignored)., ContainerFeature, LoadPlan, Package, Placement, Shipment, ShipmentItem

### Community 25 - "app/__init__.py"
Cohesion: 0.12
Nodes (17): init_db(), Database initialization orchestrator. init_db() preserves app.py's original…, create_tables(), Table definitions (CREATE TABLE IF NOT EXISTS statements). Extracted from…, create_app(), Flask app factory (Section 6.4.1, Phase 1). app.py (the project's entry point,…, load_known_locations(), create_fleet_session() (+9 more)

### Community 27 - "Planner"
Cohesion: 0.08
Nodes (16): Deprecated: kept for backward compatibility during migration., Planner, Package, setter, Score a single placement position. This is the preferred API for external…, Coordinates all subsystems for a single loading session., Score and rank candidate positions for a package. Each candidate is a dict or…, Score the entire load plan by averaging individual placement scores. Returns:… (+8 more)

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
Cohesion: 0.19
Nodes (20): api_clear_all_locations(), api_delete_location(), api_geocode(), api_known_locations(), api_manual_locations(), api_save_location(), api_update_location(), api_vehicles() (+12 more)

### Community 32 - "locations.js"
Cohesion: 0.29
Nodes (18): clearAllLocations(), clearMapLayers(), clearPendingCorners(), closeEditPanel(), deleteLocation(), escapeHtml(), getDistanceMeters(), handleMapClick() (+10 more)

### Community 34 - "fleet.py"
Cohesion: 0.18
Nodes (17): api_vehicle_set_container(), api_vehicle_types_create(), api_vehicle_types_delete(), api_vehicle_types_list(), api_vehicles_bulk_delete(), api_vehicles_create(), api_vehicles_delete(), api_vehicles_list() (+9 more)

### Community 35 - "Container"
Cohesion: 0.24
Nodes (9): _make_session(), End-to-end regression tests for auto-arrange. Unlike test_scorer.py's narrow…, test_distribute_across_vehicles_minimizes_truck_count_for_multi_truck_shipment(), test_distribute_across_vehicles_prefers_single_smallest_fitting_truck(), test_single_vehicle_realistic_shipment_all_placed_with_reasonable_utilization(), test_stack_depth_hard_cap_is_enforced(), test_stacking_used_when_floor_alone_is_insufficient(), Container (+1 more)

### Community 36 - "ApiClient"
Cohesion: 0.16
Nodes (17): populateMonthSelect(), selectVehicle(), allVehicles, closeModal(), deleteVehicle(), fetchKmData(), filteredVehicles, filterTable() (+9 more)

### Community 37 - "UI"
Cohesion: 0.21
Nodes (9): editNormal(), onVehicleInput(), onVehicleInput(), UI, addVehicleType(), deleteVehicleType(), loadTypes(), populateTypeSelect() (+1 more)

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

### Community 44 - "Delivery Module — Documentation"
Cohesion: 0.06
Nodes (35): API Endpoints, Architecture Overview, Assignments, Configuration, Dashboard Panels, Database Schema, Delivery Module — Documentation, `delivery_plan_stops` (+27 more)

### Community 45 - "utils.js"
Cohesion: 0.24
Nodes (7): calculateMultiPolygonCentroid(), calculatePolygonCentroid(), getDistanceMeters(), getLocationCentroid(), isPointInLocation(), isPointInPolygon(), showToast()

### Community 46 - "Truck Load Planner — Algorithm, API & Frontend Reference"
Cohesion: 0.06
Nodes (30): 10. Step Animation & 3D Controls, 11. Frontend: Arrange Results & Validation, 12. 2D Canvas View Coordinates, 13. Engine Architecture (`truck_load_planner/engine/`), 14. Database, 15. API: Auto-Arrange Endpoint, 1. Package Sort Order (Pre-Processing), 2. Vehicle Selection (Multi-Vehicle Distribution) (+22 more)

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

### Community 59 - "DatabaseManager"
Cohesion: 0.12
Nodes (26): DatabaseManager, Encapsulates SQLite connections for a single database file. Each `connect()`…, bulk_create_stops(), clear_plans(), confirm_import(), create_assignment(), create_driver(), create_plan() (+18 more)

### Community 60 - "Changelog"
Cohesion: 0.10
Nodes (20): 2026-07-11 — Refinements, 2026-07-13 — Container Fuel, Anomaly Detection, Vehicle Management, 2026-07-18 — Door Rendering Fixes, 2026-07-18 — Gravity, Stacking & Engine Refinement, 2026-07-18 — Inline Package Editor & Canvas UX, 2026-07-18 — Phase 3: Placement Evaluation Engine, 2026-07-18 — Phase 4: Auto Arrange Engine (v1), 2026-07-30 — Dispatch Module Phase 0: Bug Fixes (+12 more)

### Community 69 - "BÁO CÁO KIẾN TẬP THỰC TẾ"
Cohesion: 0.10
Nodes (20): 1.1. Tổng quan cơ sở lý thuyết, 1.2. Chủ đề thực tập, 1.3. Các kết quả và mục tiêu kỳ vọng, 2.1. Thông tin cơ quan, 2.2. Lịch sử hình thành và phát triển, 2.3. Cơ cấu tổ chức, nhiệm vụ chức năng của các phòng ban, 2.4. Chức năng, nhiệm vụ, phạm vi ngành nghề hoạt động, 2.5. Quy mô nhân sự và năng lực dịch vụ (+12 more)

### Community 70 - "ttas_client.py"
Cohesion: 0.16
Nodes (19): api_oil_maintenance_fetch_km(), Upsert parsed KM entries into oil_km_log using INSERT OR REPLACE. Each entry is…, Scrape the TTAS report for all vehicles from their last oil change date to…, _store_km_log(), ensure_session(), fetch_live_vehicle_data(), _fetch_ttas_report_page(), fetch_vehicle_data() (+11 more)

### Community 71 - "check_support"
Cohesion: 0.15
Nodes (14): Enum, StackingMode, _check_stacking_rules(), check_support(), _count_above(), _footprint_centre(), Package, Placement (+6 more)

### Community 72 - "vehicle_cost.py"
Cohesion: 0.18
Nodes (12): compute_fleet_cost(), compute_vehicle_floor_mm2(), compute_vehicle_volume_mm3(), _get_fuel_consumption(), Vehicle Cost Model — computes estimated transportation cost for a vehicle. Kept…, Quick pre-packing feasibility check. Returns (is_feasible, reason) where reason…, Compute actual transportation cost for a vehicle after packing. Uses actual…, Compute total transportation cost for a fleet solution. Sums the post-packing… (+4 more)

### Community 73 - "Fleet Fuel Management — AI Context"
Cohesion: 0.12
Nodes (15): AI Working Workflow, Architecture, Architecture Decision Rules, Coding Standards, Decision Making, Definition of Done, Directory Structure, Fleet Fuel Management — AI Context (+7 more)

### Community 74 - "execution_service.py"
Cohesion: 0.20
Nodes (14): advance_stop(), cancel_stop(), get_assignment_progress(), get_current_stop(), get_dashboard_data(), _get_plan_id_for_stop(), get_stop_execution(), insert_temp_stop() (+6 more)

### Community 75 - "Added"
Cohesion: 0.14
Nodes (14): 2026-07-29 — Architecture Refactor: Frontend Namespace, DatabaseManager, AABB Unification, `app/` Package Extraction, Added, `app/db.py` — `DatabaseManager`, `app/` package — extracted from the `app.py` monolith, Changed, `CLAUDE.md` (project root), `EnginePackage.from_legacy()` (`truck_load_planner/engine/package.py`), Fixed (+6 more)

### Community 76 - "6. Architectural Refactoring Roadmap — 4 Pillars"
Cohesion: 0.14
Nodes (14): 6.1.1 `app/db.py` — `DatabaseManager` Context Manager, 6.1.2 `static/js/utils.js` — `ApiClient` & `UI.toast()` Namespace, 6.1 Pillar 1: Encapsulation & Data Integrity, 6.2.1 `BaseRoutingStrategy` — Polymorphic Profile Resolution, 6.2.2 Unified Polymorphic `AABB` Class, 6.2 Pillar 2: Polymorphism & Geometry Unification, 6.3.1 `EnginePackage.from_legacy()` Factory Method, 6.3.2 Adapter Wrappers for `truck_load_planner/logistics/` (+6 more)

### Community 77 - "Added"
Cohesion: 0.15
Nodes (13): 2026-07-19 — Y-Balance, X-Preference, Rear-Proximity Scoring; Combined-Support Stacking; Rear-Door Routing; Y-Slide Fallback, Added, Candidate Priority — Removed Y Bias, Changed, Clearance Margin, Combined-Support Stacking Model, Fixed, Phase 3 — Rear-Door Redirect (Vehicle Distribution) (+5 more)

### Community 78 - "3. Python Backend Redundancies"
Cohesion: 0.15
Nodes (13): 3.10 App.py: `get_routing_profile()` Always Returns Same Value, 3.11 App.py: Duplicate Route Registration, 3.12 App.py: Duplicated Oil-Metrics Query Loop, 3.1 Duplicated Database Connection Code (4 copies), 3.2 Duplicated Stop + Execution JOIN Query (5 copies), 3.3 Duplicated Stop-Insert + Execution-Create (3 copies), 3.4 Duplicated Progress Calculation (2 copies), 3.5 Duplicated Vehicle + Container Config Query (3 copies) (+5 more)

### Community 79 - "Added"
Cohesion: 0.17
Nodes (12): 2026-07-19 — Best-Fit Decreasing, Candidate Priority, Stacking Defaults, 3D Fullscreen & Labels, 3D View Toolbar & Fullscreen, Added, Back-to-Front Loading, Best-Fit Decreasing (Vehicle Selection), Candidate Point Rotation, Candidate Priority (Pre-Validation Ranking), Changed (+4 more)

### Community 80 - "2026-07-26 — Phase 1: Delivery Plan Management Rewrite"
Cohesion: 0.17
Nodes (12): 2026-07-26 — Phase 1: Delivery Plan Management Rewrite, Added, Changed, Consolidated Test Files, Fixed, Migration Script (`scripts/migrate_to_delivery.py`), New Database Schema (6 tables, coexists with legacy `vehicle_trips`), Removed (+4 more)

### Community 81 - "Added"
Cohesion: 0.20
Nodes (10): 2026-07-18 — Multi-Vehicle Distribution, Door Access Validation, Step Animation, Added, Arrange Results Panel, Changed, Door Access Validation (`engine/access.py` — new module), Fixed, Multi-Vehicle Distribution (First-Fit Decreasing), Step Animation (Frontend) (+2 more)

### Community 82 - "Changed"
Cohesion: 0.20
Nodes (10): 2026-07-21 — Load Profile Stability Metric Fix, Floor Anchors, Local Rearrangement, Benchmark Correction, Added, Benchmark Correction, Changed, Floor Anchor Candidates, Load Profile Stability Metric, Local Rearrangement, Repair Optimizer (+2 more)

### Community 83 - "Codebase Analysis Report — Fleet Fuel Management System"
Cohesion: 0.20
Nodes (9): 10.1 Lean Root `CLAUDE.md` (<150 lines), 10.2 Directory-Level README.md Files, 10.3 Module Isolation Guidelines, 10.4 Token Budget for Common AI Tasks, 10. AI Context & Token Optimization Strategy, 1. Executive Summary, 8. Cleanup Actions Taken, Codebase Analysis Report — Fleet Fuel Management System (+1 more)

### Community 84 - "4. JavaScript Frontend Redundancies"
Cohesion: 0.20
Nodes (10): 4.1 Six Different `showToast` Implementations, 4.2 Three Identical `apiFetch` Wrappers, 4.3 Four Different `escapeHtml` / `escHtml` Implementations, 4.4 Duplicated Utility Functions in `fuel-efficiency.js` & `oil-change.js`, 4.5 Triplicated `isContainerV` Check, 4.6 Duplicated Sort Comparison Logic, 4.7 Duplicated Autocomplete Pattern (3 files), 4.8 Duplicated Modal Open/Close Pattern (3 files) (+2 more)

### Community 85 - "Fleet Fuel Management"
Cohesion: 0.20
Nodes (9): Delivery Management Tests (49 tests), Fleet Fuel Management, Pages, Project Structure, Running Tests, Tech Stack, TLP Benchmarks, Diagnostics & Manual Debugging (non-pytest), Truck Load Planner — Algorithm, API & Frontend Reference (+1 more)

### Community 86 - "BÁO CÁO KIẾN TẬP THỰC TẾ"
Cohesion: 0.22
Nodes (8): 3.1. Quy trình điều vận xe tải thùng kín và Container thực tế, 3.2. Nhận diện nút thắt (Bottlenecks), 3.3. Phân tích chất lượng dữ liệu hiện tại, BÁO CÁO KIẾN TẬP THỰC TẾ, CHƯƠNG 3: BÀI TOÁN THỰC TẾ VÀ KHẢO SÁT NGHIỆP VỤ LOGISTICS CHI TIẾT, Lý do chọn đề tài, MỞ ĐẦU, Mục đích kiến tập

### Community 87 - "Added"
Cohesion: 0.22
Nodes (9): 2026-07-22 — Frontier-Based Gap Prevention, Gap-Filling Pass, Debug Instrumentation, Added, Detailed Debug Instrumentation (`engine/auto_arrange.py`), Duplicate-Name Bug in Gap-Filling Pass, Fixed, Frontier Gap-Filling Pass (`fill_frontier_gaps` in `engine/distribution.py`), FrontierTracker (`engine/frontier.py`), Removed (+1 more)

### Community 88 - "Changed"
Cohesion: 0.22
Nodes (9): Changed, Package Sort Order, Simplified Candidate Generation (`engine/candidate_points.py`), Simplified Distribution (`engine/distribution.py`), Simplified Internal Engine (`engines/internal/engine.py`), Simplified Placement Pipeline (`engine/auto_arrange.py`), Simplified Profiles (`engine/profile.py`), Simplified Routes (`routes.py`) (+1 more)

### Community 89 - "7. Scalability Concerns"
Cohesion: 0.22
Nodes (9): 7.1 No Connection Pooling, 7.2 Global Mutable State, 7.3 No Dependency Injection, 7.4 12-Second Polling (No WebSockets/SSE), 7.5 Monolithic CSS, 7.6 No Build Step, 7.7 `app.py` Bare `except:` Blocks, 7.8 Hardcoded Values That Should Be Configurable (+1 more)

### Community 90 - "image_service.py"
Cohesion: 0.32
Nodes (6): Centralized SQLite connection management. Replaces the duplicated…, Path, delete_image(), ensure_folder(), get_image(), upload_image()

### Community 91 - "1.1. Tổng quan cơ sở lý thuyết"
Cohesion: 0.25
Nodes (8): 1.1.1. Bài toán Tối ưu hóa lộ trình (Vehicle Routing Problem — VRP), 1.1.2. Thuật toán hình học không gian áp dụng trong Định vị (Geofencing), 1.1.3. Học máy thống kê áp dụng trong Phát hiện bất thường (Anomaly Detection), 1.1.4. Kỹ nghệ dữ liệu (Data Engineering) và Tự động hóa thu thập, 1.1. Tổng quan cơ sở lý thuyết, 1.2. Chủ đề thực tập, 1.3. Các kết quả và mục tiêu kỳ vọng, CHƯƠNG 1: GIỚI THIỆU TỔNG QUAN VỀ CƠ SỞ LÝ THUYẾT VÀ CHỦ ĐỀ KIẾN TẬP

### Community 92 - "4.1. Mô tả chi tiết giải pháp phần mềm"
Cohesion: 0.25
Nodes (8): 4.1.1. Xác thực và đồng bộ dữ liệu với TTAS, 4.1.2. Cơ chế Geofencing và tự động chuyển phase, 4.1.3. Tích hợp định tuyến với OpenRouteService, 4.1.4. Mô hình phát hiện bất thường nhiên liệu, 4.1.5. Pipeline bảo dưỡng tự động, 4.1.6. Giao diện và kết quả tổng thể, 4.1.7. Tối ưu hiệu năng và hạn chế kỹ thuật, 4.1. Mô tả chi tiết giải pháp phần mềm

### Community 93 - "4.2. Học hỏi từ nơi thực tập"
Cohesion: 0.25
Nodes (8): 4.2.1. Nhận thức về khoảng cách giữa lý thuyết và thực tế, 4.2.2. Kỹ năng chuyên môn, 4.2.3. Tác phong công nghiệp và văn hóa doanh nghiệp, 4.2. Học hỏi từ nơi thực tập, 4.3.1. Tương quan giữa giảng đường và doanh nghiệp, 4.3.2. Khoảng cách lý thuyết và thực tiễn, 4.3. Đánh giá mối liên hệ giữa lý thuyết và thực tiễn, CHƯƠNG 4: KẾT QUẢ THỰC TẾ - XÂY DỰNG HỆ THỐNG PHẦN MỀM THÔNG MINH "FLEET FUEL MANAGEMENT"

### Community 94 - "2026-07-30 — Dispatch Module Phase 1: Incremental Live Updates"
Cohesion: 0.21
Nodes (8): 2026-07-30 — Dispatch Module Phase 1: Incremental Live Updates, 2026-07-30 — Dispatch Module Post-Phase-3: Plan Auto-Completion + Live Speed Signal, Added, Deferred (explicit decision, not forgotten), Fixed, Out of Scope, Remaining Technical Debt / Deferred, Testing

### Community 95 - "auto_arrange"
Cohesion: 0.25
Nodes (8): auto_arrange(), _build_placement_dict(), _distribute_across_vehicles(), _get_packages_from_request(), Convert an engine Placement to a frontend-compatible dict., Extract expanded EnginePackage list from shipment_id or inline packages., Delegate to engine.distribution.distribute_across_vehicles., Auto-arrange packages into one or more vehicles. Single-vehicle (existing…

### Community 96 - "Phụ lục A: Cấu trúc cơ sở dữ liệu"
Cohesion: 0.29
Nodes (7): A.1. Bảng `vehicle_trips` — lưu trữ chuyến hàng, A.2. Bảng `geofence_events` — nhật ký sự kiện geofence, A.3. Bảng `vehicles` — danh mục phương tiện, A.4. Bảng `fuel_log` — nhật ký đổ nhiên liệu, A.5. Bảng `oil_km_log` — lịch sử KM bảo dưỡng, A.6. Bảng `fuel_vehicle_profile` — định mức nhiên liệu, Phụ lục A: Cấu trúc cơ sở dữ liệu

### Community 97 - "Changed"
Cohesion: 0.29
Nodes (7): 2026-07-20 — Largest-Vehicle-First Fleet Distribution, Strict Unstackable Enforcement, Door-Aware Animation, Changed, Door-Used Propagation (Animation), Fleet Distribution: Best-Fit Decreasing → Largest-Vehicle-First, Package Sort: Priority-Grouped → Strict Volume Descending, Removed, Strict Unstackable Enforcement

### Community 98 - "2026-07-30 — Dispatch Module Phase 3: Operational Workspace"
Cohesion: 0.29
Nodes (7): 2026-07-30 — Dispatch Module Phase 3: Operational Workspace, Added, Changed, Fixed (self-consistency issue caught during implementation), Out of Scope, Remaining Technical Debt / Deferred, Testing

### Community 99 - "2. Redundant Files & Dead Code"
Cohesion: 0.29
Nodes (7): 2.1 Legacy `truck_load_planner/logistics/` Module, 2.2 `truck_load_planner/geometry/aabb.py` vs `engine/geometry.py`, 2.3 Dead Functions in `services/delivery/tracking_service.py`, 2.4 Dead Code in `app.py`, 2.5 Shadowed Functions in `static/js/map.js`, 2.6 Untracked Temporary/Generated Files, 2. Redundant Files & Dead Code

### Community 100 - "CHƯƠNG 2: MÔ TẢ CƠ QUAN THỰC TẬP THỰC TẾ"
Cohesion: 0.33
Nodes (6): 2.1. Thông tin cơ quan, 2.2. Lịch sử hình thành và phát triển, 2.3. Cơ cấu tổ chức, nhiệm vụ chức năng của các phòng ban, 2.4. Chức năng, nhiệm vụ, phạm vi ngành nghề hoạt động, 2.5. Quy mô nhân sự và năng lực dịch vụ, CHƯƠNG 2: MÔ TẢ CƠ QUAN THỰC TẬP THỰC TẾ

### Community 101 - "KẾT LUẬN VÀ KIẾN NGHỊ"
Cohesion: 0.33
Nodes (6): Kiến nghị, Kết luận, KẾT LUẬN VÀ KIẾN NGHỊ, Phụ lục B: Danh sách API endpoints, Phụ lục C: Cấu hình biến môi trường (`.env`), Phụ lục D: Cấu trúc thư mục mã nguồn

### Community 102 - "2026-07-30 — Dispatch Module Phase 2: Route Intelligence"
Cohesion: 0.33
Nodes (6): 2026-07-30 — Dispatch Module Phase 2: Route Intelligence, Added, Changed, Out of Scope, Remaining Technical Debt / Deferred, Testing

### Community 103 - "2026-07-30 — Site-Wide Navigation: Fixed Dispatch Dropdown Bug + Reorganized Structure"
Cohesion: 0.33
Nodes (6): 2026-07-30 — Site-Wide Navigation: Fixed Dispatch Dropdown Bug + Reorganized Structure, Changed — nav reorganization (applied identically across 9 templates: `index.html`, `delivery-dashboard.html`, `delivery-plan-builder.html`, `manage-trips.html`, `trip-history.html`, `locations.html`, `oil-change.html`, `vehicle-management.html`, `fuel-efficiency.html`), Considered and explicitly not done, Fixed, Remaining Technical Debt, Testing

### Community 104 - "9. Priority Action Items"
Cohesion: 0.33
Nodes (6): 9. Priority Action Items, Phase 1: Immediate Wins (Pillars 1 & 3) — High Impact, Low Effort, Phase 2: Structural Foundations (Pillars 1 & 4) — High Impact, Medium Effort, Phase 3: Geometry & Legacy (Pillars 2 & 3) — High Impact, Higher Effort, Phase 4: Modular Split (Pillar 4) — Foundation for AI Optimization, Phase 5: Long-Term Architecture

### Community 105 - "5. Database & Query Redundancies"
Cohesion: 0.40
Nodes (5): 5.1 N+1 Query in `get_dashboard_data()`, 5.2 App.py Opens N+1 DB Connections in Fuel Log Loop, 5.3 Dynamic SQL Injection Risk, 5.4 Migrations Not Reusable, 5. Database & Query Redundancies

### Community 106 - "2026-07-19 — Dead Space Quality (Future-Packability Estimation)"
Cohesion: 0.50
Nodes (4): 2026-07-19 — Dead Space Quality (Future-Packability Estimation), Added, Changed, Dead Space Quality Scoring

### Community 107 - "2026-07-30 — Dispatch Module Phase 3 QA Pass: Two Bugs Fixed"
Cohesion: 0.50
Nodes (4): 2026-07-30 — Dispatch Module Phase 3 QA Pass: Two Bugs Fixed, Fixed, Remaining Known Limitations (unchanged from Phase 3), Verified, no changes needed

### Community 108 - "2026-07-30 — Documentation Reorganization: Consolidated into docs/"
Cohesion: 0.50
Nodes (4): 2026-07-30 — Documentation Reorganization: Consolidated into docs/, Changed, Not touched (explicitly out of scope), Removed

### Community 109 - "2026-07-30 — Truck Load Planner Phase 1: Fixed Stacking Scoring Bias + Hard Height Cap"
Cohesion: 0.50
Nodes (4): 2026-07-30 — Truck Load Planner Phase 1: Fixed Stacking Scoring Bias + Hard Height Cap, Changed, Fixed, Testing

### Community 110 - "2026-07-30 — Truck Load Planner Phase 2: Fixed Empty-Space/Utilization Scoring"
Cohesion: 0.50
Nodes (4): 2026-07-30 — Truck Load Planner Phase 2: Fixed Empty-Space/Utilization Scoring, Fixed, Fixed during verification (not part of the original plan, found while testing), Testing

### Community 111 - "2026-07-30 — Truck Load Planner Phase 3: Performance (reduced scope)"
Cohesion: 0.50
Nodes (4): 2026-07-30 — Truck Load Planner Phase 3: Performance (reduced scope), Attempted and reverted (documented, not shipped), Fixed, Testing

### Community 112 - "2026-07-30 — Truck Load Planner Phase 4: Vehicle Candidate Selection to Minimize Truck Count"
Cohesion: 0.50
Nodes (4): 2026-07-30 — Truck Load Planner Phase 4: Vehicle Candidate Selection to Minimize Truck Count, Fixed, Fixed during verification (not part of the original plan, found while testing), Testing

## Knowledge Gaps
- **346 isolated node(s):** `$schema`, `.opencode/plugins/graphify.js`, `allEntries`, `filteredEntries`, `allVehicles` (+341 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Package` connect `Package` to `truck_load_planner/routes.py`, `test_scorer.py`, `Container`, `planner.py`, `GoogleSheetService`, `check_support`, `vehicle_capacity`, `test_all.py`, `LoadPlanningSession`, `debug_arrange.py`, `PlanningState`, `Planner`?**
  _High betweenness centrality (0.097) - this node is a cross-community bridge._
- **Why does `DatabaseManager` connect `DatabaseManager` to `truck_load_planner/routes.py`, `delivery/routes.py`, `_create_plan`, `execution_service.py`, `image_service.py`, `TestEtaService`, `auto_arrange`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Why does `UI` connect `UI` to `._getViewDims`, `ApiClient`, `.updateStatus`, `delivery-plan-builder.js`, `API`, `vehicle-list.js`, `js/map.js`, `utils.js`, `fuel-efficiency.js`, `vehicle-management.js`, `fuel-sync.js`, `.renderCanvas`, `.update3DScene`, `main.js`, `timeline.js`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `Package` (e.g. with `AutoArrangeResult` and `AutoArrangeStrategy`) actually correct?**
  _`Package` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `DatabaseManager` (e.g. with `FakeFileStorage` and `TestEtaService`) actually correct?**
  _`DatabaseManager` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `Planner` (e.g. with `AutoArrangeResult` and `StrategyRegistry`) actually correct?**
  _`Planner` has 10 INFERRED edges - model-reasoned connections that need verification._
- **What connects `$schema`, `.opencode/plugins/graphify.js`, `allEntries` to the rest of the system?**
  _346 weakly-connected nodes found - possible documentation gaps or missing edges._