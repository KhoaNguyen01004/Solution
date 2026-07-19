# Fleet Fuel Management

Flask-based fleet management with GPS tracking, fuel monitoring, and a 3D/2D **Truck Load Planner** featuring a multi-vehicle bin-packing algorithm, door-aware access validation, and step-by-step placement animation.

## Pages

- **Map** (`/`) — GPS trip tracking with geofencing (Ray Casting)
- **Fuel Efficiency** (`/fuel-efficiency`) — Dashboard with KPIs, chart, refuel log
- **Container Fuel** (`/fuel-container`) — Container-vehicle dashboard with partial-tank support
- **Truck Load Planner** (`/truck-load-planner`) — 3D/2D cargo loader with auto-arrange, stacking, step animation
- **Vehicle Management** (`/vehicle-management`) — Vehicle CRUD and interactive 3D container diagram (Three.js)
- **Oil Change** (`/oil-change`) — Oil change tracking

---

## Truck Load Planner — Algorithm Reference

### Multi-Vehicle Distribution (Best-Fit Decreasing)

When auto-arrange is triggered, all packages are distributed across every vehicle that has a container config. The algorithm (`_distribute_across_vehicles` in `routes.py`) uses **Best-Fit Decreasing (BFD)**:

1. **Sort packages**: non-stackable first, then by descending volume → footprint → weight
2. **Track active vehicles**: indices of vehicles that already hold at least one package
3. **For each package**:
   - **Phase 1**: Try every active (already-used) vehicle first — candidate positions are generated and validated, then the vehicle whose resulting fullness (sum of volume%, floor%, payload%) is **highest** (tighter fit) wins
   - **Phase 2**: If no active vehicle works, open the next unused vehicle
   - **Phase 3**: If the best position touches the rear wall (`xmax ≥ container.length`), redirect the package to the last vehicle unconditionally (fills the last vehicle's unused space with rear-door items)
4. **Result**: Packages are placed into the vehicle they fit best, minimising waste space across the fleet

The **two-tier comparator** picks the best vehicle for each package:
- **Primary**: `sum(estimated_volume_remaining%, floor_remaining%, payload_remaining%)` — lower = tighter fit = better
- **Secondary (tiebreaker)**: placement score

### Placement Strategy: `LargestFirstStrategy`

Within each vehicle, the `LargestFirstStrategy` (`engine/auto_arrange.py`) places packages one at a time:

1. **Sort**: non-stackable → largest volume → largest footprint → heaviest
2. **For each package**:
   - Generate candidate positions from the right/front/top corners of all placed packages + origin (0,0,0)
   - Add a **right-wall-aligned candidate** `(0, container.width - pkg.width - clearance, 0)` for balanced left-right placement
   - Expand each candidate with both 0° and (if allowed) 90° rotation
   - Validate each candidate: boundary, collision, weight, support, door access
   - Score valid candidates on 10 weighted criteria (see Scoring Engine)
   - Pick the highest-scoring position and commit
   - Early-exit: stop scanning candidates once any score ≥ 99.99
3. **Y-slide fallback**: if no position found for a package, slide each base candidate left/right in Y by steps of 100mm (up to 3 steps each direction) to squeeze in more packages per vehicle

### Clearance Margin

Every package gets a **10mm clearance bubble** on all 6 sides (configurable via `clearance_mm` field). The spatial index stores inflated AABBs; extreme points are offset by `+2 * clearance`; collision detection uses inflated AABBs. The boundary check and support calculations use the actual (non-inflated) AABB so packages can still touch container walls and rest on each other.

### Candidate Priority (Pre-Validation Ranking)

Before the expensive validation loop, every candidate (extreme point + rotation) is ranked by `_candidate_priority()` (module-level function in `routes.py`). This speeds up the search by testing high-potential positions first so the validation loop can early-exit once a near-perfect candidate is confirmed.

| Factor | Weight | Calculation |
|--------|--------|-------------|
| Touching Surfaces | 0–60 | Count of container walls touched (rear, left, right, floor) × 15 |
| Z-Height | 0–15 | `1 − z / container_height` — prefers floor-level |
| Wall-Contact Area | 0–15 | Sum of touching edge lengths ÷ max possible perimeter × 15 |
| Back-to-Front Loading | 0–20 | `1 − x / container_length` × 20 — prefers rear (low X) |
| Front-Center Proximity | 0–10 | `1 − dist_from_front_center / diagonal` × 10 — prefers near front-center with no Y bias |

Candidates are sorted by priority descending before validation. The first candidate that validates and scores ≥ 99.99 is committed immediately.

### Scoring Engine (`engine/scorer.py`)

Every valid candidate position receives a 0–100 quality score. The scorer never determines validity — it only ranks valid positions.

| Category | Weight | Raw → Score |
|----------|--------|-------------|
| Floor Contact | 25 | 1.0 if z=0, else 0.0 |
| Wall Contact | 10 | walls_touched ÷ 4 |
| Package Contact | 15 | contact_area ÷ max_possible (coincident face overlap) |
| Face Contact | 10 | faces_touched ÷ 6 |
| Compactness | 5 | max(0, 1 − nearest_centroid_dist ÷ 2000) |
| Stack Quality | 5 | support_area ÷ footprint_area (if stacked) |
| Vertical Stability | 10 | max(0, 1 − mid_z ÷ container_height) |
| Z Preference | 10 | max(0, 1 − zmin ÷ container_height) |
| X Preference | 5 | max(0, 1 − xmin ÷ container_length) — rewards deep (front-wall) placement |
| Rear Proximity | 10 | min(1, gap ÷ threshold) where gap = rear-wall distance, threshold = max(8% length, 300mm) |
| Y Balance | 15 | rewards Y-center-of-gravity close to container midpoint for even left-right weight distribution |
| Dead Space Quality | 10 | 0–1 estimate of how usable remaining free space is for future packages (see `engine/dead_space.py`) |

Weights are configurable via `SCORING_WEIGHTS` at module top (total 130, clamped to 100).

### Stacking Rules (`engine/support.py`)

A package may only be placed on top of another when ALL conditions hold:

1. The package below has **Allow Stacking** enabled (`stackable = True`)
2. **Weight**: above package is **lighter** than every package it rests on
3. **Combined support coverage**: the **union** of XY-overlap regions from all packages directly below must cover ≥ 90% of the candidate's footprint (grid-sampled at 20×20 resolution)
4. **Centre-of-mass**: the candidate's XY footprint centre must lie within at least one below package's XY extent (prevents unstable bridging)

Unlike the old per-package area check, the combined-support model allows a package to straddle multiple smaller packages side-by-side, as long as the union of their top faces covers the required area and the centre is supported.

> **Note**: `stackable` defaults to `False` (0) across all layers — session, planner, and API. The frontend checkbox must be explicitly enabled for a package to be used as a stacking base.

Ceiling height is enforced by the boundary check — any candidate whose top exceeds `container.height` is rejected.

### Door Access Validation (`engine/access.py`)

Every candidate position is validated to ensure the package can physically reach it through at least one door:

**Rear Door** (primary entry at `x = container.length`):
- Cross-section (width × height) must fit within door opening
- Sweep volume from rear wall to position must be clear of already-placed packages
- Package slides straight in along −X

**Side Door** (left wall `y = 0` or right wall `y = container.width`):
- Cross-section (length × height) must fit within door opening
- Package's X-range must overlap the door's X-range (position_from_front_mm)
- Sweep volume from side wall to position must be clear
- Tried for both left and right walls

The backend tries rear door first, then all side doors. If no door provides clear access, the position is rejected. This naturally enforces a front-to-back loading order — early packages go to the front, and the sweep from the rear door remains clear.

When a vehicle has no door features configured, the system assumes a full-width/full-height rear door (`width_mm = container.width`, `height_mm = container.height`), so the sweep check always runs.

### Step Animation & 3D Controls

After auto-arrange, the 3D view shows packages entering one-by-one in `load_sequence` order. Each package starts outside the rear door (`x = container.length + package.length`) and slides into its final position over 500ms with cubic ease-out.

| Control | Action |
|---------|--------|
| ◀ Prev | Previous step |
| 0/15 | Step counter |
| ▶ Next | Next step |
| ▶▶ Play | Auto-play all |
| ⏭ End | Show all immediately |
| ⛶ / ❌ | Toggle fullscreen (F key / Escape) |
| Package name labels | Text sprites rendered 30px above each package |

Controls are available in both the main toolbar and the 3D view's built-in toolbar. Keyboard shortcuts: **F** toggles fullscreen, **Escape** exits fullscreen.

### Arrange Results Panel

After multi-vehicle distribution, the left sidebar shows an **Arrange Results** section listing every vehicle that received packages with its count. Click any vehicle to view its placements and start step animation for that vehicle.

### Validation Pipeline

1. Client-side `_quickValidate()` — view-aware boundary and collision pre-check
2. `planner.validate_position()` — boundary, collision, weight vs payload, support (combined area + weight), door access (rear + side sweep)
3. Failed validations produce human-readable reasons (e.g. "Collision with 'Widget A'", "Package cannot reach position through any door")

### 2D View Coordinate System

The canvas provides three views, each mapping different container axes:

| View | Canvas X → | Canvas Y → | X Label | Y Label |
|------|------------|------------|---------|---------|
| **Top** | Length (X) | Width (Y) | X | Y |
| **Side** | Length (X) | Height (Z) | X | Z |
| **Back** | Width (Y) | Height (Z) | W | Z |

**Back view (rear perspective)**: the left wall of the truck (Y=0) appears on the right side of the canvas, and the right wall (Y=width) appears on the left — matching the real-world view when looking from the rear toward the front.

### Drag & Drop UX

- **Repositioning**: Konva native drag preserves grab offset
- **Boundary clamping**: packages cannot be dragged outside container bounds
- **Snap to grid**: toggleable 25 mm grid
- **Pan**: click-drag empty canvas background
- **Rotate**: toolbar buttons cycle through 0°/90°/180°/270°
- **Undo/Redo**: full stack with Ctrl+Z / Ctrl+Shift+Z

---

## Engine Architecture (`truck_load_planner/engine/`)

| Module | Responsibility |
|--------|---------------|
| `planner.py` | Orchestrates all planning operations |
| `auto_arrange.py` | Strategy-based auto-arrange (LargestFirstStrategy) with Y-slide fallback |
| `validation.py` | All rule checks: boundary, collision, weight, support, door access |
| `access.py` | Door access validation (rear + side sweep checks) |
| `support.py` | Stacking validation with combined-support model (union overlap + centre-of-mass) |
| `scorer.py` | 11-category placement quality scoring (0–100) |
| `geometry.py` | AABB with clearance-aware from_dimensions, overlap/intersection/translation |
| `collision.py` | AABB collision detection |
| `boundary.py` | Container boundary containment |
| `candidate_points.py` | Candidate position generator + Y-slide candidate generator |
| `dead_space.py` | Future-packability estimation — gap distance to nearest obstacle, difficulty-weighted reference set, continuous face scoring |
| `statistics.py` | Utilization, weight, and package counts |
| `weight.py` | Total weight vs payload calculation |
| `container.py` | Container dataclass (dimensions, features, payload) |
| `package.py` | Package dataclass (dimensions, stackable, rotation, clearance) |
| `placement.py` | Placement dataclass (position, rotation, sequence) |

---

## Tech Stack

- **Backend**: Python, Flask, SQLite3
- **Frontend**: Vanilla JS, Chart.js 4.4.7, Konva.js 9 (canvas), Three.js (3D)
- **No ORM** — raw SQL for full control
