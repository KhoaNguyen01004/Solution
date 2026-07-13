# System Architecture

## Overview

Flask-based fleet management system with GPS tracking, fuel efficiency logging, oil change tracking, and vehicle management. Single-page app style with vanilla JS frontend.

## Database (`routing_system.db`)

### Core Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `vehicles` | Master vehicle registry | `id`, `plate_number` (UNIQUE), `vehicle_type`, `current_driver` |
| `vehicle_types` | Editable type presets | `id`, `name` |
| `fuel_log` | Refuel entries | `id`, `license_plate`, `old_km`, `new_km`, `liters`, `unit_price`, `is_full_tank`, `vehicle_id` (FK) |
| `fuel_vehicle_profile` | Per-vehicle baselines | `license_plate` (PK), `normal_l_per_100km`, `anomaly_multiplier` |

### Supporting Tables (from original app)

- Trip tracking, oil-change, locations, route cache tables (unchanged)

## API Endpoints

### Fuel System (`/api/fuel-log`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/fuel-log` | List entries (supports `month`, `mode`, `vehicle_ids`, `license_plate`) |
| POST | `/api/fuel-log` | Create entry (supports `is_full_tank`) |
| PUT | `/api/fuel-log/<id>` | Update entry (supports `is_full_tank`) |
| DELETE | `/api/fuel-log/<id>` | Delete entry |
| GET | `/api/fuel-log/months` | Distinct months with data (`?mode=`) |
| GET | `/api/fuel-log/days` | Distinct days in month (`?month=&mode=`) |
| GET | `/api/fuel-log/stats` | Monthly stats |
| GET | `/api/fuel-log/summary` | Per-vehicle summary |
| GET | `/api/fuel-log/last-km` | Latest odometer reading |
| GET | `/api/fuel-log/profiles` | All vehicle baselines + multipliers |
| PUT | `/api/fuel-log/profiles/<plate>` | Set normal + multiplier |
| DELETE | `/api/fuel-log/profiles/<plate>` | Clear profile |
| GET | `/api/fuel-log/export` | CSV export (`?month=&mode=`) |

### Vehicle Management (`/api/fleet`)

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/api/fleet/vehicles` | List / create vehicles |
| PUT/DELETE | `/api/fleet/vehicles/<id>` | Update / delete |
| GET/POST | `/api/fleet/vehicle-types` | List / create types |
| PUT/DELETE | `/api/fleet/vehicle-types/<id>` | Update / delete |

## Frontend

### Pages

| Route | Template | JS | Purpose |
|-------|----------|----|---------|
| `/` | `index.html` | `map.js` | GPS tracking map |
| `/fuel-efficiency` | `fuel-efficiency.html` | `fuel-efficiency.js` | Regular vehicle fuel dashboard |
| `/fuel-container` | `fuel-efficiency.html` | `fuel-efficiency.js` | Container vehicle fuel dashboard |
| `/vehicle-management` | `vehicle-management.html` | `vehicle-management.js` | Vehicle CRUD |
| `/oil-change` | `oil-change.html` | `oil-change.js` | Oil change tracking |

### Shared Navigation

Secondary pages (Oil Change, Vehicles, Fuel, Container) grouped under a "Fleet ▾" dropdown on all pages.

## Fuel Efficiency Computation

### Regular Vehicles
- Standard: `l_per_100km = liters / (new_km - old_km) × 100`

### Container Vehicles (Partial Tank Support)
- **Partial fill** (`is_full_tank=0`): stored but `l_per_100km = 0` (excluded from chart/KPIs)
- **Full fill** (`is_full_tank=1`): `l_per_100km` computed from accumulated distance and liters since the last full-tank entry
- Individual `distance_km` and `liters` per entry are preserved (no double-counting in totals)

## Anomaly Detection

1. **Baseline**: manual `normal_l_per_100km` if set, otherwise 5-entry moving average of full-tank entries
2. **Threshold**: `baseline × anomaly_multiplier` (default 1.50 container, 1.20 regular)
3. **Flag**: when actual `l_per_100km > threshold`
