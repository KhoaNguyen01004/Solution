# Fleet Fuel Management

A Flask-based fleet management system with fuel efficiency tracking, refuel logging, anomaly detection, and vehicle management.

## Pages

- **Map** (`/`) — GPS trip tracking
- **Fuel Efficiency** (`/fuel-efficiency`) — Dashboard with KPIs, time-series chart, refuel log CRUD
- **Vehicle Management** (`/vehicle-management`) — Manage vehicles and vehicle types
- **Oil Change** (`/oil-change`) — Oil change tracking

## Fuel Efficiency Dashboard

- Monthly filter with prev/next navigation (dynamically populated from data)
- Day selector with arrows + dropdown for per-day filtering
- Vehicle filter (combobox with search) — KPIs, chart, and table all update
- KPI cards: Total Distance, Total Fuel, Average Efficiency (L/100km), Total Spend
- Time-series chart (Chart.js) with anomaly highlighting (red markers)
- Sortable table with anomaly and no-KM row highlighting
- Add/edit/delete refuel entries via modal
- CSV export

## Anomaly Detection

- Baseline: 5-entry moving average per vehicle (or user-defined normal L/100km)
- Flagged when actual L/100km > baseline × 1.20
- Vehicle Baselines section for per-vehicle normal values

## Vehicle Management

- Master vehicle list with plate number, type, driver
- Vehicle type presets: 1 Ton, 1.5 Tons, 2 Tons, 3.5 Tons, 5 Tons, 8 Tons, Tractor Head, Container Truck
- Types are user-editable via the management page

## Tech Stack

- **Backend:** Python, Flask, SQLite3
- **Frontend:** Vanilla JS, Chart.js 4.4.7 (CDN)
- **No ORM** — raw SQL for full control
