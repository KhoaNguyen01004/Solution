# Sorting Strategy & Algorithms — Truck Load Planner

## 1. Package Sort Order (Pre-Processing)

All packages are sorted by **descending volume, then descending weight, then descending footprint area** before any placement logic runs. The same sort is used in both single-vehicle and multi-vehicle paths.

**Source**: `engine/auto_arrange.py:48`, `engine/distribution.py:192`

```python
sorted_packages = sorted(
    packages,
    key=lambda p: (
        -(p.length_mm * p.width_mm * p.height_mm),  # volume desc
        -p.weight_kg,                                   # weight desc
        -(p.length_mm * p.width_mm),                    # footprint area desc
    ),
)
```

### Rationale

Largest and heaviest packages are the hardest to fit — placing them first maximises the chance they find a spot. Weight is included as a secondary key so that equally-sized heavy packages are prioritised over light ones (heavier packages must go on the bottom of stacks). This is a standard greedy bin-packing heuristic. Stackability is enforced at validation time (see §6), not during sorting.

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

  // Step 3 — Add floor anchor candidates
  anchors = generate_floor_anchors(placed_packages, container)
  candidates.extend(anchors)

  // Step 4 — Expand with rotations
  expanded = []
  for each (x,y,z) in candidates:
    expanded.add({x, y, z, rotation=0})
    if p.allow_rotation:
      expanded.add({x, y, z, rotation=90})

  // Step 5 — Score all, tighten top 5, re-score
  for each pos in expanded:
    score = evaluate(p, pos)
  sort expanded by score DESC
  top5 = expanded[0:5]
  tightened = [tighten_position(pos, placed_packages, container) for pos in top5]
  for each pos in tightened:
    score = evaluate(p, pos)  // re-score after tightening

  // Step 6 — Validate and pick best
  for each pos in (tightened ∪ expanded):
    result = validate(p, pos)
    if result.valid:
      score = evaluate(p, pos)
      if score > best.score:
        best = {score, pos}
        if score ≥ 99.99: break

  // Step 7 — Y-Slide fallback
  if best.pos is null:
    for each slide_pos in generate_slide_candidates(candidates, p, container):
      validate and score as above

  // Step 8 — Commit
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
| 1 | Touching Surfaces | 0–60 | `touches × 10` where touches counts container faces: front(x=0), rear(x=len), left(y=0), right(y=wid), floor(z=0), ceiling(z=h) | Rewards corner/edge placements that maximise stability |
| 2 | Z-Height | 0–15 | `(1 − z/height) × 15` | Floor placements are quicker to validate (no support check) and more stable |
| 3 | Wall-Contact Area | 0–15 | `contact_area / max_possible × 15` | Large contact area = better anchored |
| 4 | Back-to-Front | 0–20 | `(1 − x/length) × 20` | Enforces innermost-to-door loading; low X = deep in container |
| 5 | Front-Center Proximity | 0–10 | `(1 − dist/diagonal) × 10` where dist = sqrt(x² + (y−½W)² + z²) | Prefers origin-adjacent without Y bias (replaces old origin-proximity that pulled to y=0) |

Priority sorting ensures high-potential candidates are validated first, so the early-exit (score ≥ 99.99) triggers sooner — typically cutting validation calls by 50%+.

### Y-Slide Fallback

**Source**: `engine/candidate_points.py` → `generate_slide_candidates()`

When no extreme-point candidate validates, slide each base candidate in X, Y, and Z:

```
step = max(50, horizontal_clearance_mm)
for each base (x, y, z) in candidates:
    for i in [1, 2, 3]:                         // up to 3 steps per direction
        add (x, y + i*step, z, rot=0)           // slide right
        add (x, y - i*step, z, rot=0)           // slide left
        add (x + i*step, y, z, rot=0)           // slide forward
        add (x - i*step, y, z, rot=0)           // slide rearward
        add (x, y, z + i*step, rot=0)           // slide up
        if allow_rotation:
            ... (same slides with rot=90)
        // Combined X+Y slides for diagonal nudging
```

This helps in tight packs where nominal extreme points are blocked but a slight offset in any axis clears the collision. Step size is `max(50mm, horizontal_clearance_mm)`.

### Tighten Position (Push Deep + Rotate)

**Source**: `engine/candidate_points.py` → `tighten_position()`

After a valid position is found, `tighten_position` settles the package into the tightest possible spot by pushing toward the front wall (-X). When blocked, it tries progressively more expensive evasion strategies:

1. **Alternate rotation** (0° ↔ 90°) — if rotation is allowed, swap and continue -X push.
2. **Y sweep** — scan Y offsets (left/right) at current and alternate rotation to find a clear -X path.
3. **Z lift** — try raising/lowering the package combined with Y sweep and both rotations.
4. **Settle** — finally push against the left wall (-Y) and floor (-Z).

This mirrors how a real loader would nudge, rotate, and shift a package into the tightest available spot.

---

## 4. Frontier-Based Gap Prevention

**Source**: `engine/frontier.py` → `FrontierTracker`

During the greedy scoring pass, a **frontier gap penalty** prevents placement behind the current packed front.

### FrontierTracker

Maintains a 1D Y-strip frontier. For each Y strip (default `strip_width_mm` = 200–250 mm), records the maximum X (depth) of the packed front.

```python
get_frontier_at(y)       → max X at this Y-strip
gap_distance(x, y, z, w) → frontier − x   (negative = in a gap)
gap_ratio(...)            → gap_distance / container.length
```

### Gap Penalty Formula

```
gap_distance = frontier(Y) − candidate.x
gap_ratio = gap_distance / container.length
penalty = −min(gap_distance × (0.5 + gap_ratio × 0.5), 500)
adjusted_score = raw_score + penalty   # penalty ≤ 0
```

- Capped at −500 to avoid dominating scoring
- Applied in `LargestFirstStrategy.arrange()` during candidate evaluation
- The `0.5 + gap_ratio × 0.5` weighting makes the penalty grow with both absolute distance and relative depth

### Frontier Update

After each placement, `FrontierTracker.update_from_placement()` records the package's right edge X at every Y-strip it spans. The frontier for a strip is the **maximum** X among all packages in that strip.

### Gap-Filling Post-Processing

**Source**: `engine/distribution.py` → `fill_frontier_gaps()`

After the initial greedy sweep, closes any remaining frontier gaps:

1. Scan all placed packages sorted by X
2. If `package.xmin > frontier[Y_strip]` → gapped
3. Try `settle_package()` (analytical O(K))
4. If settle gives no improvement → fall back to `tighten_position()`
5. Re-place only on `tx >= pl.x - 1.0` (≥1 mm forward gain)
6. Update frontier immediately

This closes the persistent gap bug (LC900 at x≈3.5m → x≈1.07m). The 20 mm remaining gap is the minimum physically achievable (2× clearance_mm).

---

## 5. Scoring Strategy

**Source**: `engine/scorer.py` → `score_placement()`

### Weight Distribution (Total: 461, clamped to `MAX_POSSIBLE_SCORE = 200.0`)

| Category | Weight | Behaviour | Why |
|----------|--------|-----------|-----|
| Rear Proximity | 200 | Linear ramp near rear door | Avoid door; door packages belong in last vehicle |
| X Preference | 120 | Inverse of xmin/length | Push deep into container |
| Z Preference | 50 | Inverse of zmin/height | Low packages leave room for stacking |
| Floor Contact | 40 | Binary: 1 if z=0 | Floor placement is stable |
| Compactness | 15 | Inverse of nearest distance | Grouped loads are denser |
| Package Contact | 8 | Contact area ratio | Dense packing = better utilisation |
| Vertical Stability | 5 | Inverse of mid-z/height | Lower COG = more stable |
| Cluster Cohesion | 10 | Near centroid of all placed packages | Keep load tightly clustered; small+deep+compact bonus |
| Y Balance | 3 | Inverse of |y-COG − centre|/half-width | Even left-right weight distribution |
| Wall Contact | 2 | Wall count / 4 | Wall-anchored is stable |
| Face Contact | 2 | Face count / 6 | More touching faces = more stable |
| Dead Space Quality | 3 | Future-packability gap estimation | Preserve usable space for hardest remaining packages |
| Load Profile Stability | 3 | 1 − max_step/container.height | Penalise tall isolated stacks; reward flat cargo surfaces |
| Stack Quality | 0 | Support ratio | Disabled (currently unused) |

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

### Combined-Support Model (Capacity-Based)

```
For a candidate at z > 0:

1. Collect packages directly below (zmax match)
2. For each below package:
   - Check stacking mode: NONE → reject, LIGHT_ONLY → enforce max_top_weight_kg
   - Must be heavier than candidate
   - Must not exceed max_stack_layers already stacked on it
3. The candidate package itself must be stackable (stacking_mode ≠ NONE)
   — unstackable packages cannot sit on top of other packages
4. Footprint area: candidate footprint ≤ every below package's footprint
5. Compute union coverage:
   - Grid-sample candidate footprint (20×20)
   - Count samples inside any below AABB
   - Require coverage ≥ 50%
6. Centre-of-mass check:
   - Candidate XY centre must be inside at least one below AABB
```

### Stacking Modes

| Mode | Meaning |
|------|---------|
| `NONE` | Nothing allowed above this package |
| `LIGHT_ONLY` | Only packages ≤ `max_top_weight_kg` may stack on top |
| `NORMAL` | Stacking allowed subject to all other rules |

A package with `stackable=False` auto-derives `stacking_mode=NONE` via `Package.__post_init__()`, which blocks both directions. Setting `max_top_weight_kg > 0` sets `LIGHT_ONLY`.

### Stacking Rules Enforced

| Rule | Direction | Enforced In |
|------|-----------|-------------|
| Unstackable package on floor | ✅ Allowed | z=0 short-circuit |
| Unstackable package on top of another | ❌ Rejected | `_check_stacking_rules()` — top package check |
| Another package on top of unstackable | ❌ Rejected | `_check_stacking_rules()` — base package check |

### Why 50% threshold?

- The combined-support model uses union coverage with 50% threshold, down from 90%, to better accommodate packages with irregular below-support patterns
- Can be overridden per-call via `support_threshold` parameter
- Grid sampling at 20×20 gives ~5% precision

### Weight Rule

```
candidate.weight_kg ≤ every below_package.weight_kg
```

Prevents top-heavy stacks. The heaviest packages must be at the bottom.

### Footprint Area Rule

```
candidate.length_mm × candidate.width_mm ≤ every below_package.length_mm × below_package.width_mm
```

Prevents packages with a larger footprint from being stacked on smaller bases. The largest-area packages must be at the bottom.

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

### Door-Used Propagation

The `door_used` value from `check_door_sweep()` (`"rear"`, `"side_right"`, or `"side_left"`) is stored in the `Placement` dataclass and sent to the frontend as `door_used`. The 3D animation uses this field to choose the correct entry point:

- `"rear"` → start outside rear wall: `(d.len + pl, y, z)`
- `"side_right"` → start outside right wall: `(x, y, d.wid + pw)`
- `"side_left"` → start outside left wall: `(x, y, -pw)`

**Source**: `engine/placement.py:14`, `engine/validation.py:153`, `static/js/truck-load-planner.js:3128`

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
Sort: volume DESC (biggest first)
    │
    ▼
Multi-vehicle:
    Sort vehicles by combined capacity (volume × payload) DESC
    │
    ▼
For each vehicle (biggest → smallest):
    │
    └─► For each remaining package (biggest → smallest):
            │
            ├─► Generate candidate points:
            │   • Extreme points (right/front/top corners + 2×clearance)
            │   • Right-wall balance candidate
            │   • Floor anchors (largest empty floor rectangles, top 2 regions)
            │   • Expand with 0°/90° rotations
            │
            ├─► Score all candidates (13 factors, clamped 0–100)
            │   • Apply frontier gap penalty
            │   • Apply stack ceiling penalty
            │
            ├─► Tighten top 5 (snap to nearest extreme point), re-score
            │
            ├─► Validate in priority order:
            │   1. Boundary (actual AABB)
            │   2. Weight vs payload
            │   3. Door fit (inflated AABB, rear → side)
            │   4. Collision (inflated AABB)
            │   5. Support (actual AABB, combined-support model)
            │   6. Door sweep (inflated AABB)
            │
            ├─► If best position is a stack and n_floor ≤ 10:
            │   Try local rearrangement (remove ≤3 blockers, place on floor,
            │   re-place blockers, accept if floor score > stack score)
            │
            ├─► If found: place_package() → door_used stored → update frontier
            │
            └─► If not found: Y-slide (100mm steps, ±3 per axis)
                → re-validate → if found: place
                → else: keep for next vehicle
    │
    ▼
Post-processing (after all packages placed):
    fill_frontier_gaps()
    → For each gapped package (behind frontier):
        → settle_package() → if no improvement: tighten_position()
        → re-place only if ≥1mm forward gain
        → update frontier
    │
    ▼
Placement committed → load_sequence assigned
    │
    ▼
    If remaining packages exist → next (smaller) vehicle
    Else → done
    │
    ▼
Optional: Repair optimizer (destroy-and-repair LNS, max N passes)
    → redistribute unplaced packages across all vehicles
    → runs distribution repeatedly with different destroy indices
    │
    ▼
Optional: Consolidation pass (near-empty vehicle elimination)
```

## 9. Configuration Points

| Parameter | Location | Default | Description |
|-----------|----------|---------|-------------|
| `SCORING_WEIGHTS` | `engine/scorer.py:8` | Various | Per-category importance for placement quality (total 461, clamped to `MAX_POSSIBLE_SCORE = 200.0`) |
| `MAX_POSSIBLE_SCORE` | `engine/auto_arrange.py:12` | 200.0 | Maximum total score after weight application and clamping |
| `NUM_PROFILE_SLICES` | `engine/scorer.py:24` | 10 | Number of longitudinal slices for load profile stability calculation |
| `horizontal_clearance_mm` | `engine/package.py:27` | 10.0 | Horizontal safety gap between packages (mm) |
| `vertical_clearance_mm` | `engine/package.py:28` | 0.0 | Vertical safety gap for stacked packages (mm) |
| `max_top_weight_kg` | `engine/package.py:29` | 0.0 | Max weight allowed above this package (0 = unlimited); sets `LIGHT_ONLY` mode |
| `max_stack_layers` | `engine/package.py:30` | 0 | Max packages stacked on top of this one (0 = unlimited) |
| `support_threshold` | `engine/support.py:22` | 0.50 | Minimum fraction of footprint that must be covered by combined support |
| `_GRID_SAMPLES` | `engine/support.py:14` | 20 | Grid resolution for union coverage estimation |
| `_FACE_TOLERANCE` | `engine/scorer.py:20` | 1.0 | Tolerance for face-coincidence detection (mm) |
| `DEAD_SPACE_WEIGHT` | `engine/dead_space.py` | 10 | Internal weight for dead-space quality algorithm (score * this ÷ sum); scoring weight in `SCORING_WEIGHTS` is 3 |
| `MIN_GAP_MM` | `engine/dead_space.py` | 10.0 | Gaps ≤ this value are considered flush and skipped |
| `REFERENCE_SET_SIZE` | `engine/dead_space.py` | 3 | Number of hardest remaining packages in reference set |
| Slide step | `engine/candidate_points.py` | max(50, h_clr) mm | Multi-axis slide increment (X, Y, Z) |
| Max slide steps | `engine/candidate_points.py` | 3 | Max slides per direction |
| Max rearrangement remove | `engine/distribution.py` | 3 | Max blocking floor packages removed during local rearrangement |
| Rearrangement floor guard | `engine/distribution.py` | 10 | Only attempt rearrangement when floor packages ≤ this threshold |
 | `REAR_DOOR_THRESHOLD` | `routes.py` (Phase 3) | 0mm | Only redirect when package touches rear wall |
| Waste multiplier | `routes.py` (Phase 3) | 1.0 | Rear-door redirect is unconditional (always takes last vehicle) |
| `strip_width_mm` | `engine/frontier.py` | 200–250mm | Y-strip width for frontier tracking |
| `_COLUMN_GRID_MM` | `engine/auto_arrange.py:17` | 500 | Grid cell size (mm) for column-height tracking |
| `MAX_STACK_HEIGHT_MM` | `engine/auto_arrange.py:21` | 1800 | Hard ceiling: prefer floor over stacking above this height |
| Gap penalty cap | `engine/auto_arrange.py` | 500 | Max frontier gap penalty magnitude |
| Gap penalty formula | `engine/auto_arrange.py` | `gap × (0.5 + gap_ratio × 0.5)` | Weighting of gap distance vs relative depth |
| Gap-fill improvement threshold | `engine/distribution.py` | 1.0mm | Min forward movement to accept re-placement |
