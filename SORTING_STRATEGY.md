# Sorting Strategy & Algorithms — Truck Load Planner

## 1. Package Sort Order (Pre-Processing)

All packages are sorted **before** any placement logic runs. The same sorting key is used in both single-vehicle and multi-vehicle paths.

**Source**: `engine/auto_arrange.py:51`, `routes.py:901`

```python
sorted_packages = sorted(packages, key=lambda p: (
    p.stackable,                          # ASC:  False (0) → True (1)
    -(p.length_mm * p.width_mm * p.height_mm),  # DESC: volume
    -(p.length_mm * p.width_mm),          # DESC: footprint
    -p.weight_kg,                         # DESC: weight
))
```

### Rationale per field

| Field | Direction | Why |
|-------|-----------|-----|
| `stackable` | ASC (0 then 1) | Non-stackable packages **must** go on the floor. Placing them first guarantees floor space is available. Stackable packages come later and get placed on top. |
| Volume | DESC | Largest packages are hardest to fit — placing them first maximises the chance they find a spot. |
| Footprint | DESC | Secondary size metric; breaks ties when volume is equal. |
| Weight | DESC | Heaviest packages first ensures they get floor placement (good for stability). Lighter packages can stack on top. |

### Why this order?

- **Non-stackable first** → floor reservation (if non-stackable were last, they might have no floor space left)
- **Largest first** → greedy bin-packing heuristic; large items are the most constrained, so placing them early reduces failure rate
- **Heaviest first** → weight distribution; heavy items on the floor lower the centre of gravity

---

## 2. Vehicle Selection (Multi-Vehicle Distribution)

When no single `vehicle_id` is specified, packages are distributed across all available vehicles.

**Source**: `routes.py` → `_distribute_across_vehicles()`

### Algorithm: Best-Fit Decreasing (BFD)

```
Input:  sorted_packages[], vehicle_sessions[]
Output: { placed, failed, unplaced, vehicle_map }

State:
  active_indices = []    // vehicles that already hold packages

For each package p in sorted_packages:
  best = { waste: ∞, score: -1, session: null, pos: null, vinfo: null }

  // Phase 1 — Try active vehicles (already in use)
  for each idx in active_indices:
    score, pos = _find_best_for_pkg(p, vehicle_sessions[idx])
    if pos is valid:
      waste = _estimate_remaining(p, pos, session)
      if waste < best.waste OR (waste ≈ best.waste AND score > best.score):
        update best

  // Phase 2 — Try unused vehicles (open one if needed)
  if best.pos is null:
    for each unused idx:
      score, pos = _find_best_for_pkg(p, vehicle_sessions[idx])
      if pos is valid:
        waste = _estimate_remaining(p, pos, session)
        if waste < best.waste OR (waste ≈ best.waste AND score > best.score):
          update best
          mark idx for activation

  // Phase 3 — Rear-door redirect
  if best.pos exists AND package touches rear wall (xmax ≥ container.length):
    try last vehicle unconditionally; use if it can accommodate

  // Commit
  if best.session found:
    place_package(p, best.pos)
    mark vehicle as active
```

### Waste Estimation

```python
def _estimate_remaining(pkg, pos, session):
    total_vol  = container.length × container.width × container.height
    total_floor = container.length × container.width
    total_payload = container.payload_kg

    rem_vol     = total_vol     − used_vol     − pkg.volume
    rem_floor   = total_floor   − used_floor   − (pkg.footprint if z=0 else 0)
    rem_payload = total_payload − used_weight  − pkg.weight

    return (rem_vol/total_vol + rem_floor/total_floor + rem_payload/total_payload) × 100
```

Three equal components: volume + floor + payload. Lower sum = tighter fit = better.

### Why BFD over FFD?

| Criteria | First-Fit Decreasing | Best-Fit Decreasing |
|----------|---------------------|---------------------|
| Search scope | First vehicle that fits | All active vehicles, pick tightest |
| Waste | Can leave fragmented space | Minimises remaining capacity |
| Computation | O(n) per package | O(m×n) per package (m = active vehicles) |
| Result density | Lower | Higher |

BFD is chosen because the vehicle count is small (typically <20), making the O(m×n) overhead negligible while packing density improves significantly.

### Phase 3 — Rear-Door Redirect

When the best-scoring position for a package places its rear edge at or beyond the container rear wall (`xmax ≥ container.length`), the algorithm checks whether the **last vehicle** in the fleet can accommodate it. If yes, the package is redirected unconditionally. This:

1. Fills the last vehicle (which typically has the most unused space)
2. Groups rear-wall packages together (they unload first)
3. Keeps front-loaded packages in earlier vehicles

---

## 3. Intra-Vehicle Placement (Single Vehicle)

Once a vehicle is selected, the `LargestFirstStrategy` places packages one at a time.

**Source**: `engine/auto_arrange.py` → `LargestFirstStrategy.arrange()`

### Algorithm

```
For each package p in sorted_packages:

  // Step 1 — Generate base candidate points
  candidates = {(0, 0, 0)}
  for each placed package pl:
    candidates.add(pl.right_corner + 2×clearance)
    candidates.add(pl.front_corner + 2×clearance)
    candidates.add(pl.top_corner + 2×clearance)

  // Step 2 — Add right-wall balance candidate
  right_y = container.width - p.width - clearance
  if right_y > clearance:
    candidates.insert(0, (0, right_y, 0))

  // Step 3 — Expand with rotations
  expanded = []
  for each (x,y,z) in candidates:
    expanded.add({x, y, z, rotation=0})
    if p.allow_rotation:
      expanded.add({x, y, z, rotation=90})

  // Step 4 — Rank by priority (fast pre-check)
  expanded.sort(by: _candidate_priority, descending)

  // Step 5 — Validate and score in priority order
  for each pos in expanded:
    result = validate(p, pos)
    if result.valid:
      score = evaluate(p, pos)
      if score > best.score:
        best = {score, pos}
        if score ≥ 99.99: break

  // Step 6 — Y-Slide fallback
  if best.pos is null:
    for each slide_pos in generate_slide_candidates(candidates, p, container):
      validate and score as above

  // Step 7 — Commit
  if best.pos found:
    place_package(p, best.pos)
  else:
    mark as unplaced
```

### Candidate Priority Ranking

**Source**: `routes.py` → `_candidate_priority()`

Before expensive validation, each candidate is scored on 5 lightweight factors (total 0–100):

| # | Factor | Range | Formula | Purpose |
|---|--------|-------|---------|---------|
| 1 | Touching Surfaces | 0–60 | `touches × 10` where touches counts walls: rear, left, right, floor | Rewards corner/edge placements that maximise stability |
| 2 | Z-Height | 0–15 | `(1 − z/height) × 15` | Floor placements are quicker to validate (no support check) and more stable |
| 3 | Wall-Contact Area | 0–15 | `contact_area / max_possible × 15` | Large contact area = better anchored |
| 4 | Back-to-Front | 0–20 | `(1 − x/length) × 20` | Enforces innermost-to-door loading; low X = deep in container |
| 5 | Front-Center Proximity | 0–10 | `(1 − dist/diagonal) × 10` where dist = sqrt(x² + (y−½W)² + z²) | Prefers origin-adjacent without Y bias (replaces old origin-proximity that pulled to y=0) |

Priority sorting ensures high-potential candidates are validated first, so the early-exit (score ≥ 99.99) triggers sooner — typically cutting validation calls by 50%+.

### Y-Slide Fallback

**Source**: `engine/candidate_points.py` → `generate_slide_candidates()`

When no extreme-point candidate validates, slide each base candidate left and right:

```
for each base (x, y, z) in candidates:
    for step in [100, 200, 300]:       // mm
        add (x, y + step, z, rot=0)    // slide right
        add (x, y - step, z, rot=0)    // slide left
        if allow_rotation:
            add (x, y + step, z, rot=90)
            add (x, y - step, z, rot=90)
```

This helps in tight packs where nominal extreme points are blocked but a slight Y offset clears the collision.

---

## 4. Scoring Strategy

**Source**: `engine/scorer.py` → `score_placement()`

### Weight Distribution (Total: 120, clamped to 100)

| Category | Weight | Behaviour | Why |
|----------|--------|-----------|-----|
| Floor Contact | 25 | Binary: 1 if z=0 | Floor placement is always most stable |
| Package Contact | 15 | Contact area ratio | Dense packing = better utilisation |
| Y Balance | 15 | Inverse of |y-COG − centre|/half-width | Even left-right weight distribution |
| Wall Contact | 10 | Wall count / 4 | Wall-anchored is stable |
| Face Contact | 10 | Face count / 6 | More touching faces = more stable |
| Vertical Stability | 10 | Inverse of mid-z/height | Lower COG = more stable |
| Z Preference | 10 | Inverse of zmin/height | Low packages leave room for stacking |
| Rear Proximity | 10 | Linear ramp near rear door | Avoid door; door packages belong in last vehicle |
| Compactness | 5 | Inverse of nearest distance | Grouped loads are denser |
| Stack Quality | 5 | Support ratio | Well-supported stacks are stable |
| X Preference | 5 | Inverse of xmin/length | Push deep into container |

### Y-Balance Algorithm

```python
total_weight = candidate.weight
weighted_y = candidate.cy × candidate.weight
for each existing package:
    weighted_y += existing.cy × existing.weight
    total_weight += existing.weight

center_y = weighted_y / total_weight
ideal = container.width / 2
dist = |center_y − ideal|
score = max(0, 1 − dist / ideal)      # [0, 1]
```

This is a **running balance** — each new package's contribution changes the total COG. A package placed on the heavy side will score lower than one on the light side, naturally pushing the load toward equilibrium.

---

## 5. Stacking Strategy

**Source**: `engine/support.py` → `check_support()`

### Combined-Support Model

```
For a candidate at z > 0:

1. Collect packages directly below (zmax match)
2. For each below package:
   - Must be stackable
   - Must be heavier than candidate
3. Compute union coverage:
   - Grid-sample candidate footprint (20×20)
   - Count samples inside any below AABB
   - Require coverage ≥ 90%
4. Centre-of-mass check:
   - Candidate XY centre must be inside at least one below AABB
```

### Why 90% threshold?

- 100% is unrealistic with integer coordinates and floating-point AABBs
- 90% allows small overhang while still ensuring the vast majority of the package is supported
- Can be overridden per-call via `support_threshold` parameter
- Grid sampling at 20×20 gives ~5% precision, safe above 90%

### Weight Rule

```
candidate.weight_kg ≤ every below_package.weight_kg
```

Prevents top-heavy stacks. The heaviest packages must be at the bottom.

---

## 6. Door Access Strategy

**Source**: `engine/access.py` → `check_door_access()`

### Access Priority

```
Try:  rear_door  →  side_door(right)  →  side_door(left)
Accept first clear path.
```

- **Rear door**: straight-in path along −X from rear wall. Package cross-section must fit door opening; sweep volume from position to rear must be clear.
- **Side door**: perpendicular entry from left or right wall. Package length × height must fit door; X-range must overlap door position; sweep from side must be clear.

### Why rear door first?

- Most vehicles load/unload from the rear
- Rear-door sweep enforces front-to-back loading order naturally (packages near the front are placed first while the rear path is clear)

### Default Door

When no door features are configured, the system creates a virtual full-width/full-height rear door:
```python
default = {"rear_door": {"width_mm": container.width, "height_mm": container.height}}
```
This ensures sweep validation always runs.

---

## 7. Clearance Strategy

**Source**: `engine/package.py`, `engine/geometry.py`, `engine/state.py`, `engine/validation.py`

### Purpose

10mm clearance bubble on every side of every package accounts for:
- Real-world measuring tolerances
- Load shift during transit
- Easy loading/unloading without binding

### Implementation per subsystem

| Subsystem | AABB Used | Behaviour |
|-----------|-----------|-----------|
| Spatial index (`state.py`) | Inflated (+clearance) | Extreme points offset by +2×clearance |
| Collision (`collision.py`) | Inflated | 20mm gap between packages (10mm × 2) |
| Boundary (`boundary.py`) | Actual | Packages can touch walls |
| Support (`support.py`) | Actual | Footprint area based on physical dimensions |
| Door access (`access.py`) | Inflated | Sweep volume accounts for safety bubble |

---

## 8. Full Pipeline Summary

```
Packages (unsorted)
    │
    ▼
Sort: stackable ASC → volume DESC → footprint DESC → weight DESC
    │
    ▼
For each package:
    │
    ├─► Generate extreme points (right/front/top corners + 2×clearance)
    │   Add right-wall balance candidate
    │   Expand with 0°/90° rotations
    │
    ├─► Rank by candidate priority (5 factors, 0–100)
    │
    ├─► Validate in priority order:
    │   1. Boundary (actual AABB)
    │   2. Door access (inflated AABB, rear → side)
    │   3. Collision (inflated AABB)
    │   4. Weight vs payload
    │   5. Support (actual AABB, combined-support model)
    │
    ├─► Score valid candidates (11 factors, clamped 0–100)
    │
    ├─► If found: place, continue
    │
    └─► If not found: Y-slide (100mm steps, ±3 per axis)
        → re-validate → if found: place
        → else: mark unplaced
    │
    ▼
Multi-vehicle:
    ▼
    For each vehicle that could fit the package:
        Waste = remaining_volume% + remaining_floor% + remaining_payload%
        Pick vehicle with lowest waste (tightest fit)
    │
    ├─► If position touches rear wall → redirect to last vehicle
    │
    ▼
Placement committed → load_sequence assigned
```

## 9. Configuration Points

| Parameter | Location | Default | Description |
|-----------|----------|---------|-------------|
| `SCORING_WEIGHTS` | `engine/scorer.py:8` | Various | Per-category importance for placement quality |
| `clearance_mm` | `engine/package.py:15` | 10.0 | Safety gap between packages (mm) |
| `support_threshold` | `engine/support.py:22` | 0.90 | Minimum fraction of footprint that must be covered by combined support |
| `_GRID_SAMPLES` | `engine/support.py:14` | 20 | Grid resolution for union coverage estimation |
| `_FACE_TOLERANCE` | `engine/scorer.py:20` | 1.0 | Tolerance for face-coincidence detection (mm) |
| Slide step | `engine/candidate_points.py` | 100mm | Y-slide increment |
| Max slide steps | `engine/candidate_points.py` | 3 | Max slides per direction |
| `REAR_DOOR_THRESHOLD` | `routes.py` (Phase 3) | 0mm | Only redirect when package touches rear wall |
| Waste multiplier | `routes.py` (Phase 3) | 1.0 | Rear-door redirect is unconditional (always takes last vehicle) |
