"""
Benchmark: floor_contact weight = 25 (original) vs 5 (Phase 1)
Run across 50 random shipments with varying stackable/non-stackable ratios.

Usage: python benchmark_floor_contact.py
"""

import os, random, time, copy, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from collections import defaultdict

from truck_load_planner.engine.package import Package
from truck_load_planner.engine.container import Container
from truck_load_planner.engine.planner import Planner

CONTAINER = Container(
    id=1, name="40ft Container",
    length=12000, width=2400, height=2700, payload_kg=28000,
)

random.seed(42)

def gen_shipment(n_pkgs, stackable_ratio):
    """Generate a random shipment with *stackable_ratio* (0.0-1.0) stackable."""
    pkgs = []
    for i in range(n_pkgs):
        is_stackable = random.random() < stackable_ratio
        # Size distribution: 60% medium, 20% large, 20% small
        size_bucket = random.random()
        if size_bucket < 0.2:
            l = random.randint(1000, 1400)
            w = random.randint(800, 1200)
            h = random.randint(600, 1000)
            wt = random.randint(60, 120)
        elif size_bucket < 0.8:
            l = random.randint(600, 1000)
            w = random.randint(500, 800)
            h = random.randint(300, 600)
            wt = random.randint(20, 60)
        else:
            l = random.randint(300, 600)
            w = random.randint(300, 500)
            h = random.randint(200, 400)
            wt = random.randint(10, 25)
        pkgs.append(Package(
            id=i, name=f"P{i}",
            length_mm=l, width_mm=w, height_mm=h,
            weight_kg=wt, stackable=is_stackable,
        ))
    return pkgs


def run_planner(planner, pkgs):
    """Run auto_arrange and return metrics."""
    t0 = time.perf_counter()
    result = planner.auto_arrange(pkgs, debug=False)
    elapsed = time.perf_counter() - t0

    # Count stack vs floor placements
    stack_count = sum(1 for pl in planner.placements if pl.z > 0)
    floor_count = sum(1 for pl in planner.placements if pl.z == 0)

    # Floor space consumed: length of the rightmost floor package's right edge
    max_floor_x = 0
    for pl in planner.placements:
        if pl.z == 0 and pl.package:
            right = pl.x + (pl.package.length_mm if pl.rotation % 180 != 90 else pl.package.width_mm)
            if right > max_floor_x:
                max_floor_x = right

    # Floor placements by package type
    ns_floor = 0
    s_floor = 0
    for pl in planner.placements:
        if pl.z == 0 and pl.package:
            if pl.package.stackable:
                s_floor += 1
            else:
                ns_floor += 1

    # Multi-container vehicle estimate:
    # Fill containers sequentially with remaining packages
    remaining = [p for p in pkgs
                 if p.id not in {pl.package_id for pl in planner.placements}]
    total_vehicles = 1  # this container
    while remaining:
        p2 = Planner(CONTAINER)
        p2.auto_arrange(remaining, debug=False)
        total_vehicles += 1
        remaining = [p for p in remaining
                     if p.id not in {pl.package_id for pl in p2.placements}]

    return {
        "placed": result.placed_packages,
        "failed": result.failed_packages,
        "stack_count": stack_count,
        "floor_count": floor_count,
        "ns_on_floor": ns_floor,
        "s_on_floor": s_floor,
        "max_floor_x_mm": max_floor_x,
        "utilization_pct": result.utilization,
        "plan_score": result.total_score,
        "vehicles": total_vehicles,
        "time_s": elapsed,
    }


def run_trial(pkgs, label):
    """Run single trial and return metrics dict."""
    planner = Planner(CONTAINER)
    return run_planner(planner, pkgs)


# ── Scenarios ──────────────────────────────────────────────────────────
RATIOS = [0.3, 0.5, 0.7, 0.9]
PKG_COUNTS = [20, 35, 50]
TRIALS_PER_CELL = 5  # 4 ratios × 3 counts × 5 trials = 60 runs per weight

all_results_25 = []
all_results_5 = []
regressions = []  # cases where weight=5 is worse on a key metric

# Temporarily change the weight
import truck_load_planner.engine.scorer as scorer

original_weights = dict(scorer.SCORING_WEIGHTS)

for n_pkgs in PKG_COUNTS:
    for ratio in RATIOS:
        for trial in range(TRIALS_PER_CELL):
            pkgs = gen_shipment(n_pkgs, ratio)

            # --- weight = 25 (original) ---
            scorer.SCORING_WEIGHTS["floor_contact"] = 25
            # Clear any cached module state
            r25 = run_trial(pkgs, f"W25 n={n_pkgs} r={ratio} t={trial}")
            all_results_25.append(r25)

            # --- weight = 5 (Phase 1) ---
            scorer.SCORING_WEIGHTS["floor_contact"] = 5
            r5 = run_trial(pkgs, f"W5 n={n_pkgs} r={ratio} t={trial}")
            all_results_5.append(r5)

            # Check for regression
            if r5["vehicles"] > r25["vehicles"]:
                regressions.append({
                    "n": n_pkgs, "ratio": ratio, "trial": trial,
                    "vehicles_25": r25["vehicles"],
                    "vehicles_5": r5["vehicles"],
                    "placed_25": r25["placed"],
                    "placed_5": r5["placed"],
                })
            elif r5["utilization_pct"] < r25["utilization_pct"] - 5:
                regressions.append({
                    "n": n_pkgs, "ratio": ratio, "trial": trial,
                    "type": "utilization_drop",
                    "util_25": r25["utilization_pct"],
                    "util_5": r5["utilization_pct"],
                })

# Restore original
scorer.SCORING_WEIGHTS["floor_contact"] = original_weights["floor_contact"]

# ── Aggregate ──────────────────────────────────────────────────────────
def avg(lst):
    return sum(lst) / len(lst) if lst else 0

print("=" * 120)
print("BENCHMARK: floor_contact weight = 25 (original) vs 5 (Phase 1)")
print(f"Trials: {len(all_results_25)} per configuration")
print("=" * 120)

print(f"\n{'Metric':<30s} {'W=25 (orig)':>15s} {'W=5 (Phase 1)':>15s} {'Change':>15s}")
print("-" * 80)

metrics = [
    ("Placed (avg)", "placed", "{:.1f}"),
    ("Failed (avg)", "failed", "{:.1f}"),
    ("Stack count (avg)", "stack_count", "{:.1f}"),
    ("Stack % of placed", None, None),
    ("Non-stackable on floor (avg)", "ns_on_floor", "{:.1f}"),
    ("Stackable on floor (avg)", "s_on_floor", "{:.1f}"),
    ("Max floor X (mm, avg)", "max_floor_x_mm", "{:.0f}"),
    ("Utilization % (avg)", "utilization_pct", "{:.1f}"),
    ("Plan score (avg)", "plan_score", "{:.1f}"),
    ("Vehicles (avg)", "vehicles", "{:.2f}"),
    ("Planning time (s, avg)", "time_s", "{:.4f}"),
]

for name, key, fmt in metrics:
    if key:
        v25 = avg([r[key] for r in all_results_25])
        v5 = avg([r[key] for r in all_results_5])
        change = v5 - v25
        print(f"{name:<30s} {fmt.format(v25):>15s} {fmt.format(v5):>15s} {fmt.format(change):>15s}")
    elif name == "Stack % of placed":
        v25 = avg([r["stack_count"] / max(r["placed"], 1) * 100 for r in all_results_25])
        v5 = avg([r["stack_count"] / max(r["placed"], 1) * 100 for r in all_results_5])
        print(f"{name:<30s} {v25:>14.1f}% {v5:>14.1f}% {v5-v25:>+14.1f}%")

print("-" * 80)

# ── Breakdown by stackable ratio ──────────────────────────────────────
print(f"\n{'='*120}")
print("BREAKDOWN BY STACKABLE RATIO")
print(f"{'='*120}")

for ratio in RATIOS:
    subset_25 = [r for i, r in enumerate(all_results_25)
                 if PKG_COUNTS[i // (TRIALS_PER_CELL * len(RATIOS)) % len(PKG_COUNTS)] is not None]
    # Actually let me redo this properly by iterating
    print(f"\n--- Stackable ratio: {ratio:.0%} ---")
    for n_pkgs in PKG_COUNTS:
        idxs_25 = []
        idxs_5 = []
        idx = 0
        for _n in PKG_COUNTS:
            for _r in RATIOS:
                for _t in range(TRIALS_PER_CELL):
                    if _n == n_pkgs and _r == ratio:
                        idxs_25.append(idx)
                        idxs_5.append(idx)
                    idx += 1

        if not idxs_25:
            continue

        v25_v = avg([all_results_25[i]["vehicles"] for i in idxs_25])
        v5_v = avg([all_results_5[i]["vehicles"] for i in idxs_5])
        v25_u = avg([all_results_25[i]["utilization_pct"] for i in idxs_25])
        v5_u = avg([all_results_5[i]["utilization_pct"] for i in idxs_5])
        v25_s = avg([all_results_25[i]["stack_count"] for i in idxs_25])
        v5_s = avg([all_results_5[i]["stack_count"] for i in idxs_5])
        v25_ns = avg([all_results_25[i]["ns_on_floor"] for i in idxs_25])
        v5_ns = avg([all_results_5[i]["ns_on_floor"] for i in idxs_5])
        v25_ss = avg([all_results_25[i]["s_on_floor"] for i in idxs_25])
        v5_ss = avg([all_results_5[i]["s_on_floor"] for i in idxs_5])

        print(f"  n={n_pkgs:2d}: "
              f"vehicles {v25_v:.2f} -> {v5_v:.2f} "
              f"util {v25_u:.1f} -> {v5_u:.1f}% "
              f"stacks {v25_s:.1f} -> {v5_s:.1f} "
              f"ns-floor {v25_ns:.1f} -> {v5_ns:.1f} "
              f"s-floor {v25_ss:.1f} -> {v5_ss:.1f}")


# ── Regressions ───────────────────────────────────────────────────────
print(f"\n{'='*120}")
print("REGRESSION ANALYSIS")
print(f"{'='*120}")

if regressions:
    print(f"\nCases where W=5 performed WORSE than W=25: {len(regressions)}")
    for r in regressions[:10]:  # show first 10
        if "vehicles_25" in r:
            print(f"  n={r['n']} ratio={r['ratio']:.0%} trial={r['trial']}: "
                  f"vehicles {r['vehicles_25']}  ->  {r['vehicles_5']} (worse)")
        elif "util_25" in r:
            print(f"  n={r['n']} ratio={r['ratio']:.0%} trial={r['trial']}: "
                  f"util {r['util_25']:.1f}%  ->  {r['util_5']:.1f}% (drop >5pp)")
    if len(regressions) > 10:
        print(f"  ... and {len(regressions) - 10} more")
else:
    print("No regressions detected.")

# ── Answers to the 4 questions ────────────────────────────────────────
print(f"\n{'='*120}")
print("ANSWERS")
print(f"{'='*120}")

v25_v_all = avg([r["vehicles"] for r in all_results_25])
v5_v_all = avg([r["vehicles"] for r in all_results_5])
v25_u_all = avg([r["utilization_pct"] for r in all_results_25])
v5_u_all = avg([r["utilization_pct"] for r in all_results_5])
v25_t_all = avg([r["time_s"] for r in all_results_25])
v5_t_all = avg([r["time_s"] for r in all_results_5])

print(f"\n1. Does vehicle count decrease?")
print(f"   Avg vehicles: {v25_v_all:.2f}  ->  {v5_v_all:.2f}  ({v5_v_all - v25_v_all:+.2f})")
if v5_v_all < v25_v_all:
    print(f"   YES -- vehicles reduced by {v25_v_all - v5_v_all:.2f} on average")
else:
    print("   NO -- vehicles unchanged or increased")

print(f"\n2. Does average utilization increase?")
print(f"   Avg utilization: {v25_u_all:.1f}%  ->  {v5_u_all:.1f}%  ({v5_u_all - v25_u_all:+.1f}pp)")
if v5_u_all > v25_u_all:
    print(f"   YES -- utilization increased by {v5_u_all - v25_u_all:.1f} percentage points")
else:
    print("   NO -- utilization unchanged or decreased")

print(f"\n3. Does planning time remain acceptable?")
print(f"   Avg time: {v25_t_all:.4f}s  ->  {v5_t_all:.4f}s")
print(f"   Acceptable (< 1s average)" if v5_t_all < 1.0 else f"   Borderline ({v5_t_all:.2f}s)")

print(f"\n4. Do the layouts still look sensible?")
s_count_25 = sum(r["stack_count"] for r in all_results_25)
s_count_5 = sum(r["stack_count"] for r in all_results_5)
print(f"   Total stacks across all trials: {s_count_25} (W=25)  ->  {s_count_5} (W=5)")
max_stack_height = max(r["stack_count"] for r in all_results_5)
print(f"   Max stacks in a single plan: {max_stack_height}")
ns_floor_25 = sum(r["ns_on_floor"] for r in all_results_25)
ns_floor_5 = sum(r["ns_on_floor"] for r in all_results_5)
print(f"   Non-stackable on floor: {ns_floor_25} (W=25)  ->  {ns_floor_5} (W=5)")
s_floor_25 = sum(r["s_on_floor"] for r in all_results_25)
s_floor_5 = sum(r["s_on_floor"] for r in all_results_5)
print(f"   Stackable on floor: {s_floor_25} (W=25)  ->  {s_floor_5} (W=5)")
if s_floor_5 < s_floor_25 and ns_floor_5 >= ns_floor_25:
    print(f"   YES -- stackable packages moved off floor, non-stackable preserved on floor")
else:
    print(f"   Review needed -- check individual cases")
