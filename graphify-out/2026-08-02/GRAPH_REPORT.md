# Graph Report - Solution  (2026-07-31)

## Corpus Check
- 120 files · ~258,797 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2271 nodes · 4611 edges · 153 communities (137 shown, 16 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 137 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bc7ee485`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- truck_load_planner/routes.py
- delivery/routes.py
- Package
- _create_plan
- planner.py
- GoogleSheetService
- delivery-plan-builder.js
- Container
- fuel.py
- auto_arrange.py
- oil.py
- js/map.js
- LoadPlannerApp
- trips.py
- fuel-efficiency.js
- vehicle-management.js
- test_all.py
- AABB
- LoadPlanningSession
- adapters.py
- normalize_plate
- debug_arrange.py
- PlanningState
- models/__init__.py
- init_db
- Planner
- TestEtaService
- main.js
- timeline.js
- app.py
- locations.js
- fleet.py
- with_gps
- oil-change.js
- ApiClient
- UI
- api.js
- dashboard/map.js
- migrations.py
- _MutationLogger
- vehicle-list.js
- Delivery Module — Documentation
- utils.js
- Truck Load Planner — Algorithm, API & Frontend Reference
- Delivery / Dispatch Module — Architecture & Bug Audit
- calculate_multi_polygon_centroid
- fuel-sync.js
- grid.py
- polling.js
- opencode.json
- preview_import
- graphify.js
- routes/__init__.py
- app/services/__init__.py
- utils/__init__.py
- profile.py
- DatabaseManager
- Changelog
- BÁO CÁO KIẾN TẬP THỰC TẾ
- ttas_client.py
- .from_dimensions
- vehicle_cost.py
- Fleet Fuel Management — AI Context
- execution_service.py
- Added
- 6. Architectural Refactoring Roadmap — 4 Pillars
- Added
- 3. Python Backend Redundancies
- Added
- Changed
- Added
- Changed
- Codebase Analysis Report — Fleet Fuel Management System
- 4. JavaScript Frontend Redundancies
- Fleet Fuel Management
- BÁO CÁO KIẾN TẬP THỰC TẾ
- Added
- renderChart
- 7. Scalability Concerns
- image_service.py
- 1.1. Tổng quan cơ sở lý thuyết
- 4.1. Mô tả chi tiết giải pháp phần mềm
- 4.2. Học hỏi từ nơi thực tập
- 2026-07-30 — Dispatch Module Post-Phase-3: Plan Auto-Completion + Live Speed Signal
- ContainerConfig
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
- 2026-07-31 — Delivery Module Phase 2: Vehicle Identity Service
- 2026-07-30 — Truck Load Planner Phase 1: Fixed Stacking Scoring Bias + Hard Height Cap
- 2026-07-30 — Truck Load Planner Phase 2: Fixed Empty-Space/Utilization Scoring
- 2026-07-30 — Truck Load Planner Phase 3: Performance (reduced scope)
- 2026-07-30 — Truck Load Planner Phase 4: Vehicle Candidate Selection to Minimize Truck Count
- AGENTS.md
- test_delivery.py
- get_eta
- TestTrackingService
- test_delivery_routes.py
- 2026-07-31 — Removed dispatcher authentication; stop reordering on the dashboard; Plans panel positioning
- TestImportVehicleResolution
- TestImageUpload
- TestVehicleIdentity
- TestExecutionLifecycle
- app/__init__.py
- TestNoModuleCreatesVehicles
- FakeFileStorage
- TestAdvanceAtomicity
- test_vehicle_core_data.py
- 9. Confirmed Bugs
- 18. Phased Refactoring Roadmap
- TestImportRoute
- TestReorderValidation
- 2026-07-31 — Core Fleet Data Is Now Read-Only to Background Processes
- 2026-07-31 — Removed the Trip Management / Trip History pages (superseded by Dispatch)
- TestOpenAccess
- 2026-07-31 — Delivery Module Phase 1: GPS Pipeline Repair + Security Hardening
- 2026-07-31 — Delivery Module Phases 4 & 5: Frontend Hardening + Route-Layer Test Suite
- 17. Future Architecture Proposal
- TestPlanCrud
- TestStopCrud
- TestLooseMatchingPreventsFalseAlarms
- 2026-07-31 — Delivery Module Phase 3: Execution Correctness (and one retracted audit finding)
- 5. Vehicle Identity Flow
- TestReorderValidation
- 2026-07-30 — Dispatch Module Phase 1: Incremental Live Updates
- 2026-07-30 — Truck Load Planner Phase 5: Regression Test Coverage (+ 2 stacking bugs it caught)
- 3. Request Flow Diagram
- 2. System Architecture Diagram
- 4. GPS Flow Diagram
- 6. Database Relationship Diagram
- 10. Likely Bugs
- 1. Executive Summary

## God Nodes (most connected - your core abstractions)
1. `LoadPlannerApp` - 133 edges
2. `DatabaseManager` - 102 edges
3. `Package` - 82 edges
4. `UI` - 76 edges
5. `Planner` - 59 edges
6. `Container` - 56 edges
7. `AABB` - 48 edges
8. `_create_plan()` - 39 edges
9. `Changelog` - 38 edges
10. `_db()` - 36 edges

## Surprising Connections (you probably didn't know these)
- `get_current_stop()` --calls--> `DatabaseManager`  [EXTRACTED]
  services/delivery/execution_service.py → app/db.py
- `get_stop_execution()` --calls--> `DatabaseManager`  [EXTRACTED]
  services/delivery/execution_service.py → app/db.py
- `delete_image()` --calls--> `DatabaseManager`  [EXTRACTED]
  services/delivery/image_service.py → app/db.py
- `UploadRejected` --uses--> `DatabaseManager`  [INFERRED]
  services/delivery/image_service.py → app/db.py
- `_NullIndex` --uses--> `DatabaseManager`  [INFERRED]
  services/delivery/plan_service.py → app/db.py

## Import Cycles
- 3-file cycle: `app.py -> app/routes/trips.py -> app/services/routing.py -> app.py`

## Communities (153 total, 16 thin omitted)

### Community 0 - "truck_load_planner/routes.py"
Cohesion: 0.14
Nodes (33): add_feature(), clear_all_packages(), create_container_config(), create_package(), create_plan(), create_shipment(), delete_container_config(), delete_feature() (+25 more)

### Community 1 - "delivery/routes.py"
Cohesion: 0.15
Nodes (36): list_images(), advance_stop(), batch_delete_plans(), cancel_stop(), clear_plans(), confirm_plan(), create_assignment(), create_driver() (+28 more)

### Community 2 - "Package"
Cohesion: 0.13
Nodes (40): _make(), Package, Placement, test_auto_arrange_uses_remaining_packages_for_rotation_choice(), test_determinism(), test_empty_placements_list(), test_generate_candidates_adds_rotation_aware_right_wall_anchor(), test_optimized_strategy_registered_and_restores_weights() (+32 more)

### Community 3 - "_create_plan"
Cohesion: 0.16
Nodes (12): _create_plan(), _create_stop(), _create_vehicle_assignment(), Tests for execution_service.py: current stop, advance, skip, cancel., Tests for execution_service.py: a plan auto-completes once every stop across…, Tests for execution_service.py: reorder_stops and insert_temp_stop., Tests for execution_service.py: progress calculation., An assignment with no stops has no stops. This test previously asserted `total… (+4 more)

### Community 4 - "planner.py"
Cohesion: 0.10
Nodes (25): Door access validation. Ensures packages can be physically inserted through a…, check_collision(), Collision detection — checks whether two packages (via their AABBs) overlap.…, Return True if two AABBs overlap (i.e., a collision exists)., Backward-compatible re-export module. The AABB class previously defined here…, Planner — single entry point for all planning operations. The UI should never…, Uniform Grid spatial index. Divides the container into fixed-size cells. Each…, PlanningState — holds all mutable state for a single loading session. Manages… (+17 more)

### Community 5 - "GoogleSheetService"
Cohesion: 0.09
Nodes (25): GoogleSheetService, parse_date_ngay(), parse_float(), parse_int(), parse_time_gio(), Any, Google Sheets Fuel Log Synchronization Service Reads fuel records from a Google…, Parse a spreadsheet date to ``YYYY-MM-DD``. Accepts ``DD/MM/YYYY`` (the… (+17 more)

### Community 6 - "delivery-plan-builder.js"
Cohesion: 0.11
Nodes (49): applyStation(), _bindDriverAutocomplete(), _bindVehicleAutocomplete(), clearAllValidation(), clearValidation(), closeMapPicker(), confirmPlan(), deleteStop() (+41 more)

### Community 7 - "Container"
Cohesion: 0.12
Nodes (21): _make_session(), End-to-end regression tests for auto-arrange. Unlike test_scorer.py's narrow…, test_distribute_across_vehicles_minimizes_truck_count_for_multi_truck_shipment(), test_distribute_across_vehicles_prefers_single_smallest_fitting_truck(), test_single_vehicle_realistic_shipment_all_placed_with_reasonable_utilization(), test_stack_depth_hard_cap_is_enforced(), test_stacking_used_when_floor_alone_is_insufficient(), check_door_access() (+13 more)

### Community 8 - "fuel.py"
Cohesion: 0.05
Nodes (64): api_fuel_log_create(), api_fuel_log_days(), api_fuel_log_delete(), api_fuel_log_export(), api_fuel_log_last_km(), api_fuel_log_list(), api_fuel_log_months(), api_fuel_log_profile_delete() (+56 more)

### Community 9 - "auto_arrange.py"
Cohesion: 0.08
Nodes (33): AutoArrangeResult, AutoArrangeStrategy, _footprint(), _largest_first_order(), LargestFirstStrategy, OptimizedStrategy, Package, Protocol (+25 more)

### Community 10 - "oil.py"
Cohesion: 0.13
Nodes (22): api_oil_fetch_progress(), api_oil_maintenance_create(), api_oil_maintenance_delete(), api_oil_maintenance_export(), api_oil_maintenance_list(), api_oil_maintenance_mark_done(), api_oil_maintenance_update(), _compute_oil_metrics() (+14 more)

### Community 11 - "js/map.js"
Cohesion: 0.10
Nodes (43): allLocationLabels, allLocationPolygons, applyFilters(), buildPopup(), buildStatusFilters(), buildTypeFilters(), cancelTripFromMap(), createIcon() (+35 more)

### Community 13 - "trips.py"
Cohesion: 0.14
Nodes (24): api_advance_trip(), api_cancel_trip(), api_refresh_routes(), do_refresh_route_data(), get_route_data(), route, Live trip routing for the main fleet map: route geometry, phase advancement,…, Cancel an active or queued trip. (+16 more)

### Community 14 - "fuel-efficiency.js"
Cohesion: 0.13
Nodes (28): allEntries, allVehicles, availableDays, changeMonth(), clearNormal(), closeModal(), deleteEntry(), editNormal() (+20 more)

### Community 15 - "vehicle-management.js"
Cohesion: 0.11
Nodes (31): allTypes, allVehicles, animate3D(), animateCamera(), attachPreviewListeners(), buildFeaturesFromForm(), destroy3DScene(), diagram (+23 more)

### Community 16 - "test_all.py"
Cohesion: 0.11
Nodes (46): EnginePackage, _build_engine_packages(), build_placement_dict(), _load_db(), _log_instrument(), _pp_placement(), _print_engine_stats(), Manual test: define packages below, run full pipeline with instrumentation.… (+38 more)

### Community 17 - "AABB"
Cohesion: 0.07
Nodes (25): AABB, Axis-Aligned Bounding Box (AABB) operations. Pure geometry — no business logic.…, An axis-aligned bounding box defined by min/max corners., Check if two AABBs overlap in 3D space., Check if this AABB fully contains another., Check if point is strictly inside (exclusive on max boundaries). A point on the…, check_constraints(), feature_to_aabb() (+17 more)

### Community 18 - "LoadPlanningSession"
Cohesion: 0.08
Nodes (19): ABC, _next_placement_uid(), Placement, PackingEngine, PackingResult, Package, ValidationFailure, get_engine() (+11 more)

### Community 19 - "adapters.py"
Cohesion: 0.14
Nodes (16): check_boundary(), Boundary validation — checks whether a package fits inside the container., calculate_total_weight(), check_weight(), Weight validation — tracks running total and checks against payload. No…, calculate_total_weight(), check_boundary(), check_weight() (+8 more)

### Community 20 - "normalize_plate"
Cohesion: 0.15
Nodes (17): normalize_gps_position(), _parse_speed_kmh(), GPS telemetry normalization for the delivery dashboard. Input contract…, Flat dict of normalized telemetry for one vehicle. New fields can be added here…, Defensively extracts a numeric km/h reading from TTAS's raw speed text — a…, normalize_plate(), License plate normalization utilities. Vietnamese plates follow the pattern…, Extract the trailing 5-digit serial from a license plate. Examples::… (+9 more)

### Community 21 - "debug_arrange.py"
Cohesion: 0.18
Nodes (19): build_real_shipment(), fmt_breakdown(), fmt_candidate_detail(), hr(), log(), main(), pl_dim(), Package (+11 more)

### Community 23 - "PlanningState"
Cohesion: 0.07
Nodes (21): Placement, 3D uniform grid for fast AABB overlap queries. Cell size is auto-tuned from…, Register a placement and its AABB in the grid., Remove a placement (linear scan — only called on user operations)., Return (placement, aabb) pairs whose cells overlap *aabb*. Returns each…, Fast check whether anything overlaps *aabb* (early exit)., Return all grid cell keys that *aabb* overlaps., UniformGrid (+13 more)

### Community 24 - "models/__init__.py"
Cohesion: 0.09
Nodes (8): _extract_doors(), Extract rear_door from features list (side doors ignored)., ContainerFeature, LoadPlan, Package, Placement, Shipment, ShipmentItem

### Community 25 - "init_db"
Cohesion: 0.21
Nodes (9): init_db(), Database initialization orchestrator. init_db() preserves app.py's original…, migrate_tlp_extensions(), TLP: container_config_id / vehicle_id columns + one-time tlp_trucks →…, create_tables(), Table definitions (CREATE TABLE IF NOT EXISTS statements). Extracted from…, init_tlp_tables(), Database initialization for Truck Load Planner tables. Called from… (+1 more)

### Community 27 - "Planner"
Cohesion: 0.08
Nodes (17): test_placement_score_to_dict(), Deprecated: kept for backward compatibility during migration., Planner, Package, setter, Score a single placement position. This is the preferred API for external…, Coordinates all subsystems for a single loading session., Score and rank candidate positions for a package. Each candidate is a dict or… (+9 more)

### Community 28 - "TestEtaService"
Cohesion: 0.13
Nodes (4): Exception, patch, Tests for eta_service.py: Haversine fallback and ORS integration., TestEtaService

### Community 29 - "main.js"
Cohesion: 0.24
Nodes (21): applyFilters(), bindFilterEvents(), bindManagePlansEvents(), bindMapControls(), clearAllPlans(), deleteSelectedPlans(), getCurrentStopId(), init() (+13 more)

### Community 30 - "timeline.js"
Cohesion: 0.21
Nodes (21): bindActionDelegation(), bindPhotosToggle(), buildActionsHtml(), buildDetailHtml(), clear(), confirmReason(), createStop(), displaySeq() (+13 more)

### Community 31 - "app.py"
Cohesion: 0.21
Nodes (19): api_clear_all_locations(), api_delete_location(), api_geocode(), api_known_locations(), api_manual_locations(), api_save_location(), api_update_location(), api_vehicles() (+11 more)

### Community 32 - "locations.js"
Cohesion: 0.29
Nodes (18): clearAllLocations(), clearMapLayers(), clearPendingCorners(), closeEditPanel(), deleteLocation(), escapeHtml(), getDistanceMeters(), handleMapClick() (+10 more)

### Community 34 - "fleet.py"
Cohesion: 0.18
Nodes (17): api_vehicle_set_container(), api_vehicle_types_create(), api_vehicle_types_delete(), api_vehicle_types_list(), api_vehicles_bulk_delete(), api_vehicles_create(), api_vehicles_delete(), api_vehicles_list() (+9 more)

### Community 35 - "with_gps"
Cohesion: 0.15
Nodes (8): C-01: `from app import fetch_vehicle_data` raised ImportError on every request,…, C-02: the normalizer read normalize_vehicle()'s *output* names off a *raw* TTAS…, C-03: matching was `.strip().lower()` on both sides., 0,0 is the Gulf of Guinea, not a vehicle position., C-02 follow-on: the handler normalized an already-normalized dict, whose keys…, TestDashboardGps, TestEtaEndpoint, with_gps()

### Community 36 - "oil-change.js"
Cohesion: 0.16
Nodes (15): allVehicles, closeModal(), deleteVehicle(), fetchKmData(), filteredVehicles, filterTable(), handleOverlayClick(), loadVehicles() (+7 more)

### Community 37 - "ApiClient"
Cohesion: 0.22
Nodes (13): populateMonthSelect(), selectVehicle(), ApiClient, addVehicleType(), bulkDelete(), closeModal(), deleteVehicle(), deleteVehicleType() (+5 more)

### Community 39 - "api.js"
Cohesion: 0.24
Nodes (15): advance(), cancel(), clearPlans(), dashboard(), deletePlans(), drivers(), eta(), fetchJSON() (+7 more)

### Community 40 - "dashboard/map.js"
Cohesion: 0.13
Nodes (17): addBasemaps(), attr(), identifyImagery(), imageryInfoHtml(), init(), parseImageryDate(), pickBestImageryResult(), readSavedBasemap() (+9 more)

### Community 41 - "migrations.py"
Cohesion: 0.27
Nodes (10): add_missing_fuel_columns(), add_missing_vehicle_trips_columns(), backfill_vehicles_from_fuel_log(), migrate_legacy_vehicle_trips_schema(), Column migrations and data backfill for existing databases. Extracted from…, Link existing fuel_log rows to the vehicles they belong to. **Link-only. This…, Rename+recreate vehicle_trips if it predates the id-primary-key schema. Must…, Run all pre-TLP migrations in original init_db() order.… (+2 more)

### Community 43 - "vehicle-list.js"
Cohesion: 0.35
Nodes (11): attentionReasonText(), _bindAttentionToggle(), computeAttention(), createCard(), _formatTime(), _patchCard(), render(), _renderAttentionStrip() (+3 more)

### Community 44 - "Delivery Module — Documentation"
Cohesion: 0.05
Nodes (39): API Endpoints, Architecture Overview, Assignments, Configuration, Dashboard Panels, Database Schema, Delivery Module — Documentation, `delivery_plan_stops` (+31 more)

### Community 45 - "utils.js"
Cohesion: 0.24
Nodes (7): calculateMultiPolygonCentroid(), calculatePolygonCentroid(), getDistanceMeters(), getLocationCentroid(), isPointInLocation(), isPointInPolygon(), showToast()

### Community 46 - "Truck Load Planner — Algorithm, API & Frontend Reference"
Cohesion: 0.06
Nodes (30): 10. Step Animation & 3D Controls, 11. Frontend: Arrange Results & Validation, 12. 2D Canvas View Coordinates, 13. Engine Architecture (`truck_load_planner/engine/`), 14. Database, 15. API: Auto-Arrange Endpoint, 1. Package Sort Order (Pre-Processing), 2. Vehicle Selection (Multi-Vehicle Distribution) (+22 more)

### Community 47 - "Delivery / Dispatch Module — Architecture & Bug Audit"
Cohesion: 0.12
Nodes (16): 11. Technical Debt, 12. Performance Bottlenecks, 13. Security Observations, 14. Duplicate Logic Inventory, 15. Highest-Risk Areas, 16. Improvement Opportunities, 19. Recommended Implementation Order, 20. Files Most Likely to Change (+8 more)

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
Cohesion: 0.57
Nodes (6): bindVisibility(), refreshNow(), runTick(), setStatus(), start(), stop()

### Community 52 - "opencode.json"
Cohesion: 0.50
Nodes (3): plugin, $schema, .opencode/plugins/graphify.js

### Community 53 - "preview_import"
Cohesion: 0.13
Nodes (15): confirm_import(), _group_rows_by_vehicle(), _NullIndex, preview_import(), ValueError, Raised when an import references vehicles that aren't in the fleet. Always…, Group import rows by the vehicle they resolve to. Grouping used to key on the…, Dry-run summary shown before the dispatcher commits an import. When ``db_path``… (+7 more)

### Community 59 - "DatabaseManager"
Cohesion: 0.12
Nodes (26): DatabaseManager, Centralized SQLite connection management. Replaces the duplicated…, Encapsulates SQLite connections for a single database file. Each `connect()`…, bulk_create_stops(), clear_plans(), create_assignment(), create_driver(), create_plan() (+18 more)

### Community 60 - "Changelog"
Cohesion: 0.10
Nodes (20): 2026-07-11 — Refinements, 2026-07-13 — Container Fuel, Anomaly Detection, Vehicle Management, 2026-07-18 — Door Rendering Fixes, 2026-07-18 — Gravity, Stacking & Engine Refinement, 2026-07-18 — Inline Package Editor & Canvas UX, 2026-07-18 — Phase 3: Placement Evaluation Engine, 2026-07-18 — Phase 4: Auto Arrange Engine (v1), 2026-07-30 — Dispatch Module Phase 0: Bug Fixes (+12 more)

### Community 69 - "BÁO CÁO KIẾN TẬP THỰC TẾ"
Cohesion: 0.10
Nodes (20): 1.1. Tổng quan cơ sở lý thuyết, 1.2. Chủ đề thực tập, 1.3. Các kết quả và mục tiêu kỳ vọng, 2.1. Thông tin cơ quan, 2.2. Lịch sử hình thành và phát triển, 2.3. Cơ cấu tổ chức, nhiệm vụ chức năng của các phòng ban, 2.4. Chức năng, nhiệm vụ, phạm vi ngành nghề hoạt động, 2.5. Quy mô nhân sự và năng lực dịch vụ (+12 more)

### Community 70 - "ttas_client.py"
Cohesion: 0.16
Nodes (19): api_oil_maintenance_fetch_km(), Upsert parsed KM entries into oil_km_log using INSERT OR REPLACE. Each entry is…, Scrape the TTAS report for all vehicles from their last oil change date to…, _store_km_log(), ensure_session(), fetch_live_vehicle_data(), _fetch_ttas_report_page(), fetch_vehicle_data() (+11 more)

### Community 71 - ".from_dimensions"
Cohesion: 0.14
Nodes (15): Enum, StackingMode, _check_stacking_rules(), check_support(), _count_above(), _footprint_centre(), Package, Placement (+7 more)

### Community 72 - "vehicle_cost.py"
Cohesion: 0.18
Nodes (12): compute_fleet_cost(), compute_vehicle_floor_mm2(), compute_vehicle_volume_mm3(), _get_fuel_consumption(), Vehicle Cost Model — computes estimated transportation cost for a vehicle. Kept…, Quick pre-packing feasibility check. Returns (is_feasible, reason) where reason…, Compute actual transportation cost for a vehicle after packing. Uses actual…, Compute total transportation cost for a fleet solution. Sums the post-packing… (+4 more)

### Community 73 - "Fleet Fuel Management — AI Context"
Cohesion: 0.12
Nodes (16): AI Working Workflow, Architecture, Architecture Decision Rules, Coding Standards, Dashboard map conventions (learned the hard way, 2026-07-31), Decision Making, Definition of Done, Directory Structure (+8 more)

### Community 74 - "execution_service.py"
Cohesion: 0.16
Nodes (18): advance_stop(), cancel_stop(), get_assignment_progress(), get_current_stop(), get_dashboard_data(), _get_plan_id_for_stop(), get_stop_execution(), insert_temp_stop() (+10 more)

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

### Community 80 - "Changed"
Cohesion: 0.10
Nodes (21): 2026-07-26 — Phase 1: Delivery Plan Management Rewrite, Added, Changed, Changed, Consolidated Test Files, Fixed, Migration Script (`scripts/migrate_to_delivery.py`), New Database Schema (6 tables, coexists with legacy `vehicle_trips`) (+13 more)

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
Cohesion: 0.18
Nodes (10): Delivery Management Tests (187 tests), Fleet Fuel Management, Pages, Project Structure, Running Tests, Tech Stack, Third-party hosts the browser must reach, TLP Benchmarks, Diagnostics & Manual Debugging (non-pytest) (+2 more)

### Community 86 - "BÁO CÁO KIẾN TẬP THỰC TẾ"
Cohesion: 0.22
Nodes (8): 3.1. Quy trình điều vận xe tải thùng kín và Container thực tế, 3.2. Nhận diện nút thắt (Bottlenecks), 3.3. Phân tích chất lượng dữ liệu hiện tại, BÁO CÁO KIẾN TẬP THỰC TẾ, CHƯƠNG 3: BÀI TOÁN THỰC TẾ VÀ KHẢO SÁT NGHIỆP VỤ LOGISTICS CHI TIẾT, Lý do chọn đề tài, MỞ ĐẦU, Mục đích kiến tập

### Community 87 - "Added"
Cohesion: 0.22
Nodes (9): 2026-07-22 — Frontier-Based Gap Prevention, Gap-Filling Pass, Debug Instrumentation, Added, Detailed Debug Instrumentation (`engine/auto_arrange.py`), Duplicate-Name Bug in Gap-Filling Pass, Fixed, Frontier Gap-Filling Pass (`fill_frontier_gaps` in `engine/distribution.py`), FrontierTracker (`engine/frontier.py`), Removed (+1 more)

### Community 88 - "renderChart"
Cohesion: 0.20
Nodes (17): applyFilters(), changeDay(), filterTable(), hideAnomalyTooltip(), hideSearchDropdown(), loadVehicles(), onDayChange(), onFilterChange() (+9 more)

### Community 89 - "7. Scalability Concerns"
Cohesion: 0.22
Nodes (9): 7.1 No Connection Pooling, 7.2 Global Mutable State, 7.3 No Dependency Injection, 7.4 12-Second Polling (No WebSockets/SSE), 7.5 Monolithic CSS, 7.6 No Build Step, 7.7 `app.py` Bare `except:` Blocks, 7.8 Hardcoded Values That Should Be Configurable (+1 more)

### Community 90 - "image_service.py"
Cohesion: 0.24
Nodes (11): delete_image(), ensure_folder(), get_image(), ValueError, Raised when an upload fails validation. Carries a user-safe message., Reduce a user-supplied string to one safe filesystem path component.…, Check extension and size. Returns the normalized extension., _safe_path_segment() (+3 more)

### Community 91 - "1.1. Tổng quan cơ sở lý thuyết"
Cohesion: 0.25
Nodes (8): 1.1.1. Bài toán Tối ưu hóa lộ trình (Vehicle Routing Problem — VRP), 1.1.2. Thuật toán hình học không gian áp dụng trong Định vị (Geofencing), 1.1.3. Học máy thống kê áp dụng trong Phát hiện bất thường (Anomaly Detection), 1.1.4. Kỹ nghệ dữ liệu (Data Engineering) và Tự động hóa thu thập, 1.1. Tổng quan cơ sở lý thuyết, 1.2. Chủ đề thực tập, 1.3. Các kết quả và mục tiêu kỳ vọng, CHƯƠNG 1: GIỚI THIỆU TỔNG QUAN VỀ CƠ SỞ LÝ THUYẾT VÀ CHỦ ĐỀ KIẾN TẬP

### Community 92 - "4.1. Mô tả chi tiết giải pháp phần mềm"
Cohesion: 0.25
Nodes (8): 4.1.1. Xác thực và đồng bộ dữ liệu với TTAS, 4.1.2. Cơ chế Geofencing và tự động chuyển phase, 4.1.3. Tích hợp định tuyến với OpenRouteService, 4.1.4. Mô hình phát hiện bất thường nhiên liệu, 4.1.5. Pipeline bảo dưỡng tự động, 4.1.6. Giao diện và kết quả tổng thể, 4.1.7. Tối ưu hiệu năng và hạn chế kỹ thuật, 4.1. Mô tả chi tiết giải pháp phần mềm

### Community 93 - "4.2. Học hỏi từ nơi thực tập"
Cohesion: 0.25
Nodes (8): 4.2.1. Nhận thức về khoảng cách giữa lý thuyết và thực tế, 4.2.2. Kỹ năng chuyên môn, 4.2.3. Tác phong công nghiệp và văn hóa doanh nghiệp, 4.2. Học hỏi từ nơi thực tập, 4.3.1. Tương quan giữa giảng đường và doanh nghiệp, 4.3.2. Khoảng cách lý thuyết và thực tiễn, 4.3. Đánh giá mối liên hệ giữa lý thuyết và thực tiễn, CHƯƠNG 4: KẾT QUẢ THỰC TẾ - XÂY DỰNG HỆ THỐNG PHẦN MỀM THÔNG MINH "FLEET FUEL MANAGEMENT"

### Community 94 - "2026-07-30 — Dispatch Module Post-Phase-3: Plan Auto-Completion + Live Speed Signal"
Cohesion: 0.50
Nodes (4): 2026-07-30 — Dispatch Module Post-Phase-3: Plan Auto-Completion + Live Speed Signal, Added, Deferred (explicit decision, not forgotten), Testing

### Community 95 - "ContainerConfig"
Cohesion: 0.15
Nodes (11): ContainerConfig, auto_arrange(), _build_placement_dict(), _distribute_across_vehicles(), _get_packages_from_request(), _load_vehicle_session(), Convert an engine Placement to a frontend-compatible dict., Extract expanded EnginePackage list from shipment_id or inline packages. (+3 more)

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

### Community 108 - "2026-07-31 — Delivery Module Phase 2: Vehicle Identity Service"
Cohesion: 0.29
Nodes (7): 2026-07-31 — Delivery Module Phase 2: Vehicle Identity Service, Added, Changed, Fixed, Notes, Still open: other paths that auto-create vehicles, Testing

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

### Community 115 - "test_delivery.py"
Cohesion: 0.12
Nodes (10): db_path(), isolated_upload_root(), fixture, audit C-09 — `total = sum(...) or 1` leaked a division guard into the reported…, Keep uploaded test images out of the repository. image_service derives…, Create a fresh SQLite database with all delivery + vehicles tables., Verify multi-table operations roll back on failure., TestPreviewImportResolution (+2 more)

### Community 116 - "get_eta"
Cohesion: 0.19
Nodes (15): calculate_eta(), calculate_etas_for_stops(), calculate_travelled_distance_km(), _compute_etas_for_stops(), get_distance_meters(), Same computation as _compute_etas_for_stops, with an optional in-memory cache…, Approximate straight-line distance already covered on this assignment: sums…, _stops_cache_key() (+7 more)

### Community 117 - "TestTrackingService"
Cohesion: 0.22
Nodes (4): A raw TTAS DevList item — the actual input contract of…, Tests for tracking_service.py. These previously fed hand-written dicts keyed on…, _raw_ttas(), TestTrackingService

### Community 118 - "test_delivery_routes.py"
Cohesion: 0.18
Nodes (11): init_delivery_tables(), app(), client(), db(), isolated_upload_root(), fixture, Route-layer tests for the delivery/dispatch HTTP API. Why this file exists…, HTTP client. Every endpoint is open — the dispatcher password was removed… (+3 more)

### Community 119 - "2026-07-31 — Removed dispatcher authentication; stop reordering on the dashboard; Plans panel positioning"
Cohesion: 0.14
Nodes (14): 2026-07-31 — Removed dispatcher authentication; stop reordering on the dashboard; Plans panel positioning, Added — click the satellite map for the imagery capture date, Added — clicking a stop locates it on the map, Added — reorder stops from the dashboard, Added — switchable basemap, satellite by default, Fixed — clicking a vehicle took ~15 seconds to update the right panel, Fixed — map control buttons became unreadable on hover, Fixed — the map snapped back to the selected vehicle on every poll (+6 more)

### Community 120 - "TestImportVehicleResolution"
Cohesion: 0.24
Nodes (7): _add_vehicle(), _count_vehicles(), confirm_import must resolve plate variants onto existing rows instead of…, There is no override. An unknown plate always aborts, and no keyword argument…, Variants of the same unknown plate collapse to one entry, so the dispatcher…, Used to return success while the plan silently stayed 'draft' and never reached…, TestImportVehicleResolution

### Community 121 - "TestImageUpload"
Cohesion: 0.22
Nodes (6): parametrize, S-05: send_file infers Content-Type from the extension, so an uploaded .html…, S-04: category and station_code were interpolated into the upload path, so…, C-08: filenames were `{unix_seconds}{ext}`, so the second photo silently…, TestImageUpload, _upload()

### Community 122 - "TestVehicleIdentity"
Cohesion: 0.18
Nodes (6): parametrize, services/vehicle_identity.py — the resolver that replaces five mutually…, The exact duplicate shape merge_duplicate_vehicles.py cleans up: a stray…, Two different full plates sharing a 5-digit serial must not be silently…, Adding a vehicle is a Vehicle Management action. This module must never grow a…, TestVehicleIdentity

### Community 123 - "TestExecutionLifecycle"
Cohesion: 0.17
Nodes (3): C-07: two taps took a stop planned -> arrived -> completed, marking it…, C-09: `total = sum(...) or 1` made an empty assignment claim it had one…, TestExecutionLifecycle

### Community 124 - "app/__init__.py"
Cohesion: 0.22
Nodes (7): Application configuration — environment variable reads and constants. Extracted…, create_app(), Flask app factory (Section 6.4.1, Phase 1). app.py (the project's entry point,…, load_known_locations(), create_fleet_session(), Shared mutable runtime state. Not one of the report's named modules — added…, WSGI entry point for production servers (Gunicorn, etc.). Needed because…

### Community 125 - "TestNoModuleCreatesVehicles"
Cohesion: 0.24
Nodes (7): Path, Static guarantee, so a future edit can't quietly reintroduce this., plate_number / vehicle_type / current_driver identify a vehicle and describe…, container_config_id (the vehicle's dimensions) is written in exactly one place:…, Every `UPDATE vehicles SET ...` statement in a module, up to its WHERE or the…, TestNoModuleCreatesVehicles, _update_vehicles_statements()

### Community 126 - "FakeFileStorage"
Cohesion: 0.24
Nodes (4): FakeFileStorage, Mimics Werkzeug's FileStorage for testing. Now exposes ``.stream`` because that…, Tests for image_service.py: upload, list, get, delete., TestImageService

### Community 127 - "TestAdvanceAtomicity"
Cohesion: 0.27
Nodes (5): A stop must not be walked two steps by one accidental double-tap (audit C-07).…, The damage wasn't only the status — arrival and departure were stamped in the…, The guard must not break the normal flow: a dispatcher advancing twice, each…, expected_status is optional — older callers keep working., TestAdvanceAtomicity

### Community 128 - "test_vehicle_core_data.py"
Cohesion: 0.22
Nodes (8): core_data(), fleet_db(), fixture, Core fleet data is never created or altered in the background. `vehicles` —…, app/database/migrations.py runs on every startup., A database with one registered vehicle, fully specified., Everything this project considers core vehicle data., TestBootMigrationNeverWritesCoreData

### Community 129 - "9. Confirmed Bugs"
Cohesion: 0.20
Nodes (10): 9. Confirmed Bugs, C-01 · GPS pipeline dead — wrong import module, C-02 · `normalize_gps_position` consumes the wrong dict schema, C-03 · Plate matching uses `.lower()` against a field that is always absent, C-04 · No authentication on any delivery endpoint, C-05 · Excel import creates duplicate vehicle rows, ~~C-06 · Stop reordering never updates the UI~~ — **RETRACTED 2026-07-31**, C-07 · Double-click on "Advance" skips the "arrived" state (+2 more)

### Community 130 - "18. Phased Refactoring Roadmap"
Cohesion: 0.22
Nodes (9): 18. Phased Refactoring Roadmap, Phase 0 — Verify deployment reality (½ day), Phase 1 — Stop the bleeding (2-3 days), Phase 2 — Vehicle Identity Service (3-4 days), Phase 3 — GPS Adapter + Sync Layer (4-5 days), Phase 4 — Execution correctness (2-3 days), Phase 5 — Frontend hardening & performance (2-3 days), Phase 6 — Debt & documentation (2 days) (+1 more)

### Community 133 - "2026-07-31 — Core Fleet Data Is Now Read-Only to Background Processes"
Cohesion: 0.29
Nodes (7): 2026-07-31 — Core Fleet Data Is Now Read-Only to Background Processes, Added, Changed — unknown vehicle now prompts instead of failing, Fixed, Note, Reviewed and left alone, Testing

### Community 134 - "2026-07-31 — Removed the Trip Management / Trip History pages (superseded by Dispatch)"
Cohesion: 0.29
Nodes (7): 2026-07-31 — Removed the Trip Management / Trip History pages (superseded by Dispatch), Consequence worth knowing, Documentation, Kept, deliberately, Not touched, Removed, Testing

### Community 135 - "TestOpenAccess"
Cohesion: 0.29
Nodes (3): A 401 or 503 here means a gate came back. Anything else — 200, 400 for a bad…, The most destructive endpoint: cascade-deletes everything. It is deliberately…, TestOpenAccess

### Community 136 - "2026-07-31 — Delivery Module Phase 1: GPS Pipeline Repair + Security Hardening"
Cohesion: 0.33
Nodes (6): 2026-07-31 — Delivery Module Phase 1: GPS Pipeline Repair + Security Hardening, Added, Deployment note, Fixed, Known limitations / deliberately not fixed here, Testing

### Community 137 - "2026-07-31 — Delivery Module Phases 4 & 5: Frontend Hardening + Route-Layer Test Suite"
Cohesion: 0.33
Nodes (6): 2026-07-31 — Delivery Module Phases 4 & 5: Frontend Hardening + Route-Layer Test Suite, Added — route-layer test suite (T-01), Fixed — frontend, Fixed — test isolation, Still open (not in scope for these phases), Testing

### Community 138 - "17. Future Architecture Proposal"
Cohesion: 0.33
Nodes (6): 17.1 Vehicle Identity Service — `services/vehicle_identity.py`, 17.2 GPS Adapter — `services/gps/`, 17.3 Synchronization Layer — background GPS refresher, 17.4 Shared Vehicle Resolver (frontend), 17.5 Truck Load Planner ↔ Delivery Execution integration, 17. Future Architecture Proposal

### Community 141 - "TestLooseMatchingPreventsFalseAlarms"
Cohesion: 0.40
Nodes (3): parametrize, The unknown-vehicle prompt must only fire for genuinely new trucks — never…, TestLooseMatchingPreventsFalseAlarms

### Community 142 - "2026-07-31 — Delivery Module Phase 3: Execution Correctness (and one retracted audit finding)"
Cohesion: 0.40
Nodes (5): 2026-07-31 — Delivery Module Phase 3: Execution Correctness (and one retracted audit finding), Already done, Fixed, Retracted — audit findings C-06 and F-01 were wrong, Testing

### Community 143 - "5. Vehicle Identity Flow"
Cohesion: 0.40
Nodes (5): 5. Vehicle Identity Flow, Authoritative identifier — determination, Complete identity call-site inventory, Documented mismatch scenarios, Evidence this is not hypothetical

### Community 145 - "2026-07-30 — Dispatch Module Phase 1: Incremental Live Updates"
Cohesion: 0.50
Nodes (4): 2026-07-30 — Dispatch Module Phase 1: Incremental Live Updates, Fixed, Out of Scope, Remaining Technical Debt / Deferred

### Community 146 - "2026-07-30 — Truck Load Planner Phase 5: Regression Test Coverage (+ 2 stacking bugs it caught)"
Cohesion: 0.50
Nodes (4): 2026-07-30 — Truck Load Planner Phase 5: Regression Test Coverage (+ 2 stacking bugs it caught), Added, Fixed (found while writing these tests, not part of the original plan), Testing

### Community 147 - "3. Request Flow Diagram"
Cohesion: 0.50
Nodes (4): 3.1 Dashboard open → first paint, 3.2 Select a vehicle → complete a stop, 3. Request Flow Diagram, Cache inventory

### Community 148 - "2. System Architecture Diagram"
Cohesion: 0.67
Nodes (3): 2. System Architecture Diagram, Architectural observations, Component responsibilities

### Community 149 - "4. GPS Flow Diagram"
Cohesion: 0.67
Nodes (3): 4. GPS Flow Diagram, Additional GPS-path defects, The four-layer failure, in order

### Community 150 - "6. Database Relationship Diagram"
Cohesion: 0.67
Nodes (3): 6. Database Relationship Diagram, Data flow through the tables, Schema findings

## Knowledge Gaps
- **440 isolated node(s):** `$schema`, `.opencode/plugins/graphify.js`, `allEntries`, `filteredEntries`, `allVehicles` (+435 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DatabaseManager` connect `DatabaseManager` to `test_vehicle_core_data.py`, `delivery/routes.py`, `truck_load_planner/routes.py`, `_create_plan`, `TestReorderValidation`, `TestVehicleIdentity`, `execution_service.py`, `TestLooseMatchingPreventsFalseAlarms`, `test_delivery.py`, `preview_import`, `TestTrackingService`, `ContainerConfig`, `TestImportVehicleResolution`, `image_service.py`, `TestEtaService`, `TestNoModuleCreatesVehicles`, `FakeFileStorage`, `TestAdvanceAtomicity`?**
  _High betweenness centrality (0.127) - this node is a cross-community bridge._
- **Why does `Package` connect `Package` to `truck_load_planner/routes.py`, `planner.py`, `GoogleSheetService`, `Container`, `.from_dimensions`, `auto_arrange.py`, `test_all.py`, `LoadPlanningSession`, `debug_arrange.py`, `PlanningState`, `Planner`?**
  _High betweenness centrality (0.085) - this node is a cross-community bridge._
- **Why does `LoadPlanningSession` connect `LoadPlanningSession` to `truck_load_planner/routes.py`, `Package`, `planner.py`, `Container`, `auto_arrange.py`, `test_all.py`, `AABB`, `Planner`, `ContainerConfig`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `DatabaseManager` (e.g. with `UploadRejected` and `_NullIndex`) actually correct?**
  _`DatabaseManager` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 21 inferred relationships involving `Package` (e.g. with `AutoArrangeResult` and `AutoArrangeStrategy`) actually correct?**
  _`Package` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `Planner` (e.g. with `AutoArrangeResult` and `StrategyRegistry`) actually correct?**
  _`Planner` has 10 INFERRED edges - model-reasoned connections that need verification._
- **What connects `$schema`, `.opencode/plugins/graphify.js`, `allEntries` to the rest of the system?**
  _440 weakly-connected nodes found - possible documentation gaps or missing edges._