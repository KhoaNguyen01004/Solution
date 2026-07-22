"""
End-to-end benchmark using real database data:
  - 31 real package types from tlp_packages
  - 32 real vehicles with container configs
  - Full distribution pipeline (multi-vehicle + repair)
  - Compare floor_contact weight = 25 vs 5
"""
import sys, os, sqlite3, time, copy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from collections import defaultdict

import truck_load_planner.engine.scorer as scorer
from truck_load_planner.engine.package import Package
from truck_load_planner.engine.planner import Planner
from truck_load_planner.engine.geometry import AABB
from truck_load_planner.session import LoadPlanningSession
from truck_load_planner.models import ContainerConfig
from truck_load_planner.optimization.vehicle_cost import (
    VehicleCostModel, compute_vehicle_volume_mm3, _get_fuel_consumption,
    compute_fleet_cost,
)

# ── Load real data from database ─────────────────────────────────────
conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "routing_system.db"))
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Load packages
c.execute("SELECT * FROM tlp_packages ORDER BY id")
pkg_rows = c.fetchall()
packages = []
for r in pkg_rows:
    p = Package(
        id=r["id"], name=r["name"],
        length_mm=r["length"], width_mm=r["width"], height_mm=r["height"],
        weight_kg=r["weight_kg"],
        stackable=bool(r["allow_stacking"]),
        allow_rotation=bool(r["allow_rotation"]),
    )
    packages.append(p)

print(f"Loaded {len(packages)} real package types")
stackable = sum(1 for p in packages if p.stackable)
non_stackable = sum(1 for p in packages if not p.stackable)
print(f"  Stackable: {stackable}, Non-stackable: {non_stackable}")

# Load vehicles with container configs
c.execute("""
    SELECT v.id AS vehicle_id, v.plate_number, v.vehicle_type,
           cc.name AS container_name,
           cc.cargo_length_mm, cc.cargo_width_mm, cc.cargo_height_mm, cc.payload_kg,
           cc.id AS container_config_id,
           fvp.normal_l_per_100km
    FROM vehicles v
    JOIN container_configs cc ON cc.id = v.container_config_id
    LEFT JOIN fuel_vehicle_profile fvp ON fvp.license_plate = v.plate_number
    ORDER BY v.id
""")
vrows = c.fetchall()
conn.close()

print(f"Loaded {len(vrows)} vehicles with containers")

def make_vehicle_sessions(vehicle_rows):
    """Build vehicle sessions from database rows."""
    vinfos = []
    sessions = []
    for vr in vehicle_rows:
        vinfo = {
            "vehicle_id": vr["vehicle_id"],
            "plate_number": vr["plate_number"],
            "vehicle_type": vr["vehicle_type"],
        }
        session = LoadPlanningSession()
        cc = ContainerConfig(
            id=vr["container_config_id"],
            name=vr["container_name"],
            cargo_length_mm=vr["cargo_length_mm"],
            cargo_width_mm=vr["cargo_width_mm"],
            cargo_height_mm=vr["cargo_height_mm"],
            payload_kg=vr["payload_kg"],
        )
        session.select_container(cc)
        session.vehicle_id = vr["vehicle_id"]
        vinfos.append(vinfo)
        sessions.append(session)
    return list(zip(vinfos, sessions))


def run_full_pipeline(packages, vehicle_rows, weight):
    """Run distribution + repair with given floor_contact weight."""
    scorer.SCORING_WEIGHTS["floor_contact"] = weight

    t0 = time.perf_counter()

    vehicle_sessions = make_vehicle_sessions(vehicle_rows)

    from truck_load_planner.engine.distribution import distribute_across_vehicles
    from truck_load_planner.engine.repair import optimize_layout

    placed, failed, unplaced, _, _ = distribute_across_vehicles(
        packages, vehicle_sessions, debug=False,
    )

    unplaced_pkgs = [p for p in packages if p.name in unplaced]

    vehicle_sessions, improved = optimize_layout(
        vehicle_sessions, packages,
        unplaced_packages=unplaced_pkgs,
        max_passes=3, debug=False,
    )

    elapsed = time.perf_counter() - t0

    # Count metrics
    total_placements = 0
    total_stacks = 0
    total_vol_used = 0.0
    total_vol_cap = 0.0
    total_floor_used = 0.0
    total_floor_cap = 0.0
    total_fuel_score = 0.0
    vehicle_count = 0
    ns_on_floor = 0
    s_on_floor = 0
    s_in_stack = 0
    all_height_diffs = []
    all_transitions = 0
    veh_count_with_cargo = 0

    for vinfo, session in vehicle_sessions:
        pls = session._planner.placements
        if not pls:
            continue
        vehicle_count += 1
        total_placements += len(pls)
        stats = session._planner.get_statistics()
        total_vol_used += stats.get("volume_used_m3", 0)
        cc = session._planner.state.container
        vol_cap_m3 = (cc.length * cc.width * cc.height) / 1e9
        total_vol_cap += vol_cap_m3
        floor_cap_mm2 = cc.length * cc.width
        total_floor_cap += floor_cap_mm2

        # Fuel score
        fuel = _get_fuel_consumption(vinfo)
        total_fuel_score += fuel

        # Floor utilization per vehicle
        used_floor_mm2 = 0.0
        for pl in pls:
            pkg = pl.package
            if pkg is None:
                continue
            if pl.z == 0:
                used_floor_mm2 += pkg.length_mm * pkg.width_mm
        total_floor_used += used_floor_mm2

        # Height profile metrics (for vehicles with packages)
        veh_count_with_cargo += 1
        NUM_SLICES = 10
        slice_width = cc.length / max(NUM_SLICES, 1)
        heights = [0.0] * NUM_SLICES
        for pl in pls:
            pkg = pl.package
            if pkg is None:
                continue
            aabb = AABB.from_dimensions(
                pl.x, pl.y, pl.z,
                pkg.length_mm, pkg.width_mm, pkg.height_mm,
                pl.rotation, clearance=0,
            )
            for i in range(NUM_SLICES):
                sx = i * slice_width
                ex = (i + 1) * slice_width
                if aabb.xmax <= sx or aabb.xmin >= ex:
                    continue
                if aabb.zmax > heights[i]:
                    heights[i] = aabb.zmax

        # Compute height diffs and transitions for this vehicle
        for i in range(NUM_SLICES - 1):
            diff = abs(heights[i] - heights[i + 1])
            all_height_diffs.append(diff)
            if diff > 10.0:
                all_transitions += 1

        for pl in pls:
            pkg = pl.package
            if pkg is None:
                continue
            if pl.z > 0:
                total_stacks += 1
                s_in_stack += 1
            elif pl.z == 0:
                if pkg.stackable:
                    s_on_floor += 1
                else:
                    ns_on_floor += 1

    utilization = (total_vol_used / total_vol_cap * 100) if total_vol_cap > 0 else 0.0
    floor_util = (total_floor_used / total_floor_cap * 100) if total_floor_cap > 0 else 0.0
    empty_vol = total_vol_cap - total_vol_used
    height_variance = (
        sum(all_height_diffs) / len(all_height_diffs)
        if all_height_diffs else 0.0
    )
    max_height_diff = max(all_height_diffs) if all_height_diffs else 0.0

    fleet_cost = round(compute_fleet_cost(vehicle_sessions), 1)

    return {
        "vehicles": vehicle_count,
        "placed": total_placements,
        "stacks": total_stacks,
        "ns_floor": ns_on_floor,
        "s_floor": s_on_floor,
        "s_stack": s_in_stack,
        "utilization": utilization,
        "floor_util_pct": round(floor_util, 1),
        "empty_volume_m3": round(empty_vol, 4),
        "fuel_score": round(total_fuel_score, 1),
        "fleet_cost": fleet_cost,
        "height_variance": round(height_variance, 1),
        "max_height_diff": round(max_height_diff, 1),
        "staircase_transitions": all_transitions,
        "time_s": elapsed,
    }


# ── Run both configurations ──────────────────────────────────────────
print("\n" + "=" * 90)
print(f"BENCHMARK ON REAL DATA: {len(packages)} packages, {len(vrows)} vehicles")
print("=" * 90)

result_25 = run_full_pipeline(packages, vrows, weight=25)
result_5 = run_full_pipeline(packages, vrows, weight=5)

print(f"\n{'Metric':<28s} {'W=25':>12s} {'W=5':>12s} {'Change':>12s}")
print("-" * 68)

metrics = [
    ("Vehicles used", "vehicles", "{:.0f}"),
    ("Total placed", "placed", "{:.0f}"),
    ("Stack count", "stacks", "{:.0f}"),
    ("Non-stack on floor", "ns_floor", "{:.0f}"),
    ("Stackable on floor", "s_floor", "{:.0f}"),
    ("Stackable in stacks", "s_stack", "{:.0f}"),
    ("Volume utilization %", "utilization", "{:.1f}"),
    ("Floor utilization %", "floor_util_pct", "{:.1f}"),
    ("Total empty vol (m\u00b3)", "empty_volume_m3", "{:.2f}"),
    ("Total fuel score", "fuel_score", "{:.1f}"),
    ("Fleet cost", "fleet_cost", "{:.1f}"),
    ("Mean height diff (mm)", "height_variance", "{:.1f}"),
    ("Max height diff (mm)", "max_height_diff", "{:.1f}"),
    ("Staircase transitions", "staircase_transitions", "{:.0f}"),
    ("Time (s)", "time_s", "{:.3f}"),
]

for name, key, fmt in metrics:
    v25 = result_25[key]
    v5 = result_5[key]
    change = v5 - v25
    print(f"{name:<28s} {fmt.format(v25):>12s} {fmt.format(v5):>12s} {fmt.format(change):>12s}")


print(f"\n{'='*90}")
print("ANSWERS")
print(f"{'='*90}")

# Q1
if result_5["vehicles"] < result_25["vehicles"]:
    diff = result_25["vehicles"] - result_5["vehicles"]
    print(f"\n1. Vehicle count: {result_25['vehicles']} -> {result_5['vehicles']}  (-{diff})")
    print("   YES - decreased")
elif result_5["vehicles"] == result_25["vehicles"]:
    print(f"\n1. Vehicle count: {result_25['vehicles']} (unchanged)")
else:
    print(f"\n1. Vehicle count: {result_25['vehicles']} -> {result_5['vehicles']} (INCREASED)")

# Q2
if result_5["utilization"] > result_25["utilization"]:
    print(f"2. Volume utilization: {result_25['utilization']:.1f}% -> {result_5['utilization']:.1f}%  (+{result_5['utilization']-result_25['utilization']:.1f}pp)")
    print("   YES - increased")
else:
    print(f"2. Volume utilization: {result_25['utilization']:.1f}% -> {result_5['utilization']:.1f}%")

# Q3 — Fuel & Fleet Cost
print(f"3. Total fuel score: {result_25['fuel_score']:.1f} -> {result_5['fuel_score']:.1f}")
if result_5["fuel_score"] <= result_25["fuel_score"]:
    print("   YES - fuel score decreased (more fuel-efficient fleet)")
else:
    print("   REVIEW - fuel score increased")
print(f"   Fleet cost:       {result_25['fleet_cost']:.1f} -> {result_5['fleet_cost']:.1f}")

# Q4 — Empty volume
print(f"4. Empty volume (m\u00b3): {result_25['empty_volume_m3']:.2f} -> {result_5['empty_volume_m3']:.2f}")
if result_5["empty_volume_m3"] <= result_25["empty_volume_m3"]:
    print("   YES - empty volume reduced")
else:
    print("   REVIEW - empty volume increased")

# Q5 — Cargo profile
print(f"5. Cargo profile:")
print(f"   Mean height diff (mm):  {result_25['height_variance']:.1f} -> {result_5['height_variance']:.1f}")
print(f"   Max height diff (mm):   {result_25['max_height_diff']:.1f} -> {result_5['max_height_diff']:.1f}")
print(f"   Staircase transitions:  {result_25['staircase_transitions']:.0f} -> {result_5['staircase_transitions']:.0f}")

# Q6 — Runtime
print(f"6. Planning time: {result_25['time_s']:.3f}s -> {result_5['time_s']:.3f}s")
print("   Acceptable" if result_5["time_s"] < 5 else "   Check performance")

# Q7 — Layout sanity
print(f"7. Layout sanity:")
print(f"   Non-stackable on floor: {result_25['ns_floor']} -> {result_5['ns_floor']} (should be >=)")
print(f"   Stackable on floor:    {result_25['s_floor']} -> {result_5['s_floor']} (should be <=)")
print(f"   Stack count:           {result_25['stacks']} -> {result_5['stacks']} (should be >=)")

ns_ok = result_5["ns_floor"] >= result_25["ns_floor"]
s_ok = result_5["s_floor"] <= result_25["s_floor"]
st_ok = result_5["stacks"] >= result_25["stacks"]
if ns_ok and s_ok and st_ok:
    print("   YES - layouts look sensible (non-stackable preserved, stackable moved up)")
else:
    issues = []
    if not ns_ok: issues.append("non-stackable lost floor access")
    if not s_ok: issues.append("more stackable on floor")
    if not st_ok: issues.append("fewer stacks")
    print(f"   REVIEW NEEDED: {', '.join(issues)}")

# Restore
scorer.SCORING_WEIGHTS["floor_contact"] = 10
