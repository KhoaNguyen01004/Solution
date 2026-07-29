# Trip Management Rewrite

## Objective

Completely rewrite the Trip Management module.

The current implementation is trip-oriented.

The new implementation must be **Delivery Plan oriented**.

A vehicle no longer owns a trip.

Instead:

Delivery Plan
    -> Vehicle Assignment
        -> Ordered Stops

The ordered stops define the execution sequence.

There is NO route optimization.

Vehicles always follow the imported delivery plan unless dispatch manually changes the order.

---

# Main Goals

1. Replace the current phase system.

Phase == Current Stop.

2. Support importing the daily delivery Excel.

Each row becomes a Stop.

Rows belonging to the same vehicle become one Vehicle Assignment.

3. Every stop stores

- sequence
- station code
- station information
- coordinates
- address
- manager
- phone
- product
- note

4. Current stop is determined automatically.

5. ETA must be calculated using

Current GPS

+

OpenRouteService API

+

Existing TTAS GPS integration.

Calculate ETA for

Current Position

↓

Next Stop

↓

Remaining Stops

Display ETA for every remaining stop.

No route optimization.

Always follow imported order.

---

# UI

Three panel layout.

Left

Vehicle list.

Center

Vehicle summary

Driver

GPS

ETA

Current Stop

Progress

Right

Timeline

✔ Completed

▶ Current

○ Upcoming

Clicking a stop opens

- Station details

- ETA

- Distance

- Products

- Notes

- Manager

- Phone

- Images

---

# Dispatch Features

Dispatch must be able to

- reorder stops via drag & drop

- skip stop

- cancel stop

- insert temporary stop

without recreating the trip.

---

# Image Management

Every stop supports unlimited images.

Categories

Loading

Delivery

Extra

Backend stores only relative paths.

Folder structure

DeliveryPlans/

YYYY/

MM/

DD/

Vehicle/

Station/

loading/

delivery/

extra/

Automatically create folders when uploading.

Must remain compatible with the existing folder naming convention whenever possible.

---

# Dashboard

Replace the existing trip table.

Each vehicle appears as a card showing

- Driver

- Plate

- Current Stop

- ETA

- GPS Status

- Progress

- Delay Status

Color coding

Green

On Time

Yellow

Delayed

Red

Stopped

Blue

Completed

---

# Database

Create normalized tables

delivery_plans

delivery_plan_vehicles

delivery_plan_stops

delivery_stop_images

Avoid storing duplicated station data.

Use foreign keys.

---

# Architecture

Separate

Plan

Execution

Tracking

Image

ETA

into independent services.

Avoid putting business logic inside Flask routes.

Routes should only orchestrate services.

---

# Requirements

- Mobile friendly

- Real-time updates

- Reusable APIs

- Easy future integration with driver mobile app

- Maintain compatibility with existing GPS API

- Maintain compatibility with existing ORS API

- Minimize breaking changes to existing project structure

- Provide migration scripts from the old Trip Management schema

- Add unit tests for ETA calculation, stop progression, image uploads, and stop reordering.