# Truck Load Planner — Sorting Algorithm Improvement Roadmap

## Goal

The current Truck Load Planner has reached a mature heuristic architecture:

- Persistent Extreme Points
- Spatial Grid
- Best-Fit Decreasing vehicle selection
- Candidate Priority
- Progressive Validation
- Combined Support stacking
- Door sweep validation
- Clearance-aware planning
- Dead Space Quality estimation

The objective of this phase is **NOT** to redesign the planner.

Instead, improve packing quality while preserving the current architecture and deterministic behavior.

The planner should continue to produce the same style of layouts, but make smarter placement decisions.

---

# ✅ Priority 1 — Dead Space Quality (Completed)

**Implementation**: `engine/dead_space.py` — `compute_dead_space_quality()`

Integrated as a normal scoring category (`dead_space_quality: 10` in `SCORING_WEIGHTS`). The heuristic estimates future packability by measuring gap distances from each face to the nearest obstacle, then comparing those gaps against the hardest remaining packages using continuous dimension-ratio scoring. See `engine/dead_space.py` and `SYSTEM.md` for details.

---

# Priority 2 — One-Step Look-Ahead

## Problem

The current scoring rewards:

- wall contact
- face contact
- compactness
- stability

However, it does not directly penalize creating unusable cavities.

Example:

GOOD

████████
████████

BAD

████████
██    ██

Both may receive similar scores even though the second creates unusable space.

---

## Requirement

Introduce a lightweight dead-space estimation.

For every candidate placement:

Estimate the enclosed empty volume immediately surrounding the package.

Examples of undesirable situations:

- narrow vertical shafts
- enclosed pockets
- isolated cavities
- long thin unusable channels

Subtract a configurable penalty from the placement score.

Do NOT perform flood-fill or expensive volume searches.

The estimate should remain O(number_of_neighbors).

---

## Success Criteria

Layouts should naturally avoid creating trapped spaces.

Packing density should improve without noticeable runtime increase.

---

# Priority 2 — One-Step Look-Ahead

## Problem

The planner is still completely greedy.

Current flow:

Package A
↓

Best placement
↓

Commit

Sometimes another placement for Package A would allow Package B to fit.

---

## Requirement

When evaluating the best few placements for the current package:

Temporarily simulate placing the next package.

Example:

Candidate 1
↓

Can next package fit?
↓

Score = current + future

Candidate 2
↓

Can next package fit?
↓

Score = current + future

Choose the better combined result.

---

## Constraints

Maximum depth:

1 package

Maximum candidates examined:

3–5

No recursive search.

No backtracking tree.

This should remain lightweight.

---

## Success Criteria

Slightly worse placements should occasionally be selected if they enable the following package to fit.

---

# Priority 3 — Local Repair Pass

## Problem

Once a package is committed it is never reconsidered.

A single early greedy choice may reduce overall utilization.

---

## Requirement

After auto-arrange completes:

Run a lightweight optimization pass.

Possible operations:

- relocate one package
- swap two packages
- re-place the last N packages

Only keep changes that improve:

- utilization
- compactness
- score
- successful placements

---

## Constraints

No full replanning.

Maximum runtime increase:

<20%

Planner must remain deterministic.

---

## Success Criteria

Recover obvious greedy mistakes.

Improve final utilization by a small percentage.

---

# Priority 4 — Dynamic Scoring Weights

## Problem

Current scoring weights remain constant regardless of container fill level.

Early loading and late loading have different priorities.

---

## Requirement

Adjust scoring weights according to container utilization.

Example:

Early stage:

- stability
- floor contact
- wall contact

Middle stage:

- balance
- compactness

Late stage:

- dead-space reduction
- gap filling

Weight transitions should be smooth.

Do not abruptly switch profiles.

---

## Success Criteria

Late-stage placements should naturally fill remaining gaps instead of maximizing wall contact.

---

# Priority 5 — Difficulty-Based Package Sorting

## Problem

Current sorting:

stackable
↓

volume
↓

footprint
↓

weight

This assumes large packages are always the hardest.

That is not always true.

---

## Requirement

Replace static ordering with a computed difficulty score.

Possible factors:

- volume
- footprint
- aspect ratio
- rotation availability
- weight
- stackability

Long thin packages should receive a higher difficulty than simple cubes of similar volume.

---

## Constraints

Sorting must remain deterministic.

---

## Success Criteria

Hard-to-place packages should generally be loaded earlier.

---

# Priority 6 — Smarter Slide Recovery

## Problem

Current Y-slide:

±100
±200
±300

This is brute force.

---

## Requirement

Instead of fixed steps:

Use nearby obstacles to compute likely valid slide positions.

Examples:

slide immediately after obstacle

slide immediately before obstacle

nearest legal Y

This reduces unnecessary validation.

---

## Constraints

Keep the slide mechanism.

Replace only candidate generation.

---

## Success Criteria

Fewer slide candidates.

Same or better recovery rate.

---

# Priority 7 — Fragmentation Metric for Vehicle Selection

## Problem

Vehicle selection currently considers:

remaining volume

remaining floor

remaining payload

Remaining capacity alone does not describe future usability.

---

## Requirement

Add a lightweight fragmentation metric.

Possible examples:

largest remaining rectangle

largest free floor strip

largest connected floor region

Penalty should increase when remaining space becomes fragmented.

Use this metric together with the existing waste score.

---

## Success Criteria

Vehicles with cleaner remaining layouts should be preferred over equally empty but fragmented vehicles.

---

# General Constraints

Maintain existing architecture.

Do NOT redesign:

- PlanningState
- Spatial Grid
- Extreme Points
- Candidate Priority
- Validation Pipeline
- Support System
- Door System
- Dead Space (already completed)

These are considered complete.

---

# Performance Requirements

The planner must remain suitable for interactive use.

Target:

- runtime increase <25%
- deterministic output
- no stochastic optimization
- no genetic algorithms
- no simulated annealing
- no Monte Carlo search

The planner should remain a deterministic heuristic solver.

---

# Code Quality

New heuristics should be:

- modular
- independently testable
- configurable
- documented

Avoid magic numbers.

Expose thresholds as constants or configuration values.

---

# Success Definition

After completing this roadmap, the planner should:

- produce denser packing
- create fewer unusable cavities
- recover from greedy mistakes
- make more future-aware placement decisions
- preserve deterministic behavior
- maintain interactive performance
- require no UI or database changes

The goal is to approach commercial heuristic truck/container loading quality while keeping the algorithm understandable, maintainable, and fast.