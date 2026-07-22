# Truck Load Planner: Gap Placement Solution

## Problem

**KBF 280R** placed flush at x≈0, spanning full container width. Subsequent **LC 900-4/6TXA** units landed at x≈3.2–3.5m instead of flush against KBF 280R's right edge (x≈1.05m). Pure greedy placement cannot correct gaps — once a package lands in the wrong spot, later extreme points derive from *its* corners.

## Solution

Three-layer defense:

### 1. Frontier-Based Gap Penalty (During Greedy Pass)

`FrontierTracker` (`engine/frontier.py`) maintains a 1D Y-strip frontier — for each ~200–250 mm Y strip, tracks the max X of the packed front. During scoring, candidates receive:

```
penalty = −min(gap_distance × (0.5 + gap_ratio × 0.5), 500)
gap_distance = frontier(Y) − candidate.x
```

This strongly penalizes positions that leave a gap behind the frontier, preventing the misplacement at source.

### 2. `fill_frontier_gaps` (Post-Processing Pass)

After the greedy pass, scans all placed packages, detects any behind the frontier, and resettles them:

- Uses `settle_package()` (analytical O(K)) — pushes gapped packages flush to frontier + clearance
- Falls back to `tighten_position()` only when settle gives no improvement
- Guard: `tx >= pl.x - 1.0` — only re-places on ≥1 mm forward improvement
- Updates frontier immediately after each re-placement

### 3. Compaction Safety Net

Existing compaction in the pipeline handles any remaining small adjustments.

## Result

LC 900 placed at x≈1070 mm — flush against KBF 280R with the minimum physically achievable gap (20 mm = 2×10 mm horizontal clearance). All 46 packages placed successfully in the `real` scenario.

## Debugging

`scripts/debug_arrange.py` provides comprehensive per-package logs including frontier state, all candidate evaluations with full breakdown, gap analysis, settle/tighten tests, and compaction steps. Run with `--full` for per-strip frontier details.