"""Debug py3dbp mapping."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from truck_load_planner.engines.py3dbp.adapter import Py3dbpPackingEngine
from manual_test import _load_db, _build_engine_packages

vehicle_data = _load_db()
packages = _build_engine_packages()
print(f"Packages: {len(packages)}")
print(f"Vehicles: {len(vehicle_data)}")

v = vehicle_data[0]
print(f"\nFirst vehicle: id={v['vehicle_id']}, len={v['cargo_length_mm']}, wid={v['cargo_width_mm']}, hei={v['cargo_height_mm']}, payload={v['payload_kg']}")

for p in packages[:3]:
    print(f"Package: {p.name}, len={p.length_mm}, wid={p.width_mm}, hei={p.height_mm}, wt={p.weight_kg}")

from py3dbp import Packer, Bin, Item

packer = Packer()
packer.add_bin(Bin(
    str(v["vehicle_id"]),
    float(v["cargo_width_mm"]),
    float(v["cargo_height_mm"]),
    float(v["cargo_length_mm"]),
    float(v["payload_kg"]),
))
for p in packages:
    packer.add_item(Item(
        p.name,
        float(p.width_mm),
        float(p.height_mm),
        float(p.length_mm),
        float(p.weight_kg),
    ))

packer.pack(bigger_first=True, distribute_items=True, number_of_decimals=0)

for b in packer.bins:
    print(f"\nBin: {b.string()}")
    print(f"  Items placed: {len(b.items)}")
    for item in b.items:
        print(f"    {item.string()}")
    print(f"  Unfitted: {len(b.unfitted_items)}")
