"""
Corrected benchmark — vinfo matches routes.py structure so that
_vehicle_capacity() sorts largest-first as intended.
"""
import sys, os, time, sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from truck_load_planner.engine.package import Package
from truck_load_planner.session import LoadPlanningSession
from truck_load_planner.models import ContainerConfig
from truck_load_planner.engine.distribution import distribute_across_vehicles
from truck_load_planner.engine.repair import optimize_layout, _count_stacks
import truck_load_planner.engine.distribution as dist_mod

PACKAGE_DEFS = [
    {"name": "AWC 30", "length": 650, "width": 430, "height": 450, "weight": 12.0, "stackable": True, "qty": 1},
    {"name": "AWC 30", "length": 420, "width": 150, "height": 420, "weight": 3.0, "stackable": True, "qty": 3},
    {"name": "AWS 315-4E", "length": 490, "width": 490, "height": 200, "weight": 6.4, "stackable": True, "qty": 1},
    {"name": "AWS 400-4E", "length": 600, "width": 600, "height": 240, "weight": 11.3, "stackable": True, "qty": 2},
    {"name": "AWS 450-4E", "length": 650, "width": 630, "height": 240, "weight": 12.5, "stackable": True, "qty": 1},
    {"name": "AWS 500-4E", "length": 710, "width": 700, "height": 260, "weight": 17.0, "stackable": True, "qty": 3},
    {"name": "AWS 560-4D", "length": 790, "width": 790, "height": 270, "weight": 21.5, "stackable": True, "qty": 2},
    {"name": "AWS 630-4D", "length": 870, "width": 870, "height": 260, "weight": 27.5, "stackable": True, "qty": 2},
    {"name": "DVS 1200", "length": 700, "width": 520, "height": 390, "weight": 24.0, "stackable": False, "qty": 1},
    {"name": "DVS 1900", "length": 700, "width": 520, "height": 390, "weight": 24.0, "stackable": False, "qty": 3},
    {"name": "DVS 3000", "length": 700, "width": 520, "height": 390, "weight": 26.0, "stackable": False, "qty": 1},
    {"name": "DVS 500", "length": 460, "width": 370, "height": 270, "weight": 8.0, "stackable": False, "qty": 1},
    {"name": "CDF 225-4", "length": 700, "width": 580, "height": 610, "weight": 42.0, "stackable": False, "qty": 1},
    {"name": "CDF 250-4", "length": 1220, "width": 680, "height": 620, "weight": 88.0, "stackable": False, "qty": 1},
    {"name": "CDF 250-4", "length": 1220, "width": 680, "height": 620, "weight": 88.0, "stackable": False, "qty": 1},
    {"name": "CDF 280-4", "length": 730, "width": 650, "height": 690, "weight": 47.0, "stackable": False, "qty": 1},
    {"name": "CDF 315-4", "length": 860, "width": 790, "height": 800, "weight": 67.0, "stackable": False, "qty": 1},
    {"name": "CDF 315-4", "length": 860, "width": 790, "height": 800, "weight": 67.0, "stackable": False, "qty": 1},
    {"name": "FCS 450C", "length": 1290, "width": 830, "height": 1030, "weight": 177.0, "stackable": False, "qty": 2},
    {"name": "FCS 500C", "length": 1390, "width": 930, "height": 1110, "weight": 216.0, "stackable": False, "qty": 2},
    {"name": "KBF 200F", "length": 1160, "width": 680, "height": 670, "weight": 83.0, "stackable": False, "qty": 1},
    {"name": "KBF 200R", "length": 1020, "width": 1010, "height": 730, "weight": 98.0, "stackable": False, "qty": 2},
    {"name": "KBF 280F", "length": 1310, "width": 850, "height": 860, "weight": 143.0, "stackable": False, "qty": 1},
    {"name": "KBF 280R", "length": 1190, "width": 1130, "height": 910, "weight": 144.0, "stackable": False, "qty": 1},
    {"name": "LC 1000-4/6TXA/20", "length": 980, "width": 1140, "height": 1200, "weight": 285.0, "stackable": False, "qty": 1},
    {"name": "LC 710-4/12B/10", "length": 730, "width": 840, "height": 860, "weight": 105.0, "stackable": False, "qty": 1},
    {"name": "LC 710-4/12B/22.5", "length": 730, "width": 840, "height": 860, "weight": 110.0, "stackable": False, "qty": 1},
    {"name": "LC 800-4/12TXA/17.5", "length": 930, "width": 930, "height": 840, "weight": 146.0, "stackable": False, "qty": 1},
    {"name": "LC 900-4/6TXA/22.5", "length": 940, "width": 1060, "height": 1110, "weight": 200.0, "stackable": False, "qty": 2},
    {"name": "LC 900-4/6TXA/25", "length": 940, "width": 1060, "height": 1110, "weight": 200.0, "stackable": False, "qty": 1},
    {"name": "LC 900-4/6TXA/27.5", "length": 940, "width": 1060, "height": 1110, "weight": 245.0, "stackable": False, "qty": 3},
]

def build_packages(defs):
    pkgs = []
    next_id = 1
    for d in defs:
        for _ in range(d["qty"]):
            pkgs.append(Package(id=next_id, name=d["name"],
                length_mm=d["length"], width_mm=d["width"], height_mm=d["height"],
                weight_kg=d["weight"], stackable=d["stackable"], allow_rotation=True))
            next_id += 1
    return pkgs

def build_vehicle_sessions(db_path):
    """Build sessions with vinfo matching routes.py structure."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT v.id AS vehicle_id, v.plate_number, v.vehicle_type,
               cc.id AS cc_id, cc.name AS container_name,
               cc.cargo_length_mm, cc.cargo_width_mm, cc.cargo_height_mm, cc.payload_kg
        FROM vehicles v
        INNER JOIN container_configs cc ON cc.id = v.container_config_id
        ORDER BY v.plate_number
    """)
    vrows = c.fetchall()
    conn.close()
    result = []
    seen_cc = set()
    for vr in vrows:
        vinfo = dict(vr)
        session = LoadPlanningSession()
        cc = ContainerConfig(id=vr["cc_id"], name=vr["container_name"],
            cargo_length_mm=vr["cargo_length_mm"], cargo_width_mm=vr["cargo_width_mm"],
            cargo_height_mm=vr["cargo_height_mm"], payload_kg=vr["payload_kg"])
        session.select_container(cc)
        session.vehicle_id = vr["vehicle_id"]
        result.append((vinfo, session))
    return result

def compute_capacity(vinfo):
    vol = (vinfo.get("cargo_length_mm",0) * vinfo.get("cargo_width_mm",0) * vinfo.get("cargo_height_mm",0))
    return vol * max(vinfo.get("payload_kg",0), 1)

def count_active(sessions):
    return sum(1 for _, s in sessions if len(s._planner.placements) > 0)

def print_vehicle_allocation(label, vehicle_sessions):
    print(f"\n  Vehicle allocation for {label}:")
    for vinfo, session in vehicle_sessions:
        pls = session._planner.placements
        if not pls:
            continue
        cont = session._planner.container
        stacks = sum(1 for pl in pls if pl.z > 0.001)
        pkg_names = list(dict.fromkeys(pl.package.name for pl in pls if pl.package))
        vol_m3 = cont.length * cont.width * cont.height / 1e9
        print(f"    V{vinfo['vehicle_id']} {vinfo.get('plate_number','?'):>8s} "
              f"{cont.length:.0f}x{cont.width:.0f}x{cont.height:.0f}mm "
              f"({vol_m3:.1f}m3) -> {len(pls)} pkgs, {stacks} stacks")
        # Show first 3 package names
        shown = set()
        for n in pkg_names[:5]:
            shown.add(n)
            print(f"      - {n}")
        if len(pkg_names) > 5:
            print(f"      ... and {len(pkg_names)-5} more")

def run_one(label, packages, db_path, rearrangement_on, repair_on):
    vehicle_sessions = build_vehicle_sessions(db_path)
    pkgs = list(packages)

    # Print vehicle availability and order
    sorted_vs = sorted(vehicle_sessions, key=lambda vs: -compute_capacity(vs[0]))
    print(f"\n  Vehicles available (sorted by capacity): {len(sorted_vs)}")
    for vinfo, session in sorted_vs[:10]:
        cap = compute_capacity(vinfo)
        cont = session._planner.container
        vol = cont.length * cont.width * cont.height / 1e9
        print(f"    V{vinfo['vehicle_id']} {vinfo.get('plate_number','?'):>8s} "
              f"{cont.length:.0f}x{cont.width:.0f}x{cont.height:.0f}mm "
              f"({vol:.1f}m3) cap_idx={cap:.1e}")

    # Toggle rearrangement
    if not rearrangement_on:
        orig = dist_mod._try_local_rearrangement
        dist_mod._try_local_rearrangement = lambda *a, **kw: False

    t0 = time.perf_counter()
    placed, failed, unplaced, _, _ = distribute_across_vehicles(pkgs, vehicle_sessions, debug=False)
    dist_time = time.perf_counter() - t0

    stacks, _ = _count_stacks(vehicle_sessions)
    active = count_active(vehicle_sessions)

    if not rearrangement_on:
        dist_mod._try_local_rearrangement = orig

    print_vehicle_allocation(label, vehicle_sessions)

    repair_time = 0.0
    improved = False

    if repair_on:
        unplaced_pkgs = [p for p in pkgs if p.name in unplaced]
        t0 = time.perf_counter()
        result_sessions, improved = optimize_layout(
            vehicle_sessions, pkgs,
            unplaced_packages=unplaced_pkgs,
            max_passes=3, debug=False,
        )
        repair_time = time.perf_counter() - t0
        final_stacks, _ = _count_stacks(result_sessions)
        stacks = final_stacks

    total_time = dist_time + repair_time

    print(f"\n  {label}:")
    print(f"    Rearrangement: {'ON' if rearrangement_on else 'OFF'}  "
          f"Repair: {'ON' if repair_on else 'OFF'}")
    print(f"    Distribution: {dist_time:.3f}s  Repair: {repair_time:.3f}s  "
          f"Total: {total_time:.3f}s ({total_time/60:.1f} min)")
    print(f"    Vehicles: {active}  Placed: {placed}  Stacks: {stacks}")
    if repair_on:
        print(f"    Improved: {improved}")
    return dist_time, repair_time, total_time, active, placed, stacks, improved


db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "routing_system.db")
packages = build_packages(PACKAGE_DEFS)

print(f"Packages: {len(packages)} (from {len(PACKAGE_DEFS)} definitions with qty)")
print(f"\n{'='*60}")
print(f"  First: vehicle availability (same for all runs)")
print(f"{'='*60}")

# Run A
run_one("Run A (Baseline)", packages, db_path, rearrangement_on=False, repair_on=False)
print(f"\n{'='*60}")

# Run B
run_one("Run B", packages, db_path, rearrangement_on=True, repair_on=False)
print(f"\n{'='*60}")

# Run C
run_one("Run C (Current)", packages, db_path, rearrangement_on=True, repair_on=True)
