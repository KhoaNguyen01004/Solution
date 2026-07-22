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

### Multi-Vehicle Distribution (Largest-Vehicle-First)

When auto-arrange is triggered, all packages are distributed across every vehicle that has a container config. The algorithm (`distribute_across_vehicles` in `engine/distribution.py`) uses **Largest-Vehicle-First**:

1. **Sort packages** by volume descending (biggest first)
2. **Sort vehicles** by combined capacity (volume × payload) descending
3. **For each vehicle** (biggest → smallest): try to place all remaining packages, then pass leftovers to the next smaller vehicle
4. **Local rearrangement**: when the only feasible candidate for a package is a stack, and the container has ≤10 floor packages, `_try_local_rearrangement()` identifies blocking floor packages (clearance-aware AABB overlap), removes ≤3, places the package on the floor, re-places blockers, and accepts only if floor score > stack score
5. **Result**: The largest vehicles are loaded first, smaller ones only receive what big ones cannot fit

### Placement Strategy: `LargestFirstStrategy`

Within each vehicle, the `LargestFirstStrategy` (`engine/auto_arrange.py`) places packages one at a time:

1. **Sort**: by volume descending (biggest first)
2. **For each package**:
   - Generate candidate positions from the right/front/top corners of all placed packages + origin (0,0,0)
   - Add a **right-wall-aligned candidate** `(0, container.width - pkg.width - clearance, 0)` for balanced left-right placement
   - Add **floor anchor candidates** via `generate_floor_anchors()` — finds the largest empty floor rectangles via Y-boundary sweep, generating front/center/rear positions for the top 2 regions
   - Expand each candidate with both 0° and (if allowed) 90° rotation
   - **Score all candidates** on 13 weighted criteria (see Scoring Engine), then **tighten the top 5** via `tighten_position()` (snaps back to nearest extreme point after rotation), then **re-score** before picking the best
   - Validate each candidate: boundary, weight, door fit, collision, support, door sweep
   - Pick the highest-scoring position and commit
   - Early-exit: stop scanning candidates once any score ≥ 99.99
3. **Y-slide fallback**: if no position found for a package, slide each base candidate left/right in Y by steps of 100mm (up to 3 steps each direction) to squeeze in more packages per vehicle

### Frontier-Based Gap Prevention

To prevent gaps left by greedy placement, the `FrontierTracker` (`engine/frontier.py`) maintains a 1D Y-strip frontier — for each Y strip (default 200–250 mm wide), it tracks the maximum X (depth) of the packed front. During scoring, candidates receive a **gap penalty**:

```
gap_distance = frontier(Y) − candidate.x     # negative = behind frontier (in a gap)
gap_ratio = gap_distance / container.length
penalty = −min(gap_distance × (0.5 + gap_ratio × 0.5), 500)
```

This strongly penalizes positions that leave a gap behind the current frontier, pushing packages flush against the nearest packed face.

### Frontier Gap-Filling Pass (`fill_frontier_gaps`)

After the initial greedy sweep, `fill_frontier_gaps()` in `engine/distribution.py` scans all placed packages and tries to resettle any that sit behind the frontier:

1. For each package sorted by X, compute the frontier at its Y-strip
2. If `package.xmin > frontier`, flag as gapped
3. Try `settle_package()` (analytical O(K) snap to nearest extreme point)
4. Only if settle gives no improvement, fall back to `tighten_position()`
5. Re-place only when meaningful forward improvement ≥ 1 mm
6. Update frontier immediately after each re-placement

This closes the persistent gap bug where LC 900 units landed at x≈3.2–3.5 m instead of flush against KBF 280R's right edge (x≈1.07 m). The remaining 20 mm gap is the minimum physically achievable (2 × 10 mm horizontal clearance).

### Detailed Debug Instrumentation

When `debug=True` is passed to auto-arrange, each debug entry now includes:
- `all_candidate_details`: every candidate evaluated with input position, tightened position, validity, raw score, gap penalty, stack ceiling penalty, full breakdown, adjusted score
- `slide_details`: Y-slide fallback candidates with same level of detail

A standalone debugger `scripts/debug_arrange.py` logs every step, frontier state, and decision for all packages to a timestamped report file.

### Clearance Margin

Every package gets configurable per-axis clearance: `horizontal_clearance_mm` (default **10mm**) on all 4 horizontal sides, and `vertical_clearance_mm` (default **0mm**) on top/bottom (stacks rest directly on each other). The spatial index stores inflated AABBs; extreme points are offset by `+2 * horizontal_clearance`; collision detection uses per-axis inflated AABBs. The boundary check and support calculations use the actual (non-inflated) AABB so packages can still touch container walls and rest on each other. The deprecated `clearance_mm` field maps to `horizontal_clearance_mm` for backward compatibility.

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

Every valid candidate position receives a 0–200 quality score. The scorer never determines validity — it only ranks valid positions.

| Category | Weight | Raw → Score |
|----------|--------|-------------|
| Floor Contact | 40 | 1.0 if z=0, else 0.0 |
| Wall Contact | 2 | walls_touched ÷ 4 |
| Package Contact | 8 | contact_area ÷ max_possible (coincident face overlap) |
| Face Contact | 2 | faces_touched ÷ 6 |
| Compactness | 15 | max(0, 1 − nearest_centroid_dist ÷ 2000) |
| Stack Quality | 0 | support_area ÷ footprint_area (if stacked) |
| Vertical Stability | 5 | max(0, 1 − mid_z ÷ container_height) |
| Z Preference | 50 | max(0, 1 − zmin ÷ container_height) |
| X Preference | 120 | max(0, 1 − xmin ÷ container_length) — rewards deep (front-wall) placement |
| Rear Proximity | 200 | min(1, gap ÷ threshold) where gap = rear-wall distance, threshold = max(8% length, 300mm) |
| Y Balance | 3 | rewards Y-center-of-gravity close to container midpoint for even left-right weight distribution |
| Cluster Cohesion | 10 | rewards positions near centroid of all placed packages (small+deep+compact bonus) |
| Dead Space Quality | 3 | 0–1 estimate of how usable remaining free space is for future packages (see `engine/dead_space.py`) |
| Load Profile Stability | 3 | `max_step ÷ container_height` — penalises tall vertical steps; higher is flatter (see below) |

Weights are configurable via `SCORING_WEIGHTS` at module top (total 461, clamped to `MAX_POSSIBLE_SCORE = 200.0`).

### Stacking Rules (`engine/support.py`)

A package may only be placed on top of another when ALL conditions hold:

1. The **candidate package itself** must be stackable (`stackable = True`, i.e. `stacking_mode ≠ NONE`) — unstackable packages cannot sit on top of anything
2. The package below must allow stacking (`stacking_mode ≠ NONE`); supports three modes:
   - `NONE` — no stacking allowed on this package
   - `LIGHT_ONLY` — only lighter packages (`≤ max_top_weight_kg`) may stack on top
   - `NORMAL` — stacking allowed subject to other rules
3. **Weight**: above package is **lighter** than every package it rests on
4. **Max stack layers**: the package below must not exceed `max_stack_layers` packages already stacked on it
5. **Footprint area**: above package's footprint must be ≤ every below package's footprint
6. **Combined support coverage**: the **union** of XY-overlap regions from all packages directly below must cover ≥ 50% of the candidate's footprint (grid-sampled at 20×20 resolution)
7. **Centre-of-mass**: the candidate's XY footprint centre must lie within at least one below package's XY extent (prevents unstable bridging)

An unstackable package is only allowed on the floor (z=0). Attempting to stack it on top of another package, or stack another package on top of it, is rejected.

The `stackable` bool auto-derives `stacking_mode` via `Package.__post_init__()`: `stackable=False` → `stacking_mode=NONE`, which blocks stacking in both directions.

The combined-support model allows a package to straddle multiple smaller packages side-by-side, as long as the union of their top faces covers the required area and the centre is supported.

Ceiling height is enforced by the boundary check — any candidate whose top exceeds `container.height` is rejected.

### Load Profile Stability

The `_score_load_profile_stability` function (`engine/scorer.py`) evaluates the flatness of the packed cargo profile. The container floor is divided into **10 longitudinal slices** (`NUM_PROFILE_SLICES`). For each slice, the maximum occupied height is recorded. The score is:

```
max_step = max |height[i] − height[i−1]| across all slices
score = max(0, 1 − max_step / container.height)
```

This rewards layouts with small vertical steps (flat cargo surfaces) and penalises tall isolated stacks. Weight 8 creates a meaningful gradient (4+ point gap between flat and tower-heavy layouts) without dominating the other 12 factors.

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

After auto-arrange, the 3D view shows packages entering one-by-one in `load_sequence` order. Each package starts outside its entry door and slides into position over 500ms with cubic ease-out. The entry point is determined by the `door_used` field from backend validation:

- `"rear"` → outside rear wall (`x = container.length + package.length`)
- `"side_right"` → outside right wall (`y = container.width + package.width`)
- `"side_left"` → outside left wall (`y = -package.width`)

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
2. `validate_placement()` — progressive filter (cheapest first):
   - **Boundary** — actual AABB (no clearance) vs container bounds
   - **Payload / Weight** — total weight with candidate vs container payload
   - **Door fit** — cross-section fits through door opening (cheap, no sweep)
   - **Collision** — inflated AABB (with per-axis clearance) against all placed packages
   - **Support** — actual AABB, combined-support model (union coverage + centre-of-mass)
   - **Door sweep** — sweep volume from position to door must be clear (most expensive)
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
| `auto_arrange.py` | Strategy-based auto-arrange (LargestFirstStrategy) with Y-slide fallback, frontier gap penalty, debug instrumentation |
| `distribution.py` | Multi-vehicle fleet distribution (Largest-Vehicle-First), frontier gap-filling pass |
| `repair.py` | Destroy-and-Repair fleet optimizer (Large Neighborhood Search) |
| `consolidation.py` | Near-empty vehicle elimination pass |
| `frontier.py` | 1D Y-strip frontier tracker for gap-aware placement |
| `validation.py` | All rule checks: boundary, collision, weight, support, door access |
| `access.py` | Door access validation (rear + side sweep checks) |
| `support.py` | Stacking validation with combined-support model (union overlap + centre-of-mass) |
| `scorer.py` | 14-category placement quality scoring (0–200) with frontier gap penalty |
| `state.py` | Planner state: spatial index, extreme points, placement mutations |
| `spatial.py` | Spatial hash grid for fast AABB queries |
| `geometry.py` | AABB with clearance-aware from_dimensions, overlap/intersection/translation |
| `collision.py` | AABB collision detection |
| `boundary.py` | Container boundary containment |
| `candidate_points.py` | Candidate position generator + Y-slide candidate generator |
| `dead_space.py` | Future-packability estimation — gap distance to nearest obstacle, difficulty-weighted reference set, continuous face scoring |
| `statistics.py` | Utilization, weight, and package counts |
| `weight.py` | Total weight vs payload calculation |
| `container.py` | Container dataclass (dimensions, features, payload) |
| `package.py` | Package dataclass (dimensions, stackable, rotation, per-axis clearance, stacking_mode, max_top_weight_kg, max_stack_layers) |
| `placement.py` | Placement dataclass (position, rotation, sequence, door_used) |

---

## Experimental: py3dbp Packing Engine

An experimental integration of the [py3dbp](https://pypi.org/project/py3dbp/) 3D bin-packing library is available as an alternative packing engine for benchmarking purposes.

### Usage

```bash
# Run with internal engine (default, unchanged behavior)
python manual_test.py

# Run with py3dbp engine
python manual_test.py --engine py3dbp

# Side-by-side comparison
python manual_test.py --compare

# Select engine via environment variable
set PACKING_ENGINE=py3dbp
python manual_test.py
```

### Architecture

Both engines implement the `PackingEngine` interface defined in `truck_load_planner/engines/base.py`:

- `InternalPackingEngine` — wraps the existing distribution/repair/consolidation pipeline
- `Py3dbpPackingEngine` — converts packages and containers to py3dbp types, runs the packer, then validates all placements through the existing validation pipeline

Engine selection is handled by `truck_load_planner/engines/__init__.py::get_engine()`.

### Feature Comparison

| Feature | Internal Engine | py3dbp Engine |
|---------|---------------|---------------|
| Geometry Packing | ✅ | ✅ |
| Rotation (2D) | ✅ | ✅ |
| Weight Limit | ✅ | ✅ |
| Collision Detection | ✅ | ✅ |
| Stackable / Non-stackable | ✅ | Validation Layer |
| Max Top Weight | ✅ | Validation Layer |
| Max Stack Layers | ✅ | Validation Layer |
| Door Accessibility | ✅ | Validation Layer |
| Support Percentage | ✅ | Validation Layer |
| Center of Gravity | ✅ | Validation Layer |
| Vehicle Consolidation | ✅ | Existing Pipeline |
| Clearance Margins | ✅ | Validation Layer |

- **Native**: Features py3dbp supports directly via its geometric packing algorithm
- **Validation Layer**: Features enforced by running our existing validation pipeline on py3dbp's output. If validation fails, the package is marked as unplaced and processing continues.

### Known Limitations

- py3dbp uses full 3D rotation (6 axis permutations), while our system uses 2D rotation (swap x/y only). Placements with incompatible rotations are rejected.
- py3dbp does not natively support clearance margins, stacking rules, door access, or center-of-gravity constraints.
- py3dbp sorts bins by volume descending, which may spread packages across more vehicles than the internal engine's best-fit decreasing strategy.

## Project Structure

```
app.py                          # Main Flask application entry point
main.py                         # Standalone TTAS GPS tracking tool
manual_test.py                  # Manual pipeline test with instrumentation
scripts/                        # Debug, benchmark, and utility scripts
  debug_arrange.py               # Step-by-step per-package debugger with frontier analysis
  benchmark_floor_contact.py
  benchmark_real_data.py
  check_shipment_data.py
  count_tables.py
  debug_py3dbp.py / debug_stats.py / debug_validation.py / debug_vehicles.py
  diagnose_candidates.py / diagnose_stacking_decision.py
  query_db.py / query_shipments.py
  read_instrument_trace.py
truck_load_planner/             # Core application package
  routes.py                     # Flask routes / API endpoints
  session.py                    # Load planning session
  db.py                         # Database initialization
  engine/                       # Packing algorithms (20 modules)
  engines/                      # Packing engine abstraction (internal + py3dbp)
  models/                       # Data models
  logistics/                    # Legacy logistics helpers
static/                         # Frontend assets (JS, CSS)
templates/                      # HTML templates
tests/                          # Pytest test suite
```

## Tech Stack

- **Backend**: Python, Flask, SQLite3
- **Frontend**: Vanilla JS, Chart.js 4.4.7, Konva.js 9 (canvas), Three.js (3D)
- **No ORM** — raw SQL for full control
