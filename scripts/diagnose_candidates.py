"""
Diagnostic: instrument candidate generation, validation, and scoring
for one package to identify why stacking may be preferred over side-by-side.
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from truck_load_planner.engine.container import Container
from truck_load_planner.engine.package import Package
from truck_load_planner.engine.planner import Planner
from truck_load_planner.engine.auto_arrange import MAX_POSSIBLE_SCORE
from truck_load_planner.engine.candidate_points import generate_slide_candidates

# ── Scenario ────────────────────────────────────────────────────
# A moderately sized container with one floor package already placed.
# The second package could go side-by-side on the floor or stacked on top.

CONTAINER = Container(
    name="Test",
    length=2000,    # mm
    width=1500,     # mm
    height=2000,    # mm
    payload_kg=5000,
)

PKG_A = Package(
    id=1, name="FloorBox",
    length_mm=1000, width_mm=500, height_mm=500, weight_kg=50,
    stackable=True,  # can be stacked upon
    allow_rotation=True,
)

PKG_B = Package(
    id=2, name="StackableBox",
    length_mm=500, width_mm=400, height_mm=400, weight_kg=30,
    stackable=True,   # can be placed on top of others
    allow_rotation=True,
)


def _rot_dims(pkg, rotation):
    if rotation in (90, 270):
        return pkg.width_mm, pkg.length_mm, pkg.height_mm
    return pkg.length_mm, pkg.width_mm, pkg.height_mm


def main():
    planner = Planner(CONTAINER)

    # ── Place Package A at the origin ──
    result_a = planner.place_package(PKG_A, 0, 0, 0, 0)
    assert result_a.valid, f"Package A placement failed: {result_a.reasons}"
    print(f"Placed PKG_A at (0, 0, 0)  —  {PKG_A.length_mm}x{PKG_A.width_mm}x{PKG_A.height_mm}")
    print()

    # ── Instrument the pipeline for Package B ──
    pkg = PKG_B
    remaining_pkgs = []  # no more packages after this one

    # 1. Base candidates (extreme points)
    base_candidates = list(planner.get_candidate_points())
    print(f"Extreme points from planner.get_candidate_points():")
    for pt in base_candidates:
        print(f"  ({pt[0]:6.0f}, {pt[1]:6.0f}, {pt[2]:6.0f})  {'FLOOR' if pt[2] == 0 else 'STACKED'}")
    print(f"  Total: {len(base_candidates)}")
    print()

    # 2. Right-wall candidate
    container = planner.container
    clearance = getattr(pkg, 'clearance_mm', 10)
    right_y = container.width - pkg.width_mm - clearance
    right_candidate = None
    if right_y > clearance:
        right_candidate = (0, right_y, 0)
        if right_candidate not in base_candidates:
            base_candidates = [right_candidate] + list(base_candidates)
            print(f"Added right-wall candidate: (0, {right_y:.0f}, 0)  FLOOR")
        else:
            print(f"Right-wall candidate (0, {right_y:.0f}, 0) already in extreme points")
    else:
        print(f"No right-wall candidate (right_y={right_y:.0f} <= clearance={clearance})")
    print()

    # 3. Expand with rotations
    expanded = _expand_candidates(base_candidates, pkg.allow_rotation)
    print(f"Expanded candidates ({len(expanded)} total):")
    for i, c in enumerate(expanded):
        label = "FLOOR" if c["z"] == 0 else "STACKED"
        print(f"  [{i:2d}] ({c['x']:6.0f}, {c['y']:6.0f}, {c['z']:6.0f}) rot={c['rotation']}°  {label}")
    print()

    # 4. Validate and score each candidate
    validated = []
    for c in expanded:
        vresult = planner.validate_position(
            pkg, c["x"], c["y"], c["z"], c["rotation"],
        )
        if not vresult.valid:
            validated.append((c, None, vresult.reasons))
        else:
            score = planner.evaluate_position(
                pkg, c["x"], c["y"], c["z"], c["rotation"],
                remaining_packages=remaining_pkgs,
            )
            validated.append((c, score, []))

    # 5. Stats
    floor_total = sum(1 for c in expanded if c["z"] == 0)
    stacked_total = sum(1 for c in expanded if c["z"] > 0)
    floor_valid = sum(1 for c, s, r in validated if s is not None and c["z"] == 0)
    stacked_valid = sum(1 for c, s, r in validated if s is not None and c["z"] > 0)

    print(f"Candidate summary:")
    print(f"  Total candidates generated:        {len(expanded)}")
    print(f"  Floor candidates (z=0):            {floor_total}")
    print(f"  Stacked candidates (z>0):          {stacked_total}")
    print(f"  Valid floor candidates:            {floor_valid}")
    print(f"  Valid stacked candidates:          {stacked_valid}")
    print()

    # 6. Top 10 by score
    scored = [(c, s) for c, s, r in validated if s is not None]
    scored.sort(key=lambda x: -x[1].total)

    print(f"Top {min(10, len(scored))} candidates by score:")
    print(f"  {'Rank':<4} {'Pos':<30} {'Score':<7} {'Floor?':<6} {'Breakdown'}")
    print(f"  {'----':<4} {'':<30} {'------':<7} {'------':<6} {'----------'}")
    for rank, (c, s) in enumerate(scored[:10]):
        label = "FLOOR" if c["z"] == 0 else "STACKED"
        pos_str = f"({c['x']:5.0f},{c['y']:5.0f},{c['z']:5.0f}) r={c['rotation']}°"
        # Show top 3 breakdown categories
        top_keys = sorted(s.breakdown.items(), key=lambda x: -x[1])[:3]
        breakdown_str = ", ".join(f"{k}={v:.1f}" for k, v in top_keys)
        print(f"  {rank:<4} {pos_str:<30} {s.total:<7.2f} {label:<6} {breakdown_str}")

    # If there's more than 10, show the runner-up
    if len(scored) > 10:
        c, s = scored[10]
        label = "FLOOR" if c["z"] == 0 else "STACKED"
        pos_str = f"({c['x']:5.0f},{c['y']:5.0f},{c['z']:5.0f}) r={c['rotation']}°"
        print(f"  ...")
        print(f"  [10+] {pos_str:<30} {s.total:<7.2f} {label:<6}")

    print()

    # 7. Report best candidate
    if scored:
        best_c, best_s = scored[0]
        label = "FLOOR" if best_c["z"] == 0 else "STACKED"
        print(f"BEST CANDIDATE: ({best_c['x']:.0f}, {best_c['y']:.0f}, {best_c['z']:.0f}) "
              f"rot={best_c['rotation']}°  {label}  score={best_s.total:.2f}")
        print(f"Full breakdown:")
        for k, v in sorted(best_s.breakdown.items(), key=lambda x: -x[1]):
            weight = {"floor_contact": 25, "wall_contact": 10, "package_contact": 15,
                      "face_contact": 10, "compactness": 5, "stack_quality": 5,
                      "vertical_stability": 10, "z_preference": 10, "x_preference": 5,
                      "rear_proximity": 10, "y_balance": 15, "dead_space_quality": 10}.get(k, 0)
            print(f"    {k:<25} {v*weight:>7.2f}  (raw={v:.3f}, weight={weight})")

    # 8. Check if candidate generation created any floor side-by-side candidates
    floor_side_candidates = [
        c for c, s, r in validated
        if s is not None and c["z"] == 0
        and c["x"] > 0  # not at origin or right-wall
    ]
    if floor_side_candidates:
        print(f"\nFloor side-by-side candidates (x>0): {len(floor_side_candidates)}")
        for c, s in [(c, s) for c, s, _ in [(c, s, r) for c, s, r in validated if s is not None and c["z"] == 0 and c["x"] > 0]]:
            print(f"  ({c['x']:.0f}, {c['y']:.0f}, {c['z']:.0f}) rot={c['rotation']}° score={s.total:.2f}")
    else:
        print(f"\n*** NO floor side-by-side candidates were valid! ***")
        # Show why floor side-by-side candidates were invalid
        for c, s, reasons in validated:
            if c["z"] == 0 and c["x"] > 0 and s is None:
                print(f"  ({c['x']:.0f}, {c['y']:.0f}, {c['z']:.0f}) rot={c['rotation']}° INVALID: {reasons}")

    # 9. Y-slide fallback analysis
    print(f"\nY-slide fallback candidates:")
    slide_cands = generate_slide_candidates(base_candidates, pkg, container)
    print(f"  Generated {len(slide_cands)} slide candidates")
    slide_floor = sum(1 for c in slide_cands if c["z"] == 0)
    slide_stacked = sum(1 for c in slide_cands if c["z"] > 0)
    print(f"  Floor: {slide_floor}, Stacked: {slide_stacked}")

    slide_valid = 0
    for c in slide_cands:
        vresult = planner.validate_position(pkg, c["x"], c["y"], c["z"], c["rotation"])
        if vresult.valid:
            slide_valid += 1
    print(f"  Valid: {slide_valid}")


def _expand_candidates(base_candidates, allow_rotation):
    """Replicate auto_arrange expansion logic."""
    expanded = []
    seen = set()
    for pos in base_candidates:
        if isinstance(pos, dict):
            x, y, z = pos.get("x", 0), pos.get("y", 0), pos.get("z", 0)
        else:
            x, y, z = pos[0], pos[1], pos[2]
        key0 = (x, y, z, 0)
        if key0 not in seen:
            seen.add(key0)
            expanded.append({"x": x, "y": y, "z": z, "rotation": 0})
        if allow_rotation:
            key90 = (x, y, z, 90)
            if key90 not in seen:
                seen.add(key90)
                expanded.append({"x": x, "y": y, "z": z, "rotation": 90})
    return expanded


if __name__ == "__main__":
    main()
