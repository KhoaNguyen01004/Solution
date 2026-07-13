# Fleet Fuel Management

A Flask-based fleet management system with fuel efficiency tracking, refuel logging, anomaly detection, and vehicle management.

## Pages

- **Map** (`/`) — GPS trip tracking
- **Fuel Efficiency** (`/fuel-efficiency`) — Dashboard for regular vehicles with KPIs, chart, refuel log
- **Container Fuel** (`/fuel-container`) — Dashboard for container vehicles with partial-tank support
- **Vehicle Management** (`/vehicle-management`) — Manage vehicles and vehicle types
- **Oil Change** (`/oil-change`) — Oil change tracking

## Fuel Efficiency Dashboard

- **All time** or monthly filter with prev/next navigation (dynamically populated from data)
- Day selector with arrows + dropdown for per-day filtering
- Combined search bar: type to filter table **or** select a vehicle to filter chart/KPIs/table
- KPI cards: Total Distance, Total Fuel, Average Efficiency (L/100km), Total Spend
- Time-series chart (Chart.js) with data labels and anomaly highlighting (red markers)
- Issue filter — show only flagged entries (spikes, no-KM, partial fills)
- Sortable table with sticky headers, anomaly/no-KM/partial row highlighting
- Add/edit/delete refuel entries via modal
- CSV export

## Container Fuel Page

- Same layout as regular fuel dashboard but scoped to container vehicles
- **Full Tank** checkbox on entry form — partial fills are stored but skipped in efficiency calc
- **Accumulated efficiency**: when a full tank is recorded, L/100km is computed from total distance and fuel since the last full tank
- Individual entries preserve their own distance/liters (no double-counting in KPIs)
- Time and Gas Store fields hidden in modal

## Anomaly Detection

- Baseline: 5-entry moving average per vehicle (or user-defined normal L/100km)
- Per-vehicle **adjustable threshold multiplier** (default: 1.50× for container, 1.20× for regular)
- Flagged when actual L/100km > normal × multiplier
- Vehicle Baselines section for per-vehicle normal and multiplier values

## Vehicle Management

- Master vehicle list with plate number, type, driver
- Vehicle type presets: 1 Ton, 1.5 Tons, 2 Tons, 3.5 Tons, 5 Tons, 8 Tons, Tractor Head, Container Truck
- Types are user-editable via the management page

## Tech Stack

- **Backend:** Python, Flask, SQLite3
- **Frontend:** Vanilla JS, Chart.js 4.4.7 (CDN)
- **No ORM** — raw SQL for full control
