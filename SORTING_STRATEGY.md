# Sorting Strategy & Algorithms — Truck Load Planner

## 1. Package Sort Order (Pre-Processing)

All packages are sorted by **non-stackable first, then descending volume, then descending weight, then descending footprint area** before any placement logic runs. The same sort is used in both single-vehicle and multi-vehicle paths.

**Source**: `engine/auto_arrange.py` → `LargestFirstStrategy`, `engine/distribution.py` → `distribute_across_vehicles()`

```python
sorted_packages = sorted(
    packages,
    key=lambda p: (
        p.stackable,                                        # non-stackable (False = 0) first
        -(p.length_mm * p.width_mm * p.height_mm),          # volume desc
        -p.weight_kg,                                       # weight desc
        -(p.length_mm * p.width_mm),                        # footprint desc
    ),
)
```

### Rationale

Non-stackable packages must go on the floor — placing them first ensures they get floor space before stackable packages consume it. After that, largest and heaviest packages are the hardest to fit, so placing them first maximises the chance they find a spot. This is a standard greedy bin-packing heuristic.

---

## 2. Vehicle Selection (Multi-Vehicle Distribution)

When no single `vehicle_id` is specified, packages are distributed across all available vehicles using **Largest-Vehicle-First**.

**Source**: `engine/distribution.py:176` → `distribute_across_vehicles()`

### Algorithm: Largest-Vehicle-First

```
Input:  packages[], vehicle_sessions[]
Output: { placed, failed, unplaced, vehicle_map }

1. Sort packages by volume DESC (biggest first)
2. Sort vehicles by combined capacity (volume × payload) DESC
3. For each vehicle (biggest → smallest):
     For each remaining package (biggest → smallest):
       Find best position via find_best_for_pkg()
       If position found: place_package()
       If not: keep for next vehicle
4. Return { placed, failed, unplaced, vehicle_map }
```

Key difference from BFD: instead of picking the tightest-fit vehicle per-package, the algorithm exhausts the largest vehicle's capacity first, then moves to smaller ones with leftovers. This ensures:
- Largest vehicles take the most packages
- Small vehicles only receive what big ones cannot fit
- No waste estimation or per-package cross-vehicle comparison needed

---

## 3. Intra-Vehicle Placement (Single Vehicle)

Once a vehicle is selected, the `LargestFirstStrategy` places packages one at a time.

**Source**: `engine/auto_arrange.py` → `LargestFirstStrategy.arrange()`

### Algorithm

```
For each package p in sorted_packages:

  // Step 1 — Generate candidate points
  candidates = {(0, 0, 0)}
  for each placed package pl:
    candidates.add((pl.x + pl.length + 2×clearance, pl.y, pl.z))  // right face
    candidates.add((pl.x, pl.y + pl.width + 2×clearance, pl.z))   // front face
    candidates.add((pl.x, pl.y, pl.z + pl.height))                // top face

  // Step 2 — Expand with rotations
  expanded = []
  for each (x,y,z) in candidates:
    expanded.add({x, y, z, rotation=0})
    if p.allow_rotation:
      expanded.add({x, y, z, rotation=90})

  // Step 3 — Score and pick best
  best = null
  for each pos in expanded:
    if validate(p, pos) is valid:
      score = evaluate(p, pos)
      if score > best.score:
        best = {score, pos}

  // Step 4 — Commit
  if best found: place_package(p, best.pos)
  else: mark as unplaced
```

No post-processing, no repair, no gap-filling, no compaction. The first valid placement is the final one.

---

## 4. Scoring Strategy

**Source**: `engine/scorer.py` → `score_placement()`

### Weight Distribution (4 terms, unclamped)

| Category | Weight | Calculation | Why |
|----------|--------|-------------|-----|
| Package Contact | 1000 | Sum of coincident-face overlap areas (mm²) across all neighbors | Maximise contact density |
| X Preference | 200 | `max(0, container.length − xmin)` | Push deep into container |
| Floor Contact | 100 | `container.width × container.length` if z=0, else 0 | Prefer floor for stability |
| Y Balance | 50 | Y-COG proximity to container.width/2 | Even weight distribution |

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

---

## 5. Stacking Strategy

**Source**: `engine/support.py` → `check_support()`

### Combined-Support Model (Capacity-Based)

```
For a candidate at z > 0:

1. Collect packages directly below (zmax match)
2. For each below package:
   - Check stacking mode: NONE → reject, LIGHT_ONLY → enforce max_top_weight_kg
   - Must be heavier than candidate
   - Must not exceed max_stack_layers already stacked on it
3. The candidate itself must be stackable (stacking_mode ≠ NONE)
4. Footprint area: candidate ≤ every below package's footprint
5. Compute union coverage: grid-sample (20×20), require ≥ 50%
6. Centre-of-mass: XY centre inside at least one below AABB
```

### Stacking Modes

| Mode | Meaning |
|------|---------|
| `NONE` | Nothing allowed above |
| `LIGHT_ONLY` | Only packages ≤ `max_top_weight_kg` |
| `NORMAL` | Stacking allowed subject to all rules |

`stackable=False` auto-derives `stacking_mode=NONE`.

---

## 6. Door Access Strategy

**Source**: `engine/access.py` → `check_door_access()`

```
Try:  rear_door  →  side_door(right)  →  side_door(left)
```

- **Rear door**: cross-section fits opening, sweep from position to rear clear
- **Side door**: cross-section fits opening, X-range overlaps door, sweep clear
- Default: full-width/full-height rear door when no features configured

The `door_used` value is stored in `Placement` and used by the 3D animation for entry point selection.

---

## 7. Clearance Strategy

10mm clearance bubble on every side of every package. Implementation per subsystem:

| Subsystem | AABB Used | Behaviour |
|-----------|-----------|-----------|
| Spatial index | Inflated (+clearance) | Extreme points offset by +2×clearance |
| Collision | Inflated | 20mm gap between packages |
| Boundary | Actual | Packages can touch walls |
| Support | Actual | Physical footprint |
| Door access | Inflated | Sweep with safety bubble |

---

## 8. Full Pipeline Summary

```
Packages (unsorted)
    ▼
Sort: non-stackable first, volume DESC, weight DESC, footprint DESC
    ▼
Multi-vehicle: sort vehicles by capacity DESC
    ▼
For each vehicle (biggest → smallest):
    └─► For each remaining package:
            ├─► Generate candidates (origin + box corners + rotations)
            ├─► Score (4 terms: contact, x, floor, balance)
            ├─► Validate (boundary, weight, collision, support, door)
            └─► Place if valid, else unplaced → next vehicle
    ▼
Done — no post-processing passes
```

---

## 9. Configuration Points

| Parameter | Location | Default | Description |
|-----------|----------|---------|-------------|
| `SCORING_WEIGHTS` | `engine/scorer.py` | `{package_contact:1000, x_preference:200, floor_contact:100, y_balance:50}` | 4-term scoring |
| `horizontal_clearance_mm` | `engine/package.py` | 10.0 | Safety gap (mm) |
| `vertical_clearance_mm` | `engine/package.py` | 0.0 | Vertical safety gap (mm) |
| `max_top_weight_kg` | `engine/package.py` | 0.0 | Max weight above (0=unlimited) |
| `max_stack_layers` | `engine/package.py` | 0 | Max stacks on top (0=unlimited) |
| `support_threshold` | `engine/support.py` | 0.50 | Min footprint fraction for support |
| `_GRID_SAMPLES` | `engine/support.py` | 20 | Grid resolution |
| `candidate_limit` | `engine/profile.py` | 80 | Max candidates |
| `tighten_step_mm` | `engine/profile.py` | 5.0 | Tighten step |
