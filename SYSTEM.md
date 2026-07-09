# Fleet Management System — Comprehensive Documentation

## Table of Contents
1. [System Overview](#1-system-overview)
2. [Project Structure](#2-project-structure)
3. [Architecture](#3-architecture)
4. [Database Schema](#4-database-schema)
5. [API Reference](#5-api-reference)
6. [Trip Lifecycle & State Machine](#6-trip-lifecycle--state-machine)
7. [Geofencing System](#7-geofencing-system)
8. [Routing System (ORS Integration)](#8-routing-system-ors-integration)
9. [TTAS Integration](#9-ttas-integration)
10. [Oil Change Maintenance](#10-oil-change-maintenance)
11. [Frontend Overview](#11-frontend-overview)
12. [Configuration Reference](#12-configuration-reference)
13. [Development Guide](#13-development-guide)

---

## 1. System Overview

A real-time fleet vehicle tracking and trip management web application. The system integrates with **TTAS** (a Vietnamese GPS tracking platform) to display live vehicle positions, manage trips with geofence-based auto-progression, compute optimal routes via **OpenRouteService (ORS)**, and track vehicle oil change maintenance intervals.

### Key Capabilities
- **Real-time vehicle tracking** on a Leaflet map with live TTAS data
- **Trip management** with queuing, phase progression (pickup → waypoints → destination), and geofence auto-arrival detection
- **Multi-stop trips** via waypoints (arbitrary number of intermediate stops)
- **Route calculation** using ORS Directions API with HGV profile, falling back to great-circle distance
- **Geofence-based auto-progression** — vehicle advances through trip phases automatically when GPS enters a zone
- **Force override** — dispatchers can manually advance, complete, or cancel trips from the dashboard
- **Geofence event logging** — timestamped log of all zone arrivals
- **Oil change maintenance tracker** — scrapes TTAS reports to compute KM since last change with safe/warning/danger indicators
- **Dark-themed UI** with filtering by vehicle type, status, location, and route presence

---

## 2. Project Structure

```
D:\ChiTuyen\Solution\
├── .env                              # Environment variables (secrets)
├── .gitignore
├── app.py                            # Flask backend (~2184 lines)
├── main.py                           # TTAS Playwright login/report scraper (~171 lines)
├── requirements.txt                  # Python dependencies
├── manual_locations.json             # Saved geofence zones
├── log.json                          # Cached TTAS vehicle snapshot (fallback data)
├── routing_system.db                 # SQLite database (auto-created)
├── data/                             # Reserved (empty)
├── SYSTEM.md                         # This documentation
│
├── static/
│   ├── css/
│   │   └── style.css                 # Dark-theme design system (~1189 lines)
│   └── js/
│       ├── utils.js                  # Shared geo utilities (~231 lines)
│       ├── map.js                    # Main dashboard map controller (~1228 lines)
│       ├── manage-trips.js           # Trip creation & management (~1150 lines)
│       ├── locations.js              # Geofence zone editor (~599 lines)
│       ├── trip-history.js           # Trip history viewer (~195 lines)
│       └── oil-change.js             # Oil change dashboard (~500 lines)
│
└── templates/
    ├── index.html                    # Main dashboard (map + sidebar + filters)
    ├── manage-trips.html             # Trip creation form + active trips table
    ├── locations.html                # Geofence zone editor page
    ├── trip-history.html             # Completed/canceled trip history
    └── oil-change.html               # Oil change KPI cards + table + modals
```

---

## 3. Architecture

```
┌──────────┐     ┌─────────┐     ┌──────────┐
│  Browser │◀───▶│  Flask  │◀───▶│ SQLite DB│
│ (Leaflet)│     │  app.py │     └──────────┘
└──────────┘     │         │
                 │  ┌──────┴──────┐
                 │  │ Background  │
                 │  │  Thread     │
                 │  │ (60s loop)  │
                 │  └──────┬──────┘
                 │         │
                 └─────────┼──────────┐
                           │          │
                     ┌─────▼──┐  ┌────▼──────┐
                     │  ORS   │  │   TTAS    │
                     │ Routes │  │ Tracking  │
                     └────────┘  └────┬──────┘
                                       │
                                ┌──────▼──────┐
                                │  Playwright  │
                                │  (login +    │
                                │   reports)   │
                                └─────────────┘
```

### Data Flow
1. **Background thread** (every 60s) fetches live vehicle positions from TTAS API
2. For each active trip, checks GPS position against geofence zones → auto-advances phases or completes trip
3. Recalculates routes (ORS or fallback) for all active and queued trips
4. Results cached in `route_data_cache` with thread-safe lock
5. **Frontend polls** (every 15s) `/api/vehicles` and `/api/route-data`
6. User actions (create/edit/cancel/advance trip) trigger immediate cache refresh

---

## 4. Database Schema

### 4.1 `vehicle_trips` — Core trip storage

| Column | Type | Description |
|---|---|---|
| `id` | `INTEGER PK AUTO` | Primary key |
| `vehicle_id` | `TEXT NOT NULL` | TTAS vehicle identifier |
| `vehicle_name` | `TEXT` | License plate / display name |
| `driver_name` | `TEXT` | Driver name (synced from TTAS) |
| `destination_lat` | `REAL` | Final destination latitude |
| `destination_lng` | `REAL` | Final destination longitude |
| `destination_name` | `TEXT` | Destination location name |
| `pickup_lat` | `REAL` | Pickup latitude |
| `pickup_lng` | `REAL` | Pickup longitude |
| `pickup_name` | `TEXT` | Pickup location name |
| `customer_name` | `TEXT` | Customer identifier |
| `vehicle_type` | `TEXT` | Vehicle type classification |
| `last_known_eta` | `REAL` | ETA in seconds (live updated) |
| `last_known_distance` | `REAL` | Distance remaining in km |
| `status` | `TEXT` | `queued` · `active` · `completed` · `canceled` |
| `phase` | `TEXT` | Current phase number (1-based) |
| `queue_order` | `INTEGER` | Order within vehicle's trip queue |
| `waypoints` | `TEXT` | JSON array: `[{name, lat, lng}, ...]` |
| `created_at` | `TIMESTAMP` | Trip creation time |
| `updated_at` | `TIMESTAMP` | Last modification |
| `completed_at` | `TIMESTAMP` | Completion timestamp |
| `canceled_at` | `TIMESTAMP` | Cancellation timestamp |
| `cancel_reason` | `TEXT` | Reason for cancellation |

### 4.2 `geofence_events` — Zone arrival audit log

| Column | Type | Description |
|---|---|---|
| `id` | `INTEGER PK AUTO` | Primary key |
| `vehicle_id` | `TEXT NOT NULL` | Vehicle identifier |
| `vehicle_name` | `TEXT` | Vehicle name at event time |
| `trip_id` | `INTEGER` | Related trip ID |
| `event_type` | `TEXT` | `arrive` (current) |
| `location_name` | `TEXT` | Geofence zone name |
| `lat` | `REAL` | GPS latitude at event |
| `lng` | `REAL` | GPS longitude at event |
| `phase` | `INTEGER` | Trip phase at event |
| `created_at` | `TIMESTAMP` | Event timestamp |

### 4.3 `oil_maintenance` — Oil change records

| Column | Type | Description |
|---|---|---|
| `id` | `INTEGER PK AUTO` | Primary key |
| `license_plate` | `TEXT NOT NULL UNIQUE` | Vehicle plate |
| `last_oil_change_km` | `INTEGER` | Odometer at last change |
| `last_oil_change_date` | `TEXT NOT NULL` | ISO date of last change |
| `maintenance_interval` | `INTEGER` | KM interval (default 5000) |
| `created_at` | `TIMESTAMP` | Record creation |
| `updated_at` | `TIMESTAMP` | Last update |

### 4.4 `oil_km_log` — KM history log

| Column | Type | Description |
|---|---|---|
| `id` | `INTEGER PK AUTO` | Primary key |
| `license_plate` | `TEXT NOT NULL` | Vehicle plate |
| `log_date` | `TEXT NOT NULL` | ISO date |
| `km` | `INTEGER` | Cumulative KM since last change |
| `fetched_at` | `TIMESTAMP` | When data was scraped |
| `UNIQUE` | `(license_plate, log_date)` | Prevents duplicates |

---

## 5. API Reference

### 5.1 Page Routes

| Method | Path | Template | Description |
|---|---|---|---|
| `GET` | `/` | `index.html` | Main dashboard with map & sidebar |
| `GET` | `/manage-trips` | `manage-trips.html` | Trip creation & management |
| `GET` | `/locations` | `locations.html` | Geofence zone editor |
| `GET` | `/trip-history` | `trip-history.html` | Trip history viewer |
| `GET` | `/oil-change` | `oil-change.html` | Oil change dashboard |

### 5.2 Vehicle & Route Data

#### `GET /api/vehicles`
Returns live (or cached) vehicle data from TTAS.
```json
{
  "vehicles": [{
    "id": "12345",
    "device_name": "51C-xxxxx",
    "driver_name": "Nguyen Van A",
    "latitude": 10.8231,
    "longitude": 106.6297,
    "speed_status": "Chạy 45 km/h",
    "vehicle_status": "running",
    "car_type": "Xe tải",
    "last_update": "07/07/2026 14:30:00",
    "position": "Quận 1, TP.HCM"
  }],
  "source": "live|sample",
  "source_url": "https://...",
  "error": null
}
```

#### `GET /api/route-data`
Returns cached route data for all active + queued trips.
```json
[{
  "trip_id": 1,
  "vehicle_id": "12345",
  "vehicle_name": "51C-xxxxx",
  "driver_name": "Nguyen Van A",
  "current_lat": 10.82,
  "current_lng": 106.63,
  "destination_lat": 10.90,
  "destination_lng": 106.70,
  "destination_name": "Warehouse B",
  "pickup_lat": 10.78,
  "pickup_lng": 106.65,
  "pickup_name": "Depot A",
  "customer_name": "ABC Corp",
  "route_coords": [[10.82,106.63], [10.85,106.65], ...],
  "distance_remaining_km": 15.3,
  "eta_seconds": 1800,
  "current_speed": 45,
  "status": "active",
  "phase": 2,
  "queue_order": 1,
  "created_at": "2026-07-07 08:00:00",
  "waypoints": [{"name":"Stop 1","lat":10.8,"lng":106.6}]
}]
```

#### `POST /api/refresh-routes`
Triggers immediate route refresh. Returns `{ success, route_data }`.

### 5.3 Trip Management

#### `POST /api/set-destination`
Create a new trip.
```json
{
  "vehicle_id": "12345",
  "vehicle_name": "51C-xxxxx",
  "destination_lat": 10.90,
  "destination_lng": 106.70,
  "destination_name": "Warehouse B",
  "pickup_lat": 10.78,
  "pickup_lng": 106.65,
  "pickup_name": "Depot A",
  "customer_name": "ABC Corp",
  "vehicle_type": "Xe tải"
}
```

#### `POST /api/update-trip`
Update trip fields. Supports: `vehicle_id`, `vehicle_name`, `destination_lat/lng/name`, `pickup_lat/lng/name`, `customer_name`, `vehicle_type`, `status`, `queue_order`, `phase`, `driver_name`, `waypoints`.

#### `POST /api/clear-trip`
Delete a trip permanently. Body: `{ trip_id, vehicle_id }`.

#### `POST /api/clear-all-trips`
Delete all trips.

#### `POST /api/advance-trip`
Force-advance or force-complete a trip. Body: `{ trip_id, action: "advance"|"complete" }`.
- `advance` → increments phase by 1 (completes if no more stops)
- `complete` → marks trip completed, activates next queued trip

#### `POST /api/cancel-trip`
Cancel a trip. Body: `{ trip_id, reason }`. Auto-activates next queued trip if the canceled trip was active.

#### `GET /api/trip-history`
Returns all trips ordered by `completed_at DESC` / `created_at DESC`.

### 5.4 Geofence & Locations

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/known-locations` | All locations in memory (normalized) |
| `GET` | `/api/manual-locations` | Raw file contents |
| `POST` | `/api/save-location` | Create or append polygon |
| `POST` | `/api/update-location` | Replace polygon (supports rename) |
| `POST` | `/api/delete-location` | Remove location |
| `POST` | `/api/clear-all-locations` | Remove all locations |
| `GET` | `/api/geofence-events?vehicle_id=&limit=100` | Geofence arrival log |

### 5.5 Geocoding

#### `GET /api/geocode?q=<query>`
Proxies to Nominatim (OpenStreetMap). Returns:
```json
{
  "success": true,
  "results": [{"name": "...", "lat": 10.8, "lng": 106.6}]
}
```

### 5.6 Oil Change

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/oil-maintenance` | All vehicles with computed metrics |
| `GET` | `/api/oil-maintenance/export` | CSV download |
| `POST` | `/api/oil-maintenance` | Add vehicle |
| `PUT` | `/api/oil-maintenance/<plate>` | Update vehicle |
| `DELETE` | `/api/oil-maintenance/<plate>` | Delete vehicle |
| `POST` | `/api/oil-maintenance/<plate>/maintenance` | Mark oil change done |
| `POST` | `/api/oil-maintenance/fetch-km` | Scrape TTAS reports for all vehicles |
| `GET` | `/api/oil-maintenance/fetch-progress` | Progress of ongoing fetch |

---

## 6. Trip Lifecycle & State Machine

```
                        ┌─────────────┐
                        │   CREATED    │
                        │  (queued)    │
                        └──────┬──────┘
                               │ (No active trip for vehicle)
                               ▼
                        ┌─────────────┐
                   ┌───▶│   ACTIVE    │◀──────────────┐
                   │    │  (phase 1)  │               │
                   │    └──────┬──────┘               │
                   │           │                      │
                   │    Arrive at geofence            │
                   │    (auto-detect)                 │
                   │           │                      │
                   │           ▼                      │
                   │    ┌─────────────┐              │
                   │    │ ACTIVE      │              │
                   │    │ (phase N+1) │              │
                   │    └──────┬──────┘              │
                   │           │                      │
                   │    Arrive at last stop           │
                   │    (auto-detect)                 │
                   │           │                      │
                   │           ▼                      │
                   │    ┌─────────────┐              │
                   │    │  COMPLETED  │              │
                   │    └─────────────┘              │
                   │                                  │
                   │    Auto-activate next queued ────┘
                   │
                   │    Manual: Force Advance
                   │            Force Complete
                   │            Cancel
                   │
                   ▼
            ┌─────────────┐
            │  CANCELED   │
            └─────────────┘
```

### Phase Mapping (Multi-Stop)

The `phase` column is a 1-based counter. The target for each phase resolves as:

| Scenario | Phase 1 | Phase 2 | Phase 3 | ... | Final Phase |
|---|---|---|---|---|---|
| Pickup + Destination | → Pickup | → Destination | — | — | → Destination |
| Pickup + WP + Dest | → Pickup | → Waypoint[0] | → Destination | — | → Destination |
| WP + Dest (no pickup) | → Waypoint[0] | → Waypoint[1] | → Destination | — | → Destination |
| Destination only | → Destination | — | — | — | → Destination |

### State Transition Rules

| Trigger | Condition | Result |
|---|---|---|
| Trip created | No active trip for vehicle | `status=active, phase=1` |
| Trip created | Active trip exists | `status=queued, queue_order=MAX+1` |
| Vehicle enters geofence | Phase target zone matched | `phase += 1` |
| Vehicle enters geofence | Last stop reached | `status=completed, phase=NULL, completed_at=now` |
| Trip completed | Queued trip exists | Next trip `status=active, phase=1` |
| Trip canceled | Was active | Next queued trip activated |
| Manual advance | Has more stops | `phase += 1` |
| Manual advance | No more stops | `status=completed` |
| Manual complete | Any phase | `status=completed`, next queued activated |

---

## 7. Geofencing System

### Location Storage Format
Locations are stored in `manual_locations.json`. Each location uses a multi-polygon structure:

```json
{
  "Warehouse A": {
    "polygons": [
      [[10.82, 106.62], [10.82, 106.64], [10.80, 106.64], [10.80, 106.62]],
      [[10.81, 106.63], [10.81, 106.635], [10.805, 106.635], [10.805, 106.63]]
    ],
    "type": "multi_polygon"
  }
}
```

Legacy formats (single `corners` array, or point+radius) are normalized to the multi-polygon format at load time.

### Point-in-Polygon Algorithm (Ray Casting)
Both server-side (`app.py`) and client-side (`utils.js`) use the same algorithm:
- Cast a horizontal ray from the point to +∞
- Count edge crossings
- Odd count → inside, Even count → outside
- Handles multi-polygons by checking each sub-polygon

### Arrival Detection
Every 60s, the background thread:
1. For each active trip, resolves the current phase target (pickup/waypoint/destination)
2. Checks if the vehicle's GPS position is inside the target's geofence zone
3. If inside:
   - Logs a `geofence_events` record with `event_type='arrive'`
   - Advances to next phase, or completes trip if last stop
4. All operations wrapped in a SQLite transaction

### Centroid Calculation
Used for placing location labels on the map. Uses the polygon area-weighted centroid formula:
- Computes signed area of the polygon
- Computes weighted average of vertex coordinates
- For multi-polygons: weighted average by area of each sub-polygon

---

## 8. Routing System (ORS Integration)

### Route Profile
`get_routing_profile(vehicle_type)` examines the vehicle type string for keywords:
- `"dau"` (truck tractor), `"heavy"`, `"truck"`, `"tai"` (truck), `"van"`
- Always returns `"driving-hgv"` (heavy goods vehicle profile)

### ORS API Call
```
GET {ORS_BASE_URL}/driving-hgv?api_key={key}&start={lng},{lat}&end={lng},{lat}
```

### Fallback
If ORS API key is missing or the request fails, falls back to great-circle distance via Haversine formula. No duration/ETA estimate on fallback.

### Caching
- Route data is cached in memory (`route_data_cache`) with a thread-safe lock
- Cache is invalidated on: trip creation, update, cancellation, or completion
- Background thread updates cache every `ROUTE_REFRESH_INTERVAL_SECONDS` (60s)
- Frontend polls every 15s and renders latest data

### Route Display
- **Active trips**: Solid blue polyline (opacity 0.8)
- **Queued trips**: Dashed gray polyline (opacity 0.4) for preview
- Only one route shown at a time (click vehicle marker to show, click map to hide)

---

## 9. TTAS Integration

### Authentication
1. Playwright opens `TTAS_LOGIN_URL`, fills username/password from `.env`
2. Waits for login redirect, extracts cookies
3. Cookies are injected into a `requests.Session`

### Live Tracking
- `POST` to `TTAS_TRACKING_API` with JSON payload
- Response: `d.DevList[]` with per-vehicle GPS, speed, engine status, driver info
- Retry logic: up to `MAX_LIVE_FETCH_ATTEMPTS` (2) attempts
- Session auto-refresh on 301/302/401/403 responses

### Vehicle Data Normalization
```
speed_status parsing:
  "Chạy ... km/h"    → vehicle_status = "running"
  "Dừng ..." + ad3="Nổ" → "stopped_engine_on"
  "Dừng ..." + ad3≠"Nổ" → "stopped_engine_off"

License plate resolution:
  biensoxe → plate → license_plate → car_number → vehicle_number → devicename
```

### Report Scraping (Oil Change)
Two approaches:
1. **Playwright-based** (`main.py.fetch_report`): Full browser for login + report navigation + HTML extraction
2. **HTTP POST-based** (`app.py._fetch_ttas_report_page`): ASP.NET WebForms-style with `__VIEWSTATE`, `__EVENTVALIDATION`

Both extract the `#tData` table containing daily KM summaries per vehicle.

### Sample Data Fallback
- When live TTAS fetch fails, loads from `log.json` (saved by `main.py` polling loop)
- Source is indicated in `/api/vehicles` response as `"source": "sample"`

---

## 10. Oil Change Maintenance

### Data Flow
```
TTAS Report (HTML)
      │
      ▼
  Playwright fetch
      │
      ▼
  Parse #tData table  ────►  oil_km_log (upsert)
      │
      ▼
  Compute metrics per vehicle:
    • total_km_since_change = Σ km_log entries
    • remaining_km = interval - total_km_since_change
    • progress_pct = (total_km / interval) × 100
    • status: <70% = safe, 70-90% = warning, ≥90% = danger
```

### Status Thresholds

| Progress | Status | Color | Meaning |
|---|---|---|---|
| `< 70%` | `safe` | Green | Within normal range |
| `70% – 90%` | `warning` | Amber | Due soon |
| `≥ 90%` | `danger` | Red | Overdue |

### Marking Maintenance Done
1. Sets `last_oil_change_date` to today
2. Deletes all `oil_km_log` entries for that vehicle
3. Triggers immediate TTAS report refetch

### Progress Tracking
- Thread-safe `_oil_fetch_progress` dictionary tracks: `total`, `current`, `plate`, `status`, `started_at`
- Client polls `/api/oil-maintenance/fetch-progress` every 500ms
- Real-time progress bar with ETA estimate

---

## 11. Frontend Overview

### Map Dashboard (`map.js`)
- **Map**: Leaflet with OpenStreetMap tiles, centered on [10.8231, 106.6297] (Ho Chi Minh City)
- **Vehicle markers**: Color-coded divIcons — green (running), amber (stopped/engine on), red (stopped/engine off), gray (unknown)
- **Filters**: Vehicle type checkboxes, status checkboxes, location search (saved + geocoded), route-only toggle
- **Popup**: Driver, speed, status, customer, pickup, destination, phase, ETA, distance, trip time, **Advance / Complete / Cancel** buttons
- **Route display**: One at a time, click marker to show, click map to hide
- **Caching**: localStorage for vehicles, routes, and known locations
- **Polling**: 15-second interval

### Trip Management (`manage-trips.js`)
- **Form**: Pickup/dropoff via saved locations or geocoded/pinned addresses
- **Vehicle selection**: Sorted by distance to pickup, filterable by search and max distance
- **Table**: Grouped by vehicle, shows phase, ETA, driver, duration, actions (Edit / Cancel / Delete)
- **Edit mode**: Loads trip data into form, allows phase override

### Geofence Editor (`locations.js`)
- Draw polygon corners by clicking the map
- Remove last corner by clicking within 50m of existing corner
- Multi-polygon support (add multiple polygons to same location)
- Rename, delete, clear all

### Trip History (`trip-history.js`)
- Full history table with duration calculation
- Edit modal: customer, vehicle, pickup, destination, status (queued/active/completed/canceled), queue order
- Delete single or clear all

### Oil Change (`oil-change.js`)
- KPI cards: total vehicles, needing attention, average progress
- Sortable table with progress bars and status pills
- Add/edit/delete vehicles, mark maintenance done, fetch KM
- Export to CSV

---

## 12. Configuration Reference

### `.env` File

| Variable | Required | Default | Description |
|---|---|---|---|
| `ORS_API_KEY` | Yes | — | OpenRouteService API key |
| `ORS_BASE_URL` | Yes | — | ORS directions endpoint |
| `TTAS_LOGIN_URL` | Yes* | — | TTAS login page |
| `TTAS_TRACKING_PAGE_URL` | Yes | — | TTAS tracking page URL |
| `TTAS_TRACKING_API` | Yes | — | TTAS real-time AJAX endpoint |
| `TTAS_USERNAME` | Yes* | — | TTAS login username |
| `TTAS_PASSWORD` | Yes* | — | TTAS login password |
| `DB_PATH` | No | `routing_system.db` | SQLite file path |
| `MANUAL_LOCATIONS_FILE` | No | `manual_locations.json` | Geofence data file |
| `DEFAULT_RADIUS_KM` | No | `3` | Default point-location radius |
| `MAX_LIVE_FETCH_ATTEMPTS` | No | `2` | TTAS retry count |
| `ROUTE_REFRESH_INTERVAL_SECONDS` | No | `60` | Background refresh interval |
| `FLASK_HOST` | No | `0.0.0.0` | Flask bind address |
| `FLASK_PORT` | No | `5000` | Flask port |
| `FLASK_DEBUG` | No | `true` | Debug mode |

*Required by `main.py` for Playwright-based login.

### Application Constants (hardcoded)
- Polling interval: 15 seconds (frontend)
- Refresh interval: 60 seconds (backend)
- Max fetch attempts: 2
- Default radius: 3 km
- Default maintenance interval: 5000 km
- Map center: [10.8231, 106.6297]
- Min zoom for labels: 14–15

---

## 13. Development Guide

### Running Locally
```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Configure .env (see Configuration Reference)
# Start the application
python app.py
```

### Key Design Patterns
- **Background thread** for route refresh (daemon thread, starts in `if __name__ == "__main__"`)
- **Thread-safe cache** using `threading.Lock` for both route data and oil fetch progress
- **SQLite** with `row_factory = sqlite3.Row` for dict-like access
- **CRUD pattern**: All resources have create/read/update/delete endpoints
- **Geofence detection** runs server-side; client mirrors the algorithm for UI consistency
- **Phase progression** is automatic (geofence-based) but with manual override

### Common Extensions
- Add new vehicle types: update `get_routing_profile()` in `app.py`
- Add new trip statuses: update schema, API validation, frontend filters
- Customize geofence radius: change `DEFAULT_RADIUS_KM` or set per-location
- Add notifications: hook into `geofence_events` table inserts
- Multi-language: UI text in templates and JS functions
