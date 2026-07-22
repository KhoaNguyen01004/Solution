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
    """Generate additional candidates by sliding base candidates in X, Y, and Z.

    When a package can't fit at any extreme-point position, try
    shifting it in all three axes by small increments to squeeze it
    past obstacles.

    Strategy:
      1. Y-slide (left/right) — original behavior
      2. X-slide (front/rear) — push deeper into container or pull back
      3. Z-slide (up/down) — try alternative stacking heights
      4. Combined X+Y slides for diagonal nudging

    Step size = max(50, horizontal_clearance_mm).  Tries up to 3 steps
    in each direction from each base candidate.
    """
    h_clr = getattr(package, 'horizontal_clearance_mm', 10.0)
    step = max(50, h_clr)

    seen: set[tuple] = set()
    slide_origins: set[tuple[float, float, float]] = set()

    def _try_origin(ox, oy, oz):
        if oy < 0:
            return
        interior = (ox >= 0 and oy >= 0 and oz >= 0)
        if not interior:
            return
        key = (ox, oy, oz)
        if key not in seen:
            seen.add(key)
            slide_origins.add(key)

    for pos in base_candidates:
        if isinstance(pos, dict):
            bx, by, bz = pos["x"], pos["y"], pos["z"]
        else:
            bx, by, bz = pos[0], pos[1], pos[2]

        # ── Y-slide (left/right) ────────────────────────────────────
        for direction in (-1, 1):
            for i in range(1, 4):
                _try_origin(bx, by + direction * i * step, bz)

        # ── X-slide (front/rear) ────────────────────────────────────
        for direction in (-1, 1):
            for i in range(1, 4):
                _try_origin(bx + direction * i * step, by, bz)

        # ── Z-slide (up/down)  ──────────────────────────────────────
        for direction in (-1, 1):
            for i in range(1, 3):
                _try_origin(bx, by, bz + direction * i * step)

        # ── Combined X+Y (diagonal) ─────────────────────────────────
        for xi in range(1, 3):
            for yi in range(1, 3):
                for dx in (-1, 1):
                    for dy in (-1, 1):
                        _try_origin(bx + dx * xi * step,
                                    by + dy * yi * step, bz)

    # Filter by container bounds
    rot_eff_w = {0: package.width_mm, 90: package.length_mm}
    rot_eff_l = {0: package.length_mm, 90: package.width_mm}
    filtered = []
    for ox, oy, oz in slide_origins:
        for rot in (0, 90) if package.allow_rotation else (0,):
            eff_w = rot_eff_w[rot]
            eff_l = rot_eff_l[rot]
            if (ox + eff_l <= container.length + 0.001
                    and oy + eff_w <= container.width + 0.001
                    and oz + package.height_mm <= container.height + 0.001):
                key = (ox, oy, oz, rot)
                if key not in seen:
                    seen.add(key)
                    filtered.append({"x": ox, "y": oy, "z": oz, "rotation": rot})

    return filtered


def settle_package(
    planner,
    pkg,
    x: float,
    y: float,
    z: float,
    rotation: int,
) -> tuple[float, float, float, int]:
    """Analytically find the tightest -X position for a package.

    Scans nearby packages via the spatial index and computes the exact
    stopping X as max(blocker.x + blocker_length + combined_clearance)
    over all packages whose Y and Z intervals (with clearance) overlap
    the candidate. One O(K) pass via spatial index, K = nearby packages.

    **Use as a tightening step on an already-valid extreme-point candidate,
    NOT as a standalone candidate generator.**  Sequential X-then-Y settling
    is a heuristic that may miss L-shaped corners that the extreme-point
    enumeration already handles.

    The caller must process packages in ascending X order to guarantee
    that by the time package P is settled, every package that could
    block it has already reached its own final position (single-pass
    convergence for compact_placements).

    Args:
        planner: Planner instance (provides spatial index + validation).
        pkg: Package being tightened.
        x, y, z, rotation: Current valid candidate position.

    Returns:
        (tight_x, y, z, rotation) with tight_x ≤ x, or the original
        position if the analytically-computed position fails validation.
    """
    from .geometry import AABB

    container = planner.container
    h_clr = getattr(pkg, 'horizontal_clearance_mm', 10.0)
    v_clr = getattr(pkg, 'vertical_clearance_mm', 0.0)

    if rotation in (90, 270):
        dx, dy = pkg.width_mm, pkg.length_mm
    else:
        dx, dy = pkg.length_mm, pkg.width_mm
    dz = pkg.height_mm

    # Inflated bounds of the candidate package (as used in collision check)
    pkg_inf_ymin = y - h_clr
    pkg_inf_ymax = y + dy + h_clr
    pkg_inf_zmin = z - v_clr
    pkg_inf_zmax = z + dz + v_clr

    # Probe: span the package's inflated Y/Z band, from wall to current X.
    # The spatial index uses inflated (clearance-expanded) AABBs, so any
    # blocker whose inflated AABB falls in this probe is a candidate.
    probe = AABB(
        -1.0,
        pkg_inf_ymin - 1.0,
        pkg_inf_zmin - 1.0,
        x + dx + 1.0,
        pkg_inf_ymax + 1.0,
        pkg_inf_zmax + 1.0,
    )

    tight_x = 0.0  # default: front wall

    try:
        nearby = planner.state.query_aabb(probe)
    except Exception:
        nearby = [(pl, None) for pl in planner.placements]

    for bl_pl, _ in nearby:
        bp = bl_pl.package
        if bp is None:
            continue

        b_h_clr = getattr(bp, 'horizontal_clearance_mm', 10.0)
        b_v_clr = getattr(bp, 'vertical_clearance_mm', 0.0)

        if bl_pl.rotation in (90, 270):
            bdx, bdy = bp.width_mm, bp.length_mm
        else:
            bdx, bdy = bp.length_mm, bp.width_mm
        bdz = bp.height_mm

        # Blocker's inflated bounds (same as stored in spatial index)
        bl_inf_ymin = bl_pl.y - b_h_clr
        bl_inf_ymax = bl_pl.y + bdy + b_h_clr
        bl_inf_zmin = bl_pl.z - b_v_clr
        bl_inf_zmax = bl_pl.z + bdz + b_v_clr

        # No Y overlap between inflated bounds → not a blocker in X
        if pkg_inf_ymax <= bl_inf_ymin or pkg_inf_ymin >= bl_inf_ymax:
            continue

        # No Z overlap → not a blocker in X
        if pkg_inf_zmax <= bl_inf_zmin or pkg_inf_zmin >= bl_inf_zmax:
            continue

        # This blocker constrains -X movement.
        # Minimum tight_x so that inflated candidate xmin ≥ blocker inflated xmax:
        #   (tight_x - h_clr) ≥ (bl_pl.x + bdx + b_h_clr)
        #   tight_x ≥ bl_pl.x + bdx + b_h_clr + h_clr
        candidate_x = bl_pl.x + bdx + b_h_clr + h_clr
        if candidate_x > tight_x:
            tight_x = candidate_x

    # Clamp to container bounds (package must fit entirely inside)
    tight_x = max(0.0, min(tight_x, container.length - dx))

    # No improvement — return quickly without validation overhead
    if tight_x >= x - 0.1:
        return x, y, z, rotation

    # Final validation handles support, door sweep, and any edge cases
    # the analytical scan may miss (e.g., partial-overlap support rules).
    if planner.validate_position(pkg, tight_x, y, z, rotation).valid:
        return tight_x, y, z, rotation

    # Fallback: analytical position failed validation; keep original
    return x, y, z, rotation


def tighten_position(
    planner,
    pkg,
    x: float,
    y: float,
    z: float,
    rotation: int,
    step: float = 200.0,
) -> tuple[float, float, float, int]:
    """Settle a package into the tightest possible position via step-iteration.

    Pushes a package as far as it can go toward the front (-X) until it
    contacts other packages or container walls. When blocked, tries:

      1. Alternate rotation (0° ↔ 90°) to squeeze past obstacles.
      2. Y-sweep (left/right) at current rotation and alternate rotation.
      3. Z-lift (up/down) combined with Y-sweep and rotation changes.

    This produces dense packs that real warehouse workers would achieve
    by nudging, rotating, and shifting packages into the tightest spot.

    Prefer ``settle_package`` for post-placement compaction (faster, exact
    on the X axis).  Use this function when you need Y-sweep or Z-lift
    exploration (initial candidate evaluation, slide fallback).

    Args:
        planner: Planner instance (for validate_position).
        pkg: The package being placed.
        x, y, z, rotation: Current valid position.
        step: Step size in mm (default 200; reduce for finer tightening).

    Returns:
        (tight_x, tight_y, tight_z, rotation) — settled position.
    """
    h_clr = getattr(pkg, 'horizontal_clearance_mm', 10.0)
    step = max(step, h_clr)

    best_x, best_y, best_z, best_rot = x, y, z, rotation
    container = planner.container

    rotations_to_try = [rotation]
    if pkg.allow_rotation:
        rotations_to_try.append(0 if rotation == 90 else 90)

    # ── Primary loop: sprint -X, try rot / Y / Z when blocked ──
    for _ in range(50):
        # Sprint -X as far as possible with current rotation
        while best_x > 0:
            tx = max(best_x - step, 0)
            if planner.validate_position(pkg, tx, best_y, best_z, best_rot).valid:
                best_x = tx
            else:
                break

        if best_x == 0:
            break

        # Blocked in -X: try alternate rotation
        found_advance = False
        for try_rot in rotations_to_try:
            if try_rot == best_rot:
                continue
            if not planner.validate_position(pkg, best_x, best_y, best_z, try_rot).valid:
                continue
            tx = best_x
            while tx > 0:
                tx2 = max(tx - step, 0)
                if planner.validate_position(pkg, tx2, best_y, best_z, try_rot).valid:
                    tx = tx2
                else:
                    break
            if tx < best_x:
                best_x = tx
                best_rot = try_rot
                found_advance = True
                break

        if found_advance:
            continue

        # Still blocked: sweep Y with each rotation
        best_sweep_x = best_x
        best_sweep_y = best_y
        best_sweep_rot = best_rot
        found_sweep = False

        for try_rot in rotations_to_try:
            pkg_w_rot = pkg.width_mm if try_rot == 0 else pkg.length_mm
            max_y_rot = container.width - pkg_w_rot

            test_y = 0.0
            while test_y <= max_y_rot + 0.001:
                if abs(test_y - best_y) < 1.0 and try_rot == best_rot:
                    test_y += step
                    continue
                if not planner.validate_position(pkg, best_x, test_y, best_z, try_rot).valid:
                    test_y += step
                    continue
                tx = best_x
                while tx > 0:
                    tx2 = max(tx - step, 0)
                    if planner.validate_position(pkg, tx2, test_y, best_z, try_rot).valid:
                        tx = tx2
                    else:
                        break
                if tx < best_sweep_x:
                    best_sweep_x = tx
                    best_sweep_y = test_y
                    best_sweep_rot = try_rot
                    found_sweep = True
                test_y += step

        if found_sweep:
            best_x = best_sweep_x
            best_y = best_sweep_y
            best_rot = best_sweep_rot
            continue

        # Still blocked: try Z lift with each rotation + Y sweep
        best_lift_x = best_x
        best_lift_y = best_y
        best_lift_z = best_z
        best_lift_rot = best_rot
        found_lift = False

        for try_rot in rotations_to_try:
            pkg_w_rot = pkg.width_mm if try_rot == 0 else pkg.length_mm
            max_y_rot = container.width - pkg_w_rot

            for dz_dir in (-1, 1):
                for zi in range(1, 4):
                    tz = best_z + dz_dir * zi * step
                    if tz < 0 or tz + pkg.height_mm > container.height:
                        continue
                    if abs(tz - best_z) < 0.001:
                        continue

                    test_y = 0.0
                    while test_y <= max_y_rot + 0.001:
                        if not planner.validate_position(pkg, best_x, test_y, tz, try_rot).valid:
                            test_y += step
                            continue
                        tx = best_x
                        while tx > 0:
                            tx2 = max(tx - step, 0)
                            if planner.validate_position(pkg, tx2, test_y, tz, try_rot).valid:
                                tx = tx2
                            else:
                                break
                        if tx < best_lift_x:
                            best_lift_x = tx
                            best_lift_y = test_y
                            best_lift_z = tz
                            best_lift_rot = try_rot
                            found_lift = True
                        test_y += step

        if found_lift:
            best_x = best_lift_x
            best_y = best_lift_y
            best_z = best_lift_z
            best_rot = best_lift_rot
        else:
            break

    # ── Secondary: settle -Y (left wall) and -Z (floor) ──────────
    for _ in range(20):
        improved = False

        while best_y > 0:
            ty = max(best_y - step, 0)
            if planner.validate_position(pkg, best_x, ty, best_z, best_rot).valid:
                best_y = ty
                improved = True
            else:
                break

        while best_z > 0:
            tz = max(best_z - step, 0)
            if planner.validate_position(pkg, best_x, best_y, tz, best_rot).valid:
                best_z = tz
                improved = True
            else:
                break

        if not improved:
            break

    return best_x, best_y, best_z, best_rot


def generate_floor_anchors(
    placements: list,
    container: Container,
    package,
    max_regions: int = 2,
) -> list[tuple[float, float, float]]:
    """Generate candidate positions at the largest empty floor regions.

    Sweeps Y-boundaries of all floor-package footprints to find empty
    axis-aligned rectangles. For each of the top N largest regions,
    generates representative (x, y, 0) positions:
      - front-left corner (lowest x and y in the region)
      - center (if the region is large enough to distinguish it)
      - rear-left (if the region is long enough)

    Always returns positions with z=0 (floor level).

    Args:
        placements: List of Placement objects currently placed.
        container: Container being loaded.
        package: Package being placed (for footprint dimensions).
        max_regions: Maximum number of empty regions to use.

    Returns:
        List of (x, y, 0) tuples, deduplicated and sorted by region area.
    """
    footprints = []
    for pl in placements:
        pkg = pl.package
        if pkg is None or pl.z > 0:
            continue
        l = pkg.length_mm if pl.rotation in (0, 180) else pkg.width_mm
        w = pkg.width_mm if pl.rotation in (0, 180) else pkg.length_mm
        footprints.append((pl.x, pl.x + l, pl.y, pl.y + w))

    y_coords = {0.0, container.width}
    for _, _, ymin, ymax in footprints:
        y_coords.add(ymin)
        y_coords.add(ymax)
    y_coords = sorted(y_coords)

    regions = []
    for i in range(len(y_coords) - 1):
        y_low, y_high = y_coords[i], y_coords[i + 1]
        height = y_high - y_low
        if height < 1.0:
            continue
        x_intervals = [(0.0, container.length)]
        for fxmin, fxmax, fymin, fymax in footprints:
            if fymax <= y_low or fymin >= y_high:
                continue
            trimmed = []
            for xl, xr in x_intervals:
                if fxmax <= xl or fxmin >= xr:
                    trimmed.append((xl, xr))
                else:
                    if xl < fxmin:
                        trimmed.append((xl, fxmin))
                    if fxmax < xr:
                        trimmed.append((fxmax, xr))
            x_intervals = trimmed
        for xl, xr in x_intervals:
            width = xr - xl
            if width < 1.0 or height < 1.0:
                continue
            regions.append((width * height, xl, xr, y_low, y_high))

    regions.sort(key=lambda r: -r[0])

    pkg_l = package.length_mm
    pkg_w = package.width_mm
    candidates = []
    seen = set()
    MARGIN = 1.0

    for _, xl, xr, yl, yr in regions[:max_regions]:
        rw = xr - xl
        rh = yr - yl

        if rw < pkg_l - MARGIN or rh < pkg_w - MARGIN:
            continue

        pos = (xl, yl, 0.0)
        if pos not in seen:
            seen.add(pos)
            candidates.append(pos)

        if rw > pkg_l * 1.5 + MARGIN and rh > pkg_w * 1.5 + MARGIN:
            cx = xl + (rw - pkg_l) / 2
            cy = yl + (rh - pkg_w) / 2
            pos = (cx, cy, 0.0)
            if pos not in seen:
                seen.add(pos)
                candidates.append(pos)

        if rw > pkg_l * 1.5 + MARGIN:
            rx = xr - pkg_l
            pos = (rx, yl, 0.0)
            if pos not in seen:
                seen.add(pos)
                candidates.append(pos)

    return candidates
