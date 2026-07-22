"""Debug statistics calculation."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from truck_load_planner.engines import get_engine

from manual_test import _load_db, _build_engine_packages

vehicle_data = _load_db()
packages = _build_engine_packages()

engine = get_engine("py3dbp")
result = engine.pack(vehicle_data, packages)

s = result.statistics
print(f"Statistics: {s}")
print(f"\nVehicles used: {s.get('vehicles_used')}")
print(f"Vehicle_placements keys: {list(result.vehicle_placements.keys())}")

total_pkg_vol = 0
for pl in result.placements:
    if pl.package:
        total_pkg_vol += pl.package.length_mm * pl.package.width_mm * pl.package.height_mm

print(f"\nTotal package volume placed: {total_pkg_vol / 1e9:.4f} m3")

for vid, pls in result.vehicle_placements.items():
    if not pls:
        continue
    c = result.vehicle_containers.get(vid)
    if c:
        print(f"\nVehicle {vid}:")
        print(f"  Container: {c.length}x{c.width}x{c.height}mm = {c.volume_m3:.2f} m3")
        print(f"  Packages: {len(pls)}")
        v = sum(p.package.length_mm * p.package.width_mm * p.package.height_mm for p in pls if p.package) / 1e9
        print(f"  Volume used: {v:.4f} m3")
        print(f"  Utilization: {v / c.volume_m3 * 100:.1f}%")
