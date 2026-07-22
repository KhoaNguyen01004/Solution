# System Architecture

## Overview

Flask-based fleet management with GPS tracking, fuel monitoring, oil changes, and a 3D/2D truck load planner. Single-page app style with vanilla JS (Konva.js for 2D canvas, Three.js for 3D).

---

## Sorting Algorithm

### Multi-Vehicle Distribution (Largest-Vehicle-First)

**File**: `engine/distribution.py` → `distribute_across_vehicles()`

When auto-arrange is called without specifying a single vehicle, the backend distributes all packages across every vehicle using **Largest-Vehicle-First**: biggest vehicles are loaded first, smaller ones only receive leftovers.

```
Input:  [Package A, ..., Package N], [Vehicle 1, ..., Vehicle M]
Output: { placed_packages, failed_packages, per_vehicle: [{ vehicle_id, plate_number, package_count }] }

Algorithm:
1. Sort vehicles by combined capacity (volume_mm³ × payload_kg) DESC
2. For each vehicle (biggest → smallest):
      For each remaining package (biggest → smallest):
        a. Generate candidate points (origin + corners of placed boxes)
        b. Expand with 0° / 90° rotations
        c. Score candidates (4-term: contact, x-preference, floor, y-balance)
        d. Validate (boundary, weight, collision, support, door access)
        e. If valid: place_package() → door_used stored
        f. If not: keep for next vehicle
3. Return { placed, failed, unplaced, vehicle_map }
```

**Why Largest-Vehicle-First?**
- Biggest vehicles have the most capacity — fully utilising them first reduces the number of vehicles needed
- Smaller vehicles naturally receive only what big ones cannot accommodate

### Single-Vehicle Placement: `LargestFirstStrategy`

**File**: `engine/auto_arrange.py` → `LargestFirstStrategy.arrange()`

Once a vehicle is selected, the strategy places packages one-by-one:

```
For each package (sorted: non-stackable first, volume DESC, weight DESC, footprint DESC):
  1. Generate candidate points = {(0,0,0)} ∪ {right-corner, front-corner, top-corner of each placed package}
  2. For each (x,y,z), try rotation=0 and (if allow_rotation) rotation=90
  3. Score all candidates (4-term: package_contact, x_preference, floor_contact, y_balance)
  4. Validate: check_boundary(), check_weight(), check_collision(), check_support(), check_door_access()
  5. Pick the highest-scoring valid position → place_package()
  6. If none found → mark as unplaced
```

No frontier penalty, no Y-slide, no gap-filling, no repair, no compaction passes.

### Candidate Point Generation

**File**: `engine/candidate_points.py`

Points are derived from the current state of placed packages:

```
Start with: {(0, 0, 0)}
For each placed package (x, y, z) with dimensions (l, w, h):
  Add (x + l + 2*clearance, y, z)     // right face
  Add (x, y + w + 2*clearance, z)     // front face
  Add (x, y, z + h + 2*clearance)     // top face
Filter: keep points within container bounds
Sort by: (z, x, y)
```

Extreme points are offset by `+2*clearance` (10mm default) to prevent adjacent package AABBs from overlapping after inflation.

**Tighten Position**: `tighten_position()` snaps a candidate (x, y, z, rotation) back to the nearest valid extreme point. Called after initial candidate generation.

---

## Scoring Engine

**File**: `engine/scorer.py` → `score_placement()`

Every valid candidate position receives a score. The scorer never validates — invalid positions are filtered before scoring.

### Scoring Categories (4 terms)

| Category | Weight | Calculation |
|----------|--------|-------------|
| `package_contact` | 1000 | Sum of coincident-face overlap areas (mm²) across all neighboring packages |
| `x_preference` | 200 | `max(0, container.length − xmin)` — push deep into container |
| `floor_contact` | 100 | `container.width × container.length` if `z==0`, else 0 — prefer floor |
| `y_balance` | 50 | Y-COG proximity to `container.width/2` — even weight distribution |

### Design Principles
- No clamping — raw contact area and length values compete naturally
- `SCORING_WEIGHTS` dict at module top for global rebalancing
- `debug=True` prints per-category breakdown for analysis

### Y-Balance Details

Computes Y-centre-of-gravity of all packages (existing + candidate) using actual `weight_kg`:

```
score = max(0, 1 − |y_cog − container.width/2| / (container.width/2))
```

1.0 when perfectly centred, 0.0 at either wall.

---

## Validation Pipeline

**File**: `engine/validation.py` → `validate_placement()`

Every candidate position passes through 6 checks in order (cheapest first). The first failure short-circuits.

```
1. check_boundary()    — is the package fully inside the container? (uses actual AABB, no clearance)
2. check_weight()      — does total weight exceed payload?
3. check_door_fit()    — does the package cross-section fit through a door opening? (cheap, no sweep)
4. check_collision()   — does it overlap any already-placed package? (uses inflated AABB with per-axis clearance)
5. check_support()     — is the package properly supported below? (uses actual AABB, combined-support model)
6. check_door_sweep()  — is the sweep volume from position to door clear of obstacles? (most expensive)
```

### Clearance Handling in Validation

| Check | AABB Used | Rationale |
|-------|-----------|-----------|
| Boundary | Actual (no clearance) | Packages can touch walls; clearance is about inter-package gaps |
| Weight / Payload | — | Simple sum, no geometry involved |
| Door Fit | Inflated | Cross-section must clear the door opening with breathing room |
| Collision | Inflated (+clearance_xy) | Ensures horizontal gap between packages; vertical clearance uses separate `clearance_z` |
| Support | Actual (no clearance) | Support surface area should reflect physical contact, not inflated boxes |
| Door Sweep | Inflated | Sweep volume must account for the package's safety bubble |

### Door Access Validation

**File**: `engine/access.py`

Every placement is validated against vehicle features (doors from `container_features` table). If no door features are configured, the system assumes a **full-width / full-height rear door** (`width_mm = container.width`, `height_mm = container.height`), ensuring the sweep check always runs.

#### Rear Door Check
```
1. Package cross-section (width × height) fits within rear door dimensions
2. Sweep volume: AABB from package position (x, y, z) to rear wall (container.length, y+w, z+h)
3. Sweep must not intersect any already-placed package (using their inflated AABBs)
```
The sweep represents the straight-line path a forklift would take from the rear door straight into the container. If any placed package intersects this volume, the position is blocked for rear-door entry.

#### Side Door Check
```
1. Package cross-section (length × height) fits within side door dimensions
2. Package X-range [x, x+l] overlaps door X-range [position_from_front, position_from_front + width]
3. Sweep volume: from position to side wall (y=0 or y=container.width)
4. Sweep must not intersect any placed package
```
The side door is positioned at `position_from_front_mm` from the front wall. For a package to be accessible from the side, its X-range must overlap this opening. Both the right wall (y=container.width) and left wall (y=0) are checked.

#### Access Strategy
```
Try: rear door → side door (right) → side door (left)
Accept the first door with a clear sweep and valid fit.
```

### Stacking Validation

**File**: `engine/support.py` → `check_support()`

#### Combined-Support Model (Capacity-Based)

Stacking uses a capacity-based model with three modes and multiple constraints:

| Mode | Behaviour |
|------|-----------|
| `NONE` | Nothing allowed above this package |
| `LIGHT_ONLY` | Only packages ≤ `max_top_weight_kg` may stack on top |
| `NORMAL` | Stacking allowed subject to weight, layers, and coverage rules |

| Rule | Check | Implementation |
|------|-------|----------------|
| Floor | Always supported | If `z == 0`, skip all checks |
| Top package unstackable | Candidate must have `stacking_mode ≠ NONE` | Rejects if candidate itself is unstackable — prevents unstackable packages sitting on top of others |
| Stackable base | Every below package must allow stacking based on its mode | Rejects if any below package has mode `NONE`; `LIGHT_ONLY` enforces weight limit |
| Weight | Candidate lighter than every below package | Rejects if candidate weight > any below package's weight |
| Max stack layers | Each below package must not exceed `max_stack_layers` already stacked on it | Prevents tower instability |
| Footprint area | Candidate footprint ≤ every below package's footprint | Largest-area packages at the bottom |
| Combined coverage | Union of XY overlap of all below AABBs ≥ 50% of candidate footprint | Grid-samples candidate footprint at 20×20 resolution; counts samples inside any below AABB |
| Centre-of-mass | Candidate's XY centre must lie within at least one below package's XY extent | Prevents unstable bridging/overhang |

The `stackable` bool auto-derives `stacking_mode` via `Package.__post_init__()`: `stackable=False` → `stacking_mode=NONE`, which blocks stacking in both directions (cannot stack on, cannot be stacked on). Explicit `max_top_weight_kg > 0` sets `LIGHT_ONLY`.

**Why combined-support instead of per-package area?**
- Old model: each supporting package individually needed footprint ≥ candidate's footprint — impossible to straddle two smaller packages
- New model: computes the **union** of all below-package XY overlap regions; a wide box can rest on two narrower boxes side-by-side as long as their combined coverage meets the threshold and the centre is supported
- The `support_threshold` parameter (default 0.50) is configurable per call

### Support Area Grid Sampling

```python
for i in range(20):           # 20 samples along X
    for j in range(20):       # 20 samples along Y
        px = xmin + (i+0.5) * step_x
        py = ymin + (j+0.5) * step_y
        for ba in below_aabbs:
            if ba.xmin <= px <= ba.xmax and ba.ymin <= py <= ba.ymax:
                supported += 1
                break   # counted once even if in multiple below AABBs
coverage = supported / 400
```

The grid resolution (20×20 = 400 samples) provides ~5% precision, which is adequate for a 90% threshold with margin.

---

## Step Animation & 3D Controls

After auto-arrange completes, the frontend sorts placements by `load_sequence` and plays them one-by-one in the Three.js 3D view.

```
1. Sort placements by load_sequence ASC
2. For each step:
   a. Read door_used field from placement
   b. Choose start position based on door:
      - "rear":       (container.length + pkg_length, y, z)  — outside rear wall
      - "side_right": (x, y, container.width + pkg_width)     — outside right wall
      - "side_left":  (x, y, -pkg_width)                      — outside left wall
   c. Create a mesh at start position
   d. Tween to final position over 500ms with cubic ease-out (1 − (1−t)³)
   e. On completion, convert to permanent mesh
3. Auto-play advances every 700ms (500ms tween + 200ms pause)
```

**Source**: `static/js/truck-load-planner.js:3126` — `_stepNext()` reads `placement.door_used` and computes the correct entry point. The backend stores `door_used` in `Placement.door_used` (default `"rear"`).

The animation is driven by `requestAnimationFrame` inside the existing `_animate3D()` loop. Step meshes are tracked separately from the main scene to avoid conflicts with normal `update3DScene()` calls.

### 3D Toolbar Controls

A built-in toolbar inside the 3D container provides step controls and fullscreen toggle:

| Control | ID | Behaviour |
|---------|----|-----------|
| ◀ Prev | `tlp-3d-btn-prev` | Go back one step, re-show previous packages |
| 0/15 | `tlp-3d-step-counter` | Current step / total |
| ▶ Next | `tlp-3d-btn-next` | Advance one step with fly-in animation |
| ▶▶ Play | `tlp-3d-btn-play` | Toggle auto-play; icon changes to ⏸ when playing |
| ⏭ End | `tlp-3d-btn-end` | Show all packages immediately |
| ⛶ / ❌ | `tlp-3d-btn-fullscreen` | Toggle fullscreen mode (CSS fixed overlay, not native API) |

**Visibility**: toolbar is `opacity: 0` by default, `opacity: 1` on hover or when `.fullscreen` class is active.

**Persistence**: after animation completes or user clicks "Show all", the buttons remain visible (step mode stays active). Only switching vehicles or closing the 3D view hides them.

### Package Labels

Each package in the 3D view renders a text sprite showing its name 30px above the top face. Created by `_makeTextSprite()` which draws the name onto a canvas texture and wraps it in `THREE.Sprite`.

### Fullscreen

- **Keyboard**: `F` toggles fullscreen, `Escape` exits
- **CSS**: `.fullscreen` class on `#tlp-3d-container` sets `position: fixed; inset: 0; z-index: 9999`
- **No native Fullscreen API** — the CSS approach avoids browser permission quirks

---

## Database

### TLP Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `tlp_packages` | Package definitions | `id`, `name`, `length`, `width`, `height`, `weight_kg`, `color`, `allow_rotation`, `allow_stacking`, `default_qty` |
| `tlp_shipments` | Customer orders | `id`, `customer_name`, `reference`, `notes` |
| `tlp_shipment_items` | Package-quantity links | `id`, `shipment_id` (FK), `package_id` (FK), `quantity` |
| `tlp_load_plans` | Saved plans | `id`, `name`, `vehicle_id` (FK), `shipment_id` (FK), `status`, `planner`, `notes` |
| `tlp_placements` | Individual placements | `id`, `load_plan_id` (FK), `package_id` (FK), `x`, `y`, `z`, `rotation`, `load_sequence` |
| `container_configs` | Container/trailer dimensions | `id`, `name`, `cargo_length_mm`, `cargo_width_mm`, `cargo_height_mm`, `payload_kg` |
| `container_features` | Doors, lift gates | `id`, `container_config_id` (FK), `feature_type`, `geometry_json` |

### Feature Geometry Schema

**Rear door** `geometry_json`:
```json
{ "width_mm": 1800, "height_mm": 1900 }
```

**Side door** `geometry_json`:
```json
{ "width_mm": 1200, "height_mm": 1800, "position_from_front_mm": 2400 }
```

---

## API: Auto-Arrange Endpoint

```
POST /api/tlp/auto-arrange
```

**Body** (no `vehicle_id` = multi-vehicle distribution):
```json
{
  "strategy": "largest_first",
  "shipment_id": 1,
  "debug": false
}
```

**Response**:
```json
{
  "multi_vehicle": true,
  "success": true,
  "summary": {
    "placed_packages": 42,
    "failed_packages": 0,
    "utilization": 78.3,
    "warnings": [],
    "unplaced_packages": []
  },
  "per_vehicle": [
    { "vehicle_id": 1, "plate_number": "51C-123.45", "package_count": 24, "statistics": { "volume_used_pct": 82.1 } },
    { "vehicle_id": 3, "plate_number": "51C-678.90", "package_count": 18, "statistics": { "volume_used_pct": 65.4 } }
  ],
  "placements": [
    { "package_id": 5, "x": 0, "y": 0, "z": 0, "rotation": 0, "load_sequence": 1, "vehicle_id": 1, "_name": "Widget A", ... }
  ]
}
```

---

## 2D Canvas View Coordinates

The frontend renders three orthogonal views of the container using Konva.js. Each view maps two container axes onto the canvas:

| View | Canvas X | Canvas Y | Ruler X Label | Ruler Y Label |
|------|----------|----------|---------------|---------------|
| **Top** | Container length (front→rear) | Container width (left→right) | X | Y |
| **Side** | Container length (front→rear) | Container height (floor→ceiling) | X | Z |
| **Back** | Container width | Container height | W | Z |

### Back View (Rear Perspective)

The back view renders the cargo area as seen from the rear door looking toward the front. Since the viewer faces forward (same direction as the truck), **the left wall (Y=0) appears on the right side of the canvas** and the right wall (Y=width) appears on the left.

Coordinate flips are applied consistently across rendering (`_drawPackages`, `_focusOnPackage`), drag-and-drop, preview, validation (`_quickValidate`, `_throttledValidate`), and placement (`_onDrop`). The generic `_mmToStage` / `_stageToMm` converters remain unfipped — all view-specific logic is handled at the call site.

## Frontend: Arrange Results

After auto-arrange, the left sidebar shows an **Arrange Results** section. Each row represents a vehicle that received packages:

```
┌─ Arrange Results ────────────────────┐
│  51C-123.45          24 pkgs         │  ← clickable, switches viewer
│  51C-678.90          18 pkgs         │
└──────────────────────────────────────┘
```

Clicking a vehicle:
1. Calls `_selectVehicle(vehicle_id)` — loads container config, resets placements
2. Filters `_arrangePlacements` to that vehicle's packages
3. Re-renders the 2D canvas and 3D view
4. Starts step animation for that vehicle
5. Highlights the active row
