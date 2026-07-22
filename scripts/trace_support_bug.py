"""
Trace every Placement mutation to identify the source of the
support-integrity bug.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from truck_load_planner.engine.package import Package
from truck_load_planner.engine.container import Container
from truck_load_planner.engine.planner import Planner
from truck_load_planner.engine.trace_mutations import M
from truck_load_planner.engine.geometry import AABB
from truck_load_planner.engine.support import check_support

M.reset()

container = Container(
    id=1, name="Test Container",
    length=5000, width=2500, height=2200, payload_kg=10000,
)

packages = [
    # Big base — forces stacking on top
    Package(id=1, name="BASE_A", length_mm=1200, width_mm=1000,
            height_mm=500, weight_kg=300, stackable=True, allow_rotation=True),
    Package(id=2, name="BASE_B", length_mm=1200, width_mm=1000,
            height_mm=500, weight_kg=300, stackable=True, allow_rotation=True),
    Package(id=3, name="STACK_1", length_mm=800, width_mm=600,
            height_mm=400, weight_kg=100, stackable=True, allow_rotation=True),
    Package(id=4, name="STACK_2", length_mm=800, width_mm=600,
            height_mm=400, weight_kg=100, stackable=True, allow_rotation=True),
    Package(id=5, name="STACK_3", length_mm=600, width_mm=400,
            height_mm=300, weight_kg=50, stackable=True, allow_rotation=True),
    Package(id=6, name="STACK_4", length_mm=600, width_mm=400,
            height_mm=300, weight_kg=50, stackable=True, allow_rotation=True),
    Package(id=7, name="FILL_A", length_mm=1400, width_mm=1000,
            height_mm=600, weight_kg=400, stackable=False, allow_rotation=True),
    Package(id=8, name="FILL_B", length_mm=1400, width_mm=1000,
            height_mm=600, weight_kg=400, stackable=False, allow_rotation=True),
    Package(id=9, name="TOP_1", length_mm=800, width_mm=600,
            height_mm=400, weight_kg=80, stackable=True, allow_rotation=True),
    Package(id=10, name="TOP_2", length_mm=800, width_mm=600,
            height_mm=400, weight_kg=80, stackable=True, allow_rotation=True),
]

print(f"Packages: {len(packages)}")
for p in packages:
    print(f"  {p.name}: {p.length_mm}x{p.width_mm}x{p.height_mm} {p.weight_kg}kg stack={p.stackable}")

planner = Planner(container, candidate_limit=80)

print("\n=== Running auto_arrange (largest_first) ===")
sys.stdout.flush()
result = planner.auto_arrange(packages, strategy="largest_first", debug=False)
sys.stdout.flush()
print(f"Placed: {result.placed_packages}, Failed: {result.failed_packages}")
print(f"Utilization: {result.utilization:.1f}%, Score: {result.total_score}")

# ── Support integrity check ─────────────────────────────────────────
print("\n=== Support Integrity Check ===")
unsupported = []
for pl in planner.placements:
    if pl.package is None:
        continue
    uid = getattr(pl, '_uid', -1)
    if pl.z < 0.001:
        print(f"  FLOOR: uid={uid} '{pl.package.name}' @ ({pl.x:.0f},{pl.y:.0f},{pl.z:.0f})")
        continue
    aabb = AABB.from_dimensions(
        pl.x, pl.y, pl.z,
        pl.package.length_mm, pl.package.width_mm, pl.package.height_mm,
        pl.rotation, clearance=0,
    )
    sresult = check_support(planner.placements, aabb, package=pl.package, support_threshold=0.50)
    if not sresult["valid"]:
        unsupported.append((uid, pl.package.name, pl.x, pl.y, pl.z, sresult["reasons"]))
        print(f"  *** UNSUPPORTED: uid={uid} '{pl.package.name}' @ "
              f"({pl.x:.0f},{pl.y:.0f},{pl.z:.0f}) — {sresult['reasons']}")
    else:
        print(f"  OK: uid={uid} '{pl.package.name}' @ ({pl.x:.0f},{pl.y:.0f},{pl.z:.0f})")

if unsupported:
    for uid, name, *_ in unsupported:
        print(f"\n>>> TRACE for '{name}' (last uid={uid}):")
        M.dump_for(name)
else:
    print("\nAll packages have valid support.")

print("\n========== FULL TRACE ==========")
M.dump_all()
