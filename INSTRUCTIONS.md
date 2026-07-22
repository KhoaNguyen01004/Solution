# Simplify the 3D Bin Packing Algorithm

**✅ Refactoring complete.** See CHANGELOG.md for details. All changes are reflected in SYSTEM.md and SORTING_STRATEGY.md.

You are refactoring an existing Python 3D bin packing project.

## Goal

The current planner has become over-engineered. It contains many interacting heuristics, repair passes, rescoring stages, and prediction algorithms, making it difficult to maintain while not producing consistently good packing results.

Your objective is **not to improve the existing heuristic system**.

Your objective is to **remove unnecessary complexity** and redesign the placement algorithm around a small number of strong heuristics.

The final system should be:

* easier to understand
* easier to debug
* faster
* deterministic
* modular
* produce equal or better packing quality

Favor deleting code over adding code.

---

# Current Problems

The current planner suffers from several architectural issues:

## 1. Too many scoring criteria

The scoring system contains many overlapping heuristics such as:

* rear proximity
* x preference
* compactness
* package contact
* wall contact
* frontier score
* dead-space score
* cluster score
* stability score
* weight balance
* etc.

Most of these measure nearly the same thing.

Replace them with a small scoring model.

Target no more than 4–5 scoring terms.

Recommended:

* maximize contact area
* minimize X position
* prefer floor support
* maintain weight balance

Everything else should be removed unless it provides clear measurable benefit.

---

## 2. Candidate generation is too complicated

Current pipeline generates candidates from many sources:

* extreme points
* frontier
* right wall
* floor anchors
* rescoring
* tightening
* sliding
* diagonal movement
* retries

Simplify candidate generation.

Generate candidates only from occupied boxes:

For every placed box:

* right face
* front face
* top face

Also include:

* origin

Remove candidate duplication.

Remove candidate rescoring.

Generate a small candidate list.

---

## 3. Remove predictive heuristics

The planner currently tries to predict the future with algorithms such as:

* dead space prediction
* frontier estimation
* future package estimation
* clustering
* gap filling

These make the algorithm complicated while having limited influence.

Delete these systems unless absolutely required.

A good constructive heuristic should naturally reduce dead space.

---

## 4. Simplify placement

Placement should become:

```
Sort items

↓

For each item

    Generate candidates

    Validate

    Score

    Pick best

Place item
```

Avoid multiple repair passes.

Avoid repeated rescoring.

Avoid multiple optimization loops.

---

## 5. Simplify sorting

Current sorting mixes:

* volume
* footprint
* weight
* height
* density
* priorities

Create a single sortable difficulty score.

Example:

difficulty =
volume
× footprint
× aspect_ratio_penalty

Sort descending.

Keep it deterministic.

---

## 6. Remove repair algorithms

If there are algorithms such as:

* destroy and repair
* adaptive repair
* rearrangement
* fill_frontier_gaps
* consolidation
* compaction

Evaluate whether they are still necessary.

Delete them if the constructive algorithm is improved.

The objective is to make the first placement correct instead of fixing it later.

---

## 7. Simplify candidate scoring

Instead of dozens of weighted terms, use something like:

```
score =

1000 * contact_area

- 200 * x_position

+ 100 * floor_support

+ 50 * weight_balance
```

Keep scoring interpretable.

Every coefficient should have an obvious meaning.

---

## 8. Keep only strong validation

The collision and validation code is one of the strongest parts of the project.

Keep:

* collision detection
* boundary checks
* support validation
* weight limits
* stacking constraints

These should remain mostly unchanged.

---

## 9. Remove duplicate logic

Look for places where the same concept is evaluated twice.

Examples:

Candidate generation prefers walls.

Then scoring prefers walls.

Candidate generation prefers low height.

Then scoring prefers low height.

Candidate generation prefers rear placement.

Then scoring prefers rear placement.

Keep each decision in exactly one place.

---

## 10. Reduce optimization passes

Avoid pipelines like:

```
Generate

↓

Slide

↓

Tighten

↓

Rescore

↓

Slide again

↓

Repair

↓

Compact

↓

Rearrange
```

Instead:

```
Generate

↓

Validate

↓

Score

↓

Place
```

---

# Design Principles

Follow these principles:

* Delete unnecessary code.
* Prefer simple algorithms over clever heuristics.
* Every heuristic must have a clear purpose.
* Minimize the number of configurable weights.
* Prefer deterministic behavior.
* Avoid hidden interactions between modules.
* Keep each module responsible for one thing.

---

# Deliverables

1. Refactor the planner into a simple constructive algorithm.

2. Remove obsolete modules and dead code.

3. Remove heuristics that duplicate each other.

4. Simplify the scoring function.

5. Simplify candidate generation.

6. Keep validation robust.

7. Update documentation to explain the new algorithm.

8. Measure performance before and after:

* packing efficiency
* runtime
* code size
* number of heuristics
* average candidates evaluated

Provide a summary explaining every removed component and why it was removed.

---

**Success criteria**

A successful refactor should reduce the codebase by roughly **30–50%**, reduce the number of heuristics dramatically, and produce a planner that is easier to reason about while maintaining or improving packing quality. The emphasis is on a strong constructive algorithm rather than layers of prediction and repair.
