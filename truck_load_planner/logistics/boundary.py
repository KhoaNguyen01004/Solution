"""
Boundary validation — checks if a package fits inside the truck container.
"""

from truck_load_planner.geometry.aabb import AABB


def check_boundary(package_aabb: AABB, truck_aabb: AABB) -> dict:
    """Check if package AABB is fully inside the truck AABB.

    Returns:
        {"pass": True} or {"pass": False, "errors": [...]}
    """
    if truck_aabb.contains(package_aabb):
        return {"pass": True}
    errors = []
    if package_aabb.xmin < truck_aabb.xmin:
        errors.append("Package extends beyond front wall")
    if package_aabb.xmax > truck_aabb.xmax:
        errors.append("Package extends beyond rear wall")
    if package_aabb.ymin < truck_aabb.ymin:
        errors.append("Package extends beyond left wall")
    if package_aabb.ymax > truck_aabb.ymax:
        errors.append("Package extends beyond right wall")
    if package_aabb.zmin < truck_aabb.zmin:
        errors.append("Package extends below floor")
    if package_aabb.zmax > truck_aabb.zmax:
        errors.append("Package exceeds cargo height")
    return {"pass": False, "errors": errors}
