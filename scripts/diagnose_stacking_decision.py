"""
Diagnostic: For each placed package, report every valid candidate,
its score breakdown, and whether it is FLOOR (z=0) or STACK (z>0).
Then summarise how often STACK candidates were generated, validated,
and whether they ever won — and which scoring terms discriminated.

Run: python diagnose_stacking_decision.py
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from collections import defaultdict
from truck_load_planner.engine.package import Package
from truck_load_planner.engine.container import Container
from truck_load_planner.engine.planner import Planner
from truck_load_planner.engine.geometry import AABB
from truck_load_planner.engine.validation import validate_placement
from truck_load_planner.engine.scorer import score_placement, SCORING_WEIGHTS

# ── Scenario ──────────────────────────────────────────────────────────
CONTAINER = Container(
    id=1, name="40ft Container",
    length=12000, width=2400, height=2700, payload_kg=28000,
)

# Generate a mix of packages: many stackable, some non-stackable
def make_pkg(i, length, width, height, weight, stackable=True, name=None):
    return Package(
        id=i, name=name or f"P{i}",
        length_mm=length, width_mm=width, height_mm=height,
        weight_kg=weight, stackable=stackable,
        horizontal_clearance_mm=10.0, vertical_clearance_mm=0.0,
    )

packages = [
    # Non-stackable (must go on floor)
    make_pkg(1, 1200, 1000, 800, 120, stackable=False, name="NS-Big"),
    make_pkg(2, 1000, 800, 700, 90, stackable=False, name="NS-Med"),
    # Large stackable
    make_pkg(3, 1100, 900, 600, 80, name="Lg-Stk"),
    make_pkg(4, 1000, 800, 500, 60, name="Med-Stk-A"),
    make_pkg(5, 800, 700, 500, 50, name="Med-Stk-B"),
    make_pkg(6, 900, 700, 400, 45, name="Med-Stk-C"),
    # Medium stackable
    make_pkg(7, 700, 600, 400, 35, name="Sm-Stk-A"),
    make_pkg(8, 600, 500, 400, 30, name="Sm-Stk-B"),
    make_pkg(9, 600, 500, 350, 25, name="Sm-Stk-C"),
    make_pkg(10, 500, 500, 300, 20, name="Sm-Stk-D"),
    # More stackable
    make_pkg(11, 800, 600, 500, 40, name="Stk-Tall"),
    make_pkg(12, 800, 600, 400, 35, name="Stk-Short"),
    make_pkg(13, 700, 500, 400, 30, name="Stk-Mid"),
    make_pkg(14, 600, 500, 300, 25, name="Stk-Low"),
    make_pkg(15, 500, 400, 300, 20, name="Stk-Sm"),
]

# Sort the same way LargestFirstStrategy does
sorted_packages = sorted(
    packages,
    key=lambda p: (
        p.stackable,
        -(p.length_mm * p.width_mm * p.height_mm),
        -(p.length_mm * p.width_mm),
        -p.weight_kg,
    ),
)

# ── Instrumented arrangement ──────────────────────────────────────────
planner = Planner(CONTAINER)

# Storage
package_decisions = []   # per-package summary
all_valid = []           # every valid candidate across all packages
stack_lost_to_floor = []  # cases where STACK existed but FLOOR won
floor_lost_to_stack = []  # cases where FLOOR existed but STACK won

def _expand_candidates(base_candidates, allow_rotation):
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

# Manually replicate the LargestFirstStrategy loop with full instrumentation
for idx, pkg in enumerate(sorted_packages):
    remaining_pkgs = sorted_packages[idx + 1:]

    base_candidates = list(planner.get_candidate_points())

    # Right-wall candidate
    h_clr = getattr(pkg, 'horizontal_clearance_mm', 10.0)
    right_y = CONTAINER.width - pkg.width_mm - h_clr
    if right_y > h_clr:
        right_candidate = (0, right_y, 0)
        if right_candidate not in base_candidates:
            base_candidates = [right_candidate] + list(base_candidates)

    expanded = _expand_candidates(base_candidates, pkg.allow_rotation)

    # Collect valid candidates with scores
    valid_candidates = []
    for cand in expanded:
        vresult = planner.validate_position(
            pkg, cand["x"], cand["y"], cand["z"], cand["rotation"],
        )
        if not vresult.valid:
            continue
        score = planner.evaluate_position(
            pkg, cand["x"], cand["y"], cand["z"], cand["rotation"],
            debug=False, remaining_packages=remaining_pkgs,
        )
        cand_type = "STACK" if cand["z"] > 0 else "FLOOR"
        valid_candidates.append({
            "pos": (cand["x"], cand["y"], cand["z"], cand["rotation"]),
            "type": cand_type,
            "score": score.total,
            "breakdown": dict(score.breakdown),
        })

    if not valid_candidates:
        # Y-slide pass
        from truck_load_planner.engine.candidate_points import generate_slide_candidates
        slide_cands = generate_slide_candidates(base_candidates, pkg, CONTAINER)
        for cand in slide_cands:
            vresult = planner.validate_position(
                pkg, cand["x"], cand["y"], cand["z"], cand["rotation"],
            )
            if not vresult.valid:
                continue
            score = planner.evaluate_position(
                pkg, cand["x"], cand["y"], cand["z"], cand["rotation"],
                debug=False, remaining_packages=remaining_pkgs,
            )
            cand_type = "STACK" if cand["z"] > 0 else "FLOOR"
            valid_candidates.append({
                "pos": (cand["x"], cand["y"], cand["z"], cand["rotation"]),
                "type": cand_type,
                "score": score.total,
                "breakdown": dict(score.breakdown),
            })

    # Choose best
    valid_candidates.sort(key=lambda c: -c["score"])
    best = valid_candidates[0] if valid_candidates else None

    has_stack = any(c["type"] == "STACK" for c in valid_candidates)
    has_floor = any(c["type"] == "FLOOR" for c in valid_candidates)

    if best:
        is_stack_win = best["type"] == "STACK"
        p_result = planner.place_package(
            pkg, best["pos"][0], best["pos"][1], best["pos"][2], best["pos"][3],
        )
        placed = p_result.valid
    else:
        is_stack_win = False
        placed = False

    entry = {
        "pkg": pkg.name,
        "stackable": pkg.stackable,
        "placed": placed,
        "total_valid": len(valid_candidates),
        "stack_valid": sum(1 for c in valid_candidates if c["type"] == "STACK"),
        "floor_valid": sum(1 for c in valid_candidates if c["type"] == "FLOOR"),
        "chosen": best["pos"] if best else None,
        "chosen_type": best["type"] if best else "NONE",
        "chosen_score": best["score"] if best else 0,
        "chosen_breakdown": best["breakdown"] if best else {},
        "has_stack": has_stack,
        "has_floor": has_floor,
        "stack_won": is_stack_win,
        "all_candidates": valid_candidates,
    }
    package_decisions.append(entry)
    all_valid.extend(valid_candidates)

    if has_stack and has_floor:
        if best and best["type"] == "FLOOR":
            stack_lost_to_floor.append(entry)
        elif best and best["type"] == "STACK":
            floor_lost_to_stack.append(entry)

# ── Report ────────────────────────────────────────────────────────────
def fmt_score(score):
    return f"{score:6.2f}"

def fmt_type(t):
    return f"{t:5s}"

print("=" * 140)
print(f"{'Pkg':12s} {'Stk?':5s} {'#Valid':6s} {'#Stack':6s} {'#Floor':6s} "
      f"{'Chosen':30s} {'Type':5s} {'Score':7s} "
      f"{'floor':>6s} {'wall':>6s} {'pkgCt':>6s} {'faceCt':>6s} "
      f"{'compt':>6s} {'stkQl':>6s} {'vStab':>6s} {'zPref':>6s} "
      f"{'xPref':>6s} {'rearP':>6s} {'yBal':>6s} {'deadS':>6s}")
print("-" * 140)

for e in package_decisions:
    ch = e["chosen"]
    pos_str = f"({ch[0]:.0f},{ch[1]:.0f},{ch[2]:.0f},r{ch[3]})" if ch else "NONE"
    bd = e["chosen_breakdown"]
    print(f"{e['pkg']:12s} {str(e['stackable']):5s} {e['total_valid']:6d} "
          f"{e['stack_valid']:6d} {e['floor_valid']:6d} "
          f"{pos_str:30s} {fmt_type(e['chosen_type']):5s} {fmt_score(e['chosen_score']):7s} "
          f"{bd.get('floor_contact',0):6.1f} {bd.get('wall_contact',0):6.1f} "
          f"{bd.get('package_contact',0):6.1f} {bd.get('face_contact',0):6.1f} "
          f"{bd.get('compactness',0):6.1f} {bd.get('stack_quality',0):6.1f} "
          f"{bd.get('vertical_stability',0):6.1f} {bd.get('z_preference',0):6.1f} "
          f"{bd.get('x_preference',0):6.1f} {bd.get('rear_proximity',0):6.1f} "
          f"{bd.get('y_balance',0):6.1f} {bd.get('dead_space_quality',0):6.1f}")

print("=" * 140)

# ── Summary ───────────────────────────────────────────────────────────
print()
print("SUMMARY")
print("-------")
total = len(package_decisions)
placed = sum(1 for e in package_decisions if e["placed"])
print(f"Total packages attempted: {total}")
print(f"Placed: {placed}")
print(f"Failed: {total - placed}")
print()

# Packages that had stack candidates
with_stack = [e for e in package_decisions if e["has_stack"]]
with_floor = [e for e in package_decisions if e["has_floor"]]
print(f"Packages with at least one STACK candidate:  {len(with_stack)}/{total}")
print(f"Packages with at least one FLOOR candidate:  {len(with_floor)}/{total}")
print(f"Packages with BOTH types available:          {len(stack_lost_to_floor) + len(floor_lost_to_stack)}/{total}")
print()

# Stack vs floor wins
print(f"STACK candidates that WON:   {len(floor_lost_to_stack)}")
print(f"FLOOR candidates that WON:   {len(stack_lost_to_floor)}")
print()

# When STACK existed but FLOOR won, find discriminating terms
if stack_lost_to_floor:
    print("DETAIL: STACK existed but FLOOR was chosen")
    print("-" * 50)
    for e in stack_lost_to_floor:
        # Find the best STACK candidate's score vs the chosen FLOOR
        best_stack = max((c for c in e["all_candidates"] if c["type"] == "STACK"), key=lambda c: c["score"])
        best_floor = max((c for c in e["all_candidates"] if c["type"] == "FLOOR"), key=lambda c: c["score"])
        print(f"  {e['pkg']}: FLOOR={best_floor['score']:.2f} vs STACK={best_stack['score']:.2f}")
        diffs = {}
        for key in SCORING_WEIGHTS:
            d = best_floor["breakdown"].get(key, 0) - best_stack["breakdown"].get(key, 0)
            if abs(d) > 0.5:
                diffs[key] = d
        if diffs:
            for k, v in sorted(diffs.items(), key=lambda x: -abs(x[1])):
                print(f"    {k:20s}: FLOOR={best_floor['breakdown'].get(k,0):.1f}  STACK={best_stack['breakdown'].get(k,0):.1f}  delta={v:+.1f}")
        print(f"    Best STACK pos: ({best_stack['pos'][0]:.0f},{best_stack['pos'][1]:.0f},{best_stack['pos'][2]:.0f})  "
              f"Best FLOOR pos: ({best_floor['pos'][0]:.0f},{best_floor['pos'][1]:.0f},{best_floor['pos'][2]:.0f})")
else:
    print("No cases where STACK lost to FLOOR — implying problem is earlier in pipeline.")
    print()

# Check if any STACK candidates existed at all
total_stack_candidates = sum(e["stack_valid"] for e in package_decisions)
total_floor_candidates = sum(e["floor_valid"] for e in package_decisions)
print(f"Total STACK candidates across all packages: {total_stack_candidates}")
print(f"Total FLOOR candidates across all packages: {total_floor_candidates}")
print()

if total_stack_candidates == 0:
    print(">>> ROOT CAUSE: No STACK candidates were validated at any stage.")
    print("    Problem is SEARCH or VALIDATION, not scoring.")
    print("    Check candidate generation (extreme points for Z > 0)")
    print("    and whether collision / support validation allows stacking.")
elif len(stack_lost_to_floor) == 0 and total_stack_candidates > 0:
    print(">>> Some STACK candidates exist but none appear alongside FLOOR candidates.")
    print("    When both exist, STACK never wins. Likely SCORING issue.")
else:
    # Find the most commonly discriminating terms
    disc_sum = defaultdict(float)
    for e in stack_lost_to_floor:
        best_stack = max((c for c in e["all_candidates"] if c["type"] == "STACK"), key=lambda c: c["score"])
        best_floor = max((c for c in e["all_candidates"] if c["type"] == "FLOOR"), key=lambda c: c["score"])
        for key in SCORING_WEIGHTS:
            d = best_floor["breakdown"].get(key, 0) - best_stack["breakdown"].get(key, 0)
            disc_sum[key] += d
    if stack_lost_to_floor:
        print(">>> DISCRIMINATING TERMS (total delta = FLOOR - STACK, summed across all cases):")
        for k, v in sorted(disc_sum.items(), key=lambda x: -abs(x[1])):
            print(f"    {k:20s}: total delta = {v:+.1f}  (weight = {SCORING_WEIGHTS[k]})")
