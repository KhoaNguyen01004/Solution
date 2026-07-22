from .container import Container
from .placement import Placement


def generate_candidate_points(
    placements: list,
    container: Container,
) -> list:
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


def tighten_position(
    planner,
    pkg,
    x: float,
    y: float,
    z: float,
    rotation: int,
    step: float = 200.0,
) -> tuple[float, float, float, int]:
    h_clr = getattr(pkg, 'horizontal_clearance_mm', 10.0)
    step = max(step, h_clr)

    best_x, best_y, best_z, best_rot = x, y, z, rotation

    for _ in range(50):
        while best_x > 0:
            tx = max(best_x - step, 0)
            if planner.validate_position(pkg, tx, best_y, best_z, best_rot).valid:
                best_x = tx
            else:
                break

        if best_x == 0:
            break

        found_advance = False
        if pkg.allow_rotation:
            try_rot = 0 if best_rot == 90 else 90
            if planner.validate_position(pkg, best_x, best_y, best_z, try_rot).valid:
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
                    continue

        if not found_advance:
            break

    return best_x, best_y, best_z, best_rot


def generate_floor_anchors(
    placements: list,
    container: Container,
    package,
    max_regions: int = 2,
) -> list[tuple[float, float, float]]:
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
