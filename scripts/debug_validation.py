"""Debug why py3dbp placements fail validation."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from truck_load_planner.engine.package import Package
from truck_load_planner.engine.placement import Placement
from truck_load_planner.engine.container import Container
from truck_load_planner.engine.validation import validate_placement
from manual_test import _load_db, _build_engine_packages

vehicle_data = _load_db()
packages = _build_engine_packages()

v = vehicle_data[0]
container = Container(
    id=v.get("cc_id"),
    name=v.get("container_name", ""),
    length=float(v["cargo_length_mm"]),
    width=float(v["cargo_width_mm"]),
    height=float(v["cargo_height_mm"]),
    payload_kg=float(v["payload_kg"]),
)

pkg = packages[0]
print(f"Package: {pkg.name}")
print(f"  length_mm={pkg.length_mm}, width_mm={pkg.width_mm}, height_mm={pkg.height_mm}")
print(f"  weight_kg={pkg.weight_kg}, stackable={pkg.stackable}")
print(f"Container: L={container.length}, W={container.width}, H={container.height}, payload={container.payload_kg}")

result = validate_placement(
    [], pkg, 0.0, 0.0, 0.0, 0,
    container, [],
)
print(f"Validation result: valid={result.valid}")
if not result.valid:
    print(f"  Reasons: {result.reasons}")

# Debug with specific validators
from truck_load_planner.engine.geometry import AABB
from truck_load_planner.engine.boundary import check_boundary
from truck_load_planner.engine.weight import check_weight
from truck_load_planner.engine.support import check_support
from truck_load_planner.engine.access import check_door_fit, check_door_sweep

actual_aabb = AABB.from_dimensions(0, 0, 0, pkg.length_mm, pkg.width_mm, pkg.height_mm, 0, clearance=0)
container_aabb = AABB(0, 0, 0, container.length, container.width, container.height)

bresult = check_boundary(actual_aabb, container_aabb)
print(f"Boundary: pass={bresult['pass']}, errors={bresult['errors']}")

candidate_aabb = AABB.from_dimensions(0, 0, 0, pkg.length_mm, pkg.width_mm, pkg.height_mm, 0, clearance_xy=10.0, clearance_z=0.0)
wresult = check_weight([], container.payload_kg)
print(f"Weight: pass={wresult['pass']}")

fresult = check_door_fit(pkg, candidate_aabb, container, [], rotation=0)
print(f"Door fit: fits={fresult['fits']}")

# Support check at z=0
sresult = check_support([], actual_aabb, package=pkg)
print(f"Support: valid={sresult['valid']}")

# Door sweep
if fresult.get('fits'):
    doors_info = {
        "rear_door": {
            "width_mm": container.width,
            "height_mm": container.height,
        },
        "side_doors": [],
    }
    dresult = check_door_sweep([], pkg, candidate_aabb, container, doors_info, rotation=0)
    print(f"Door sweep: valid={dresult['valid']}, door_used={dresult.get('door_used')}")
