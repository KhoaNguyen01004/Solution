# Sorting Strategy & Algorithms — Truck Load Planner

## 1. Package Sort Order (Pre-Processing)

All packages are sorted by **non-stackable first, then descending width, then descending length, then descending volume, then descending weight** before any placement logic runs. The same sort is used in both single-vehicle and multi-vehicle paths.

**Source**: `engine/auto_arrange.py` → `LargestFirstStrategy`, `engine/distribution.py` → `distribute_across_vehicles()`

```python
sorted_packages = sorted(
    packages,
    key=lambda p: (
        0 if not p.stackable else 1,                        # non-stackable first
        -p.width_mm,                                        # width desc
        -p.length_mm,                                       # length desc
        -(p.length_mm * p.width_mm * p.height_mm),          # volume desc
        -p.weight_kg,                                       # weight desc
    ),
)
```

### Rationale

Non-stackable packages must go on the floor — placing them first ensures they get floor space before stackable packages consume it. After that, the widest packages come first so the X-slice filling heuristic can pack the full container width as early as possible, reducing blocking. Length, volume, and weight are secondary tie-breakers.

---

## 2. Vehicle Selection (Multi-Vehicle Distribution)

When no single `vehicle_id` is specified, packages are distributed via
`distribute_across_vehicles()` (`engine/distribution.py`), which delegates candidate
*ordering* to a pluggable `VehicleSelectionStrategy`
(`engine/vehicle_selection.py`). The default is **`SmallestVehicleThatFitsStrategy`**,
fixed in Phase 4 to actually minimize fleet size/cost:

```
Input:  packages[], vehicle_sessions[]
Output: { placed, failed, unplaced, vehicle_map }

1. Sort packages by width DESC, length DESC, volume DESC, weight DESC (non-stackable first)
2. Vehicle selection (SmallestVehicleThatFitsStrategy.select_vehicles):
     Sort vehicles by capacity (volume × payload) ASCENDING
     For each vehicle, smallest first:
       Cheap prefilter (_cheap_could_fit_all): total volume/weight vs. capacity,
         each package's footprint vs. cargo cross-section (with rotation) —
         reject obviously-infeasible vehicles with no arrangement attempt
       If it passes: probe with a single fast pass (strategy="largest_first"),
         not the 15-pass "optimized" strategy
       If everything placed: reset to empty, re-run "optimized" once on just
         this vehicle to refine the layout, use it alone, done
     If no single vehicle fits everything: fall back to DESCENDING (largest-
     first) order for the incremental multi-vehicle loop below — filling big
     vehicles first uses fewer trucks overall than filling small ones first
3. For each selected vehicle (in the order chosen above):
     Delegate to the same per-package placement pipeline the single-vehicle
     path uses (auto_arrange.py::_run_ordered_pass), not a separate
     hand-written copy — see Section 3
4. Return { placed, failed, unplaced, vehicle_map }
```

Notes/tradeoffs:
- The cheap prefilter is a *necessary, not sufficient* condition (it can't predict real
  packing efficiency/clearance losses), so some vehicles that pass it still fail the
  real single-vehicle probe. This means the single-vehicle-fits-all search costs more
  than a naive "always largest-first" approach when nothing fits alone — that cost buys
  the ability to use one smaller (cheaper) truck instead of a larger one when a shipment
  genuinely fits, which a pure largest-first approach can't discover.
- `LargestVehicleFirstStrategy` (`vehicle_selection.py`) is available as an explicit
  alternative (`StrategyRegistry.get("largest_first")`) for callers that want to skip
  the single-vehicle search entirely.

---

## 3. Intra-Vehicle Placement (Single Vehicle)

Once a vehicle is selected, a `StrategyRegistry`-registered strategy places packages
one at a time. The route default (`routes.py`) is **`optimized`**
(`OptimizedStrategy`), not `LargestFirstStrategy` — `LargestFirstStrategy` is a
simpler, faster single-pass strategy still registered and available, but not the
default entry point.

**Source**: `engine/auto_arrange.py` → `LargestFirstStrategy.arrange()` /
`OptimizedStrategy.arrange()`

### `LargestFirstStrategy` — single-pass algorithm

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

  // Step 3 — Score (see Section 4 for the real term list/weights) and pick best
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

No post-processing, no repair, no gap-filling, no compaction. The first valid placement
is the final one.

### `OptimizedStrategy` — the actual live default

Runs the `LargestFirstStrategy`-style pass repeatedly: **5 package orderings × 3
scoring-weight profiles = 15 full arrangement passes** per call
(`auto_arrange.py:272-328`), keeping whichever trial placed the most packages at the
best utilization/score, and early-exits the sweep only once a trial places every
package. This is the primary identified cause of "auto-arrange is slow" for realistic
package counts — the 15x multiplier itself is unchanged as of Phase 3 (see that phase's
CHANGELOG entry for why early-exit tuning was attempted-then-deferred rather than
shipped). Prior to the Phase 3 fix it also unconditionally discarded any caller-
configured `candidate_limit` on every trial; it now respects one when set.

---

## 4. Scoring Strategy

**Source**: `engine/scorer.py` → `score_placement()`, `SCORING_WEIGHTS`

Each candidate position gets a `raw_score × weight` per term, summed into `total`.
Terms are **not** on a consistent 0-1 scale — some (`contact_area`, `x_position`) are
ratios multiplied by a large weight; others (`usable_space`, `stack_level`,
`tower_height`) are already large raw numbers with weight `1`. This mixed convention is
a known readability wart, not a bug in itself.

### Terms & Weights (as of the Phase 1+2 fixes)

| Term | Weight | Raw range | Calculation | Why |
|------|--------|-----------|--------------|-----|
| `contact_area` | 1000 | 0–1 | Sum of coincident-face overlap areas ÷ max possible | Maximise contact density |
| `x_position` | 200 | 0–1 | Row/slice completion at the deepest X reached so far, within the candidate's own height band (`_score_x_position`) — higher = closes out the current row instead of skipping ahead into fresh depth | Reduces blocking behavior; replaces a pre-Phase-2 version that just measured `xmin / container.length` (a weak "prefer small X" bias with no completion signal) |
| `weight_balance` | 50 | 0–1 | `1 − \|y_cog − container.width/2\| / (container.width/2)` | Even weight distribution across width |
| `usable_space` | 3 | -500 to 500 | Gap-awareness: rewards positions that don't leave a dead strip too narrow for any remaining package (see `_score_usable_space`) | Boosted 3x in Phase 2 (was 1) — at weight 1 its -500 dead-strip penalty could be outweighed by a high `contact_area` score (max 1000), letting a placement with great contact still win despite leaving an unusable gap |
| `stack_level` | 1 | -500 to 200 | Floor=200, layer1=150, layer2=50, layer3+=-500 | Prefer floor, but not overwhelmingly — kept intentionally close between floor and layer1 so `contact_area`/`usable_space` can tip a genuinely-better stack into winning |
| `tower_height` | 1 | -800 to 100 | Based on the tallest stack anywhere in the candidate's XY neighbourhood (not just directly below) | Discourage building next to/on top of an already-tall tower |

`stack_level` and `tower_height`'s magnitudes were reduced from an earlier version
(floor=1000/500 vs. layer1=300/300 — a ~900-point gap that made the algorithm prefer an
empty floor tile over stacking essentially unconditionally, regardless of whether
stacking was actually more space-efficient). See `engine/support.py` for the
complementary **hard** stacking-height cap (`_SYSTEM_MAX_STACK_LAYERS`), which — unlike
`tower_height` — is a validity constraint, not just a scoring preference.

`OptimizedStrategy`'s `dense`/`stack_friendly` weight-profile trials
(`auto_arrange.py::_weight_profiles`) override `usable_space` to `2.0`/`2.5` and
`x_position` to `350.0`/`300.0` — these are **independently pre-tuned absolute values**,
not multipliers relative to the base weights above; don't scale them proportionally if
the base weights change again (this was tried during Phase 2 and caused a measurable
regression in aggregate placement rate before being reverted).

---

## 5. Stacking Strategy

**Source**: `engine/support.py` → `check_support()`

### Combined-Support Model (Capacity-Based)

```
For a candidate at z > 0:

1. Collect packages directly below (zmax match)
2. Hard column-depth cap: how many packages deep is the tallest column
   among the below packages? If placing the candidate would reach
   _SYSTEM_MAX_STACK_LAYERS (3) packages in that single-file column →
   reject, regardless of any per-package max_stack_layers setting
   (_tower_depth() in engine/support.py)
3. For each below package:
   - Check stacking mode: NONE → reject, LIGHT_ONLY → enforce max_top_weight_kg
   - Must not exceed max_stack_layers already stacked directly on IT
     specifically (XY-overlap-scoped, not just any placement sharing its
     height) — if the package's own `max_stack_layers` is 0 ("no explicit
     per-package limit," the DB/UI default), the same system-wide
     `_SYSTEM_MAX_STACK_LAYERS` applies as a breadth fallback (how many
     separate packages can share this one base's top surface)
   - Must be heavier than candidate
4. The candidate itself must be stackable (stacking_mode ≠ NONE)
5. Footprint area: candidate ≤ every below package's footprint
6. Compute union coverage: grid-sample (20×20), require ≥ 50%
7. Centre-of-mass: XY centre inside at least one below AABB
```

Step 2 (depth) and step 3's `max_stack_layers` check (breadth) are genuinely
different constraints — a linear single-file column never has more than one
package directly on any given package, so the breadth check alone can't limit
how many layers deep a tower goes (this was the actual state of the code
immediately after the Phase 1 pass; confirmed by testing a tall single-column
scenario, which towered until it hit the container's physical height boundary
instead of the intended stacking cap). Both gaps — the missing depth cap, and
`_count_above`'s breadth check not being scoped to XY overlap with the
specific base package (so it could reject a stack based on an unrelated
package merely sharing its height elsewhere in the container) — were found
and fixed while writing Phase 5's regression tests, since a real end-to-end
test finally exercised this path under conditions where `max_stack_layers`
isn't explicitly set (the common case).

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
Sort: non-stackable first, width DESC, length DESC, volume DESC, weight DESC
    ▼
Multi-vehicle: SmallestVehicleThatFitsStrategy (see Section 2 — under revision)
    ▼
For each selected vehicle:
    └─► For each remaining package:
            ├─► Generate candidates (origin + box corners + rotations)
            ├─► Score (6 terms: contact_area, x_position, weight_balance,
            │         usable_space, stack_level, tower_height — Section 4)
            ├─► Validate (boundary, weight, collision, support, door)
            └─► Place if valid, else unplaced → next vehicle
    ▼
Done — no post-processing passes
```

---

## 9. Configuration Points

| Parameter | Location | Default | Description |
|-----------|----------|---------|-------------|
| `SCORING_WEIGHTS` | `engine/scorer.py` | `{contact_area:1000, x_position:200, weight_balance:50, usable_space:3, stack_level:1, tower_height:1}` | 6-term scoring, see Section 4 |
| `_SYSTEM_MAX_STACK_LAYERS` | `engine/support.py` | 3 | Hard cap applied when a package's own `max_stack_layers` is 0 |
| `horizontal_clearance_mm` | `engine/package.py` | 10.0 | Safety gap (mm) |
| `vertical_clearance_mm` | `engine/package.py` | 0.0 | Vertical safety gap (mm) |
| `max_top_weight_kg` | `engine/package.py` | 0.0 | Max weight above (0=unlimited) |
| `max_stack_layers` | `engine/package.py` | 0 | Per-package stack-layer override (0 = no override, falls back to `_SYSTEM_MAX_STACK_LAYERS`) |
| `support_threshold` | `engine/support.py` | 0.50 | Min footprint fraction for support |
| `_GRID_SAMPLES` | `engine/support.py` | 20 | Grid resolution |
| `candidate_limit` | `engine/profile.py` (`PlannerProfile`) | `None` (balanced) / 15 (fast) | Max candidates. As of the Phase 3 fix, `OptimizedStrategy` now respects a caller-configured limit instead of discarding it every trial — only matters when `profile=fast` is explicitly requested alongside `strategy=optimized`, since `balanced` (the default) never sets a limit to begin with |
| `tighten_step_mm` | `engine/profile.py` (`PlannerProfile`) | 200.0 | Defined but **dead** — `tighten_position()` (`candidate_points.py:70`) hardcodes its own step (`max(50.0, h_clr*2)`) and never reads this value |
