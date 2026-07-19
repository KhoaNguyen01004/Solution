"""
Stateless candidate point generation.
Produces candidate positions from the current placement state.

Note: Planner now uses ``PlanningState`` with Extreme Points internally.
This function is kept as a standalone utility for external use or testing.
"""

from .container import Container
from .placement import Placement


def generate_candidate_points(
    placements: list,
    container: Container,
) -> list:
    """Generate all candidate points from current placements.

    Starts with (0,0,0) and adds the right/front/top corner
    of every placed package. Points outside the container are
    filtered out. Duplicates are removed.

    Returns:
        List of (x, y, z) tuples sorted by z, then x, then y.
    """
    points = {(0, 0, 0)}

    for pl in placements:
        pkg = pl.package
        if pkg is None:
            continue

        if pl.rotation in (90, 270):
            l_eff = pkg.width_mm
            w_eff = pkg.length_mm
        else:
            l_eff = pkg.length_mm
            w_eff = pkg.width_mm

        points.add((pl.x + l_eff, pl.y, pl.z))
        points.add((pl.x, pl.y + w_eff, pl.z))
        points.add((pl.x, pl.y, pl.z + pkg.height_mm))

    filtered = []
    for x, y, z in points:
        if (x <= container.length + 0.001
                and y <= container.width + 0.001
                and z <= container.height + 0.001):
            filtered.append((x, y, z))

    filtered.sort(key=lambda p: (p[2], p[0], p[1]))
    return filtered


def generate_slide_candidates(
    base_candidates: list,
    package,
    container,
) -> list[dict]:
    """Generate additional candidates by sliding base candidates in Y.

    When a package can't fit at any extreme-point position, try
    shifting it left/right in Y by small increments to squeeze it
    past obstacles. Returns expanded candidate dicts with rotation.

    Step size = max(50, package.clearance_mm). Tries up to 3 steps
    in each direction from each base candidate.
    """
    clearance = getattr(package, 'clearance_mm', 10)
    step = max(50, clearance)

    seen: set[tuple] = set()
    slide_origins: set[tuple[float, float, float]] = set()

    for pos in base_candidates:
        if isinstance(pos, dict):
            x, y, z = pos["x"], pos["y"], pos["z"]
        else:
            x, y, z = pos[0], pos[1], pos[2]

        # Try sliding left (decreasing Y) and right (increasing Y)
        for direction in (-1, 1):
            for i in range(1, 4):
                new_y = y + direction * i * step
                if new_y < 0:
                    break
                origin = (x, new_y, z)
                if origin not in seen:
                    seen.add(origin)
                    slide_origins.add(origin)

    # Filter by container Y bound
    rot_eff_w = {0: package.width_mm, 90: package.length_mm}
    filtered = []
    for x, y, z in slide_origins:
        for rot in (0, 90) if package.allow_rotation else (0,):
            eff_w = rot_eff_w[rot]
            if y + eff_w <= container.width + 0.001:
                key = (x, y, z, rot)
                if key not in seen:
                    seen.add(key)
                    filtered.append({"x": x, "y": y, "z": z, "rotation": rot})

    return filtered
