# Changelog

## 2026-07-13 — Container Fuel, Partial Tank, Search & UI Overhaul

### Added

- **Container Fuel page** (`/fuel-container`) — separate dashboard for container vehicles
  - Full Tank ✅ checkbox in modal (hidden on regular page)
  - Partial fills excluded from efficiency/chart; accumulated efficiency computed at next full tank
  - Table shows Full/Partial Tank column
- **Accumulated efficiency** for container vehicles
  - When `is_full_tank=1`, `l_per_100km` = total liters ÷ total distance since last full tank
  - Individual `distance_km`/`liters` preserved per-entry (no double-counting in KPIs)
  - Baseline computation filters to full-tank entries only (falls back to all entries)
- **Adjustable anomaly multiplier** per vehicle
  - Default: 1.50× for container, 1.20× for regular
  - Editable in Vehicle Baselines table alongside normal L/100km
- **All time month filter** — "All time" option in month selector (default), shows entire history
- **Combined search bar** — single input handles both table text search and vehicle selection
  - Click to show all available vehicles; type to filter; "No vehicle found" message on mismatch
  - Container page shows only container vehicles; regular page shows only regular vehicles
- **Issue filter** — dropdown to show only flagged entries (spikes, no-KM, partial fills)
- **Chart data labels** — numeric L/100km value displayed above each chart point
- **Fleet navigation dropdown** — secondary pages (Oil Change, Vehicles, Fuel, Container) grouped under "Fleet ▾" on all pages
- **Sticky table headers** — column titles stay visible when scrolling long tables
- **Styled scrollbar** — thin, semi-transparent scrollbar for refuel log table

### Changed

- **`fuel_log` table** — added `is_full_tank INTEGER NOT NULL DEFAULT 1`
- **`fuel_vehicle_profile` table** — added `anomaly_multiplier REAL DEFAULT NULL`
- **`_compute_fuel_entry()`** — skips efficiency for partial fills; computes accumulated efficiency for full fills
- **`_apply_anomaly_flag()`** — uses per-vehicle multiplier instead of hardcoded 1.20
- **`GET /api/fuel-log/months`** — accepts `?mode=` to filter months by vehicle type
- **`GET /api/fuel-log/days`** — accepts `?mode=` to filter days by vehicle type
- **`GET /api/fuel-log/profiles`** — returns `anomaly_multiplier` per vehicle
- **`PUT /api/fuel-log/profiles/:plate`** — accepts `anomaly_multiplier` in addition to `normal_l_per_100km`
- **CSV export** — added Full Tank, Accum Distance KM, Accum Liters columns
- **Navigation** — consolidated into Fleet dropdown on all pages (index, oil-change, trip-history, locations, manage-trips, fuel-efficiency, vehicle-management)
- **Month selector** defaults to "All time" instead of current month

### Fixed

- **Vehicle Baselines** table now filters by mode (container/regular)
- **Day/month selectors** now respect mode filter when querying available days/months
- **Chart no longer dips to 0** from partial-fill entries (explicitly excluded via `l_per_100km > 0` filter)
- **Dropdown toggle** uses direct `style.display` swap instead of `classList.toggle` (which didn't work with inline styles)

## 2026-07-11 — Fuel Efficiency, Refuel Log & Vehicle Management

### Added

- **Fuel Efficiency Dashboard** (`/fuel-efficiency`)
  - Monthly filter with prev/next navigation (defaults to current month)
  - KPI cards: Total Distance (km), Total Fuel (L), Average Efficiency (km/L)
  - Time-series chart (Chart.js) plotting km/L over time with anomaly highlighting
  - Click anomaly points on chart to inspect details (date, distance, fuel, baseline, driver, store)
  - Vehicle selector for chart: search by plate, add/remove chips to filter displayed vehicles
  - Simplified controls — single search bar only (redundant dropdown removed)
  - Sortable refuel log table with anomaly row highlighting

- **Refuel Log CRUD** (`/api/fuel-log`)
  - Create/edit/delete refuel entries with validation (new_km >= old_km, liters > 0)
  - Warnings when distance > 2000 km or < 1 km
  - Vehicle autocomplete in the entry form — type to search, auto-fills vehicle type and driver
  - Monthly stats and filtering via `?month=YYYY-MM` parameter

- **Anomaly Detection**
  - Baseline: 5-entry moving average of L/100km per vehicle (or user-defined normal)
  - Anomaly flagged when actual L/100km exceeds baseline &times; 1.20
  - Visual indicators on chart (red markers, larger points) and table (amber row background)

- **Vehicle Management** (`/vehicle-management`)
  - Master list of all fleet vehicles (`vehicles` table)
  - Full CRUD: add, edit, delete vehicles with plate number, vehicle type, driver
  - Vehicle type presets: 1 Ton, 1.5 Tons, 2 Tons, 3.5 Tons, 5 Tons, 8 Tons, Tractor Head, Container Truck
  - KPI cards: total vehicles, unique types, assigned drivers

- **Vehicle Baselines** (per-vehicle normal L/100km)
  - Set/edit expected normal consumption per vehicle
  - Inline editing in the dashboard — click Edit, enter value, Save
  - Anomaly detection uses manual normal if set, falls back to computed moving average

- **Navigation links** updated on all pages (index, oil-change, fuel-efficiency) to cross-link between Map, Vehicles, Fuel Efficiency, Oil Change

### Changed

- **`fuel_log` table** — added `vehicle_id` column (FK to `vehicles`), auto-backfilled from existing `license_plate` data
- **`GET /api/fuel-log`** — now supports `month`, `vehicle_ids`, and `license_plate` query parameters
- **`GET /api/fuel-log/summary`** — supports `?month=` parameter for scoped summaries
- **`GET /api/fuel-log/export`** — supports `?month=` parameter for scoped CSV export
- **`POST /api/fuel-log`** — accepts `vehicle_id`; auto-fills plate/driver from `vehicles` table; auto-creates vehicle record if new plate

### Database

- **New table: `vehicles`**
  ```sql
  vehicles (id, plate_number UNIQUE, vehicle_type, current_driver, created_at, updated_at)
  ```
- **New table: `fuel_vehicle_profile`**
  ```sql
  fuel_vehicle_profile (license_plate PK, normal_l_per_100km, updated_at)
  ```
- **Modified: `fuel_log`** — added `vehicle_id INTEGER DEFAULT NULL`

### Notes

- Existing trip-tracking state machine and oil-change logic are untouched
- Designed for future extensibility (manufacturer, model, fuel type, tank capacity, insurance, etc. can be added to `vehicles` table)

## 2026-07-11 — Refinements & Bug Fixes

### Changed

- **Unit:** All fuel efficiency now uses **L/100km** consistently (was km/L). Updated backend stats, chart, table, tooltips, CSV export.
- **Average calculation:** Switched from weighted average to **simple average** of per-entry L/100km values to match user expectations.
- **Chart vehicle selector:** Replaced chip-based multi-select with a single **combobox** (click to select from list or type to search).
- **KPIs now respond to vehicle filter:** Total Distance, Total Fuel, Average Efficiency, and Total Spend update when a specific vehicle is selected in the chart filter.
- **Month selector:** Dynamically populated from actual months with data (`/api/fuel-log/months`) instead of predefined range.
- **CSV export:** License plate prefixed with tab character to prevent Excel from stripping leading zeros.
- **All L/100km values** display with 2 decimal places throughout.
- **KM fields optional:** Old KM and New KM can be empty. Entries without KM are stored but excluded from efficiency/chart/stats.
- **Baseline calculation** in summary endpoint fixed to use proper L/100km average per vehicle.

### Added

- **Day selector** next to month selector (arrows + dropdown). Shows only days with entries. Filters table, chart, and KPIs.
- **Total Spend KPI card** (4th card) showing sum of `unit_price × liters` for the filtered scope.
- **No-KM row highlighting:** Table rows without KM data get amber left border + tint + `⚠ No KM` badge.
- **Anomaly/No-KM counts** shown in the fuel KPI subtext (e.g. "2 spike, 3 no KM").
- **Backend endpoint:** `GET /api/fuel-log/days?month=YYYY-MM` returns distinct days with entries.
- **Backend endpoint:** `GET /api/fuel-log/months` returns distinct months with entries.

### Fixed

- **Anomaly tooltip:** `entry.liters` now properly formatted with 1 decimal place.
- **Profile loading:** `loadProfiles()` was never called on initial page load — now called during `DOMContentLoaded` and after `loadDashboard()`.
- **Stats endpoint:** Now only sums valid entries (distance > 0, liters > 0) — was including zero-distance entries and skewing averages.
- **Day selector race condition:** `populateMonthSelect()` is now awaited before `onMonthChange()` runs, ensuring the month dropdown is populated before the day dropdown tries to read it.

### Added

- **Fuel Efficiency Dashboard** (`/fuel-efficiency`)
  - Monthly filter with prev/next navigation (defaults to current month)
  - KPI cards: Total Distance (km), Total Fuel (L), Average Efficiency (km/L)
  - Time-series chart (Chart.js) plotting km/L over time with anomaly highlighting
  - Click anomaly points on chart to inspect details (date, distance, fuel, baseline, driver, store)
  - Vehicle selector for chart: search by plate, add/remove chips to filter displayed vehicles
  - Simplified controls — single search bar only (redundant dropdown removed)
  - Sortable refuel log table with anomaly row highlighting

- **Refuel Log CRUD** (`/api/fuel-log`)
  - Create/edit/delete refuel entries with validation (new_km >= old_km, liters > 0)
  - Warnings when distance > 2000 km or < 1 km
  - Vehicle autocomplete in the entry form — type to search, auto-fills vehicle type and driver
  - Monthly stats and filtering via `?month=YYYY-MM` parameter

- **Anomaly Detection**
  - Baseline: 5-entry moving average of L/100km per vehicle (or user-defined normal)
  - Anomaly flagged when actual L/100km exceeds baseline &times; 1.20
  - Visual indicators on chart (red markers, larger points) and table (amber row background)

- **Vehicle Management** (`/vehicle-management`)
  - Master list of all fleet vehicles (`vehicles` table)
  - Full CRUD: add, edit, delete vehicles with plate number, vehicle type, driver
  - Vehicle type presets: 1 Ton, 1.5 Tons, 2 Tons, 3.5 Tons, 5 Tons, 8 Tons, Tractor Head, Container Truck
  - KPI cards: total vehicles, unique types, assigned drivers

- **Vehicle Baselines** (per-vehicle normal L/100km)
  - Set/edit expected normal consumption per vehicle
  - Inline editing in the dashboard — click Edit, enter value, Save
  - Anomaly detection uses manual normal if set, falls back to computed moving average

- **Navigation links** updated on all pages (index, oil-change, fuel-efficiency) to cross-link between Map, Vehicles, Fuel Efficiency, Oil Change

### Changed

- **`fuel_log` table** — added `vehicle_id` column (FK to `vehicles`), auto-backfilled from existing `license_plate` data
- **`GET /api/fuel-log`** — now supports `month`, `vehicle_ids`, and `license_plate` query parameters
- **`GET /api/fuel-log/summary`** — supports `?month=` parameter for scoped summaries
- **`GET /api/fuel-log/export`** — supports `?month=` parameter for scoped CSV export
- **`POST /api/fuel-log`** — accepts `vehicle_id`; auto-fills plate/driver from `vehicles` table; auto-creates vehicle record if new plate

### Database

- **New table: `vehicles`**
  ```sql
  vehicles (id, plate_number UNIQUE, vehicle_type, current_driver, created_at, updated_at)
  ```
- **New table: `fuel_vehicle_profile`**
  ```sql
  fuel_vehicle_profile (license_plate PK, normal_l_per_100km, updated_at)
  ```
- **Modified: `fuel_log`** — added `vehicle_id INTEGER DEFAULT NULL`

### Notes

- Existing trip-tracking state machine and oil-change logic are untouched
- Designed for future extensibility (manufacturer, model, fuel type, tank capacity, insurance, etc. can be added to `vehicles` table)
