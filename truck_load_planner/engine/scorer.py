from dataclasses import dataclass, field
from typing import Optional
from .package import Package
from .placement import Placement
from .container import Container
from .geometry import AABB

SCORING_WEIGHTS = {
    "floor_contact": 25,
    "wall_contact": 10,
    "package_contact": 15,
    "face_contact": 10,
    "compactness": 5,
    "stack_quality": 5,
    "vertical_stability": 10,
    "z_preference": 10,
    "x_preference": 5,
    "rear_proximity": 10,
    "y_balance": 15,
    "dead_space_quality": 10,
}

_FACE_TOLERANCE = 1.0


@dataclass
class PlacementScore:
    total: float = 0.0
    breakdown: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total": round(self.total, 1),
            "breakdown": {k: round(v, 1) for k, v in self.breakdown.items()},
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


def _make_aabb(package: Package, x: float, y: float, z: float,
               rotation: int = 0) -> AABB:
    return AABB.from_dimensions(
        x, y, z,
        package.length_mm,
        package.width_mm,
        package.height_mm,
        rotation,
    )


def _centroid(aabb: AABB) -> tuple[float, float, float]:
    return (
        (aabb.xmin + aabb.xmax) / 2,
        (aabb.ymin + aabb.ymax) / 2,
        (aabb.zmin + aabb.zmax) / 2,
    )


def _build_others(placements: list) -> list[AABB]:
    result = []
    for pl in placements:
        if pl.package is None:
            continue
        result.append(_make_aabb(pl.package, pl.x, pl.y, pl.z, pl.rotation))
    return result


# ── Scoring functions ─────────────────────────────────────────────────


def _score_floor_contact(aabb: AABB) -> float:
    return 1.0 if aabb.zmin == 0 else 0.0


def _score_wall_contact(aabb: AABB, container: Container) -> float:
    count = 0
    if aabb.xmin == 0:
        count += 1
    if aabb.xmax == container.length:
        count += 1
    if aabb.ymin == 0:
        count += 1
    if aabb.ymax == container.width:
        count += 1
    return min(count / 4.0, 1.0)


def _score_package_contact(aabb: AABB, others: list[AABB]) -> float:
    l = aabb.xmax - aabb.xmin
    w = aabb.ymax - aabb.ymin
    h = aabb.zmax - aabb.zmin
    max_possible = l * w + l * h + w * h
    if max_possible <= 0:
        return 0.0

    total_contact = 0.0
    for o in others:
        if abs(aabb.xmin - o.xmax) <= _FACE_TOLERANCE and _overlap_2d(
            (aabb.ymin, aabb.ymax), (o.ymin, o.ymax),
            (aabb.zmin, aabb.zmax), (o.zmin, o.zmax),
        ):
            dy = _overlap_len(aabb.ymin, aabb.ymax, o.ymin, o.ymax)
            dz = _overlap_len(aabb.zmin, aabb.zmax, o.zmin, o.zmax)
            total_contact += dy * dz

        if abs(aabb.xmax - o.xmin) <= _FACE_TOLERANCE and _overlap_2d(
            (aabb.ymin, aabb.ymax), (o.ymin, o.ymax),
            (aabb.zmin, aabb.zmax), (o.zmin, o.zmax),
        ):
            dy = _overlap_len(aabb.ymin, aabb.ymax, o.ymin, o.ymax)
            dz = _overlap_len(aabb.zmin, aabb.zmax, o.zmin, o.zmax)
            total_contact += dy * dz

        if abs(aabb.ymin - o.ymax) <= _FACE_TOLERANCE and _overlap_2d(
            (aabb.xmin, aabb.xmax), (o.xmin, o.xmax),
            (aabb.zmin, aabb.zmax), (o.zmin, o.zmax),
        ):
            dx = _overlap_len(aabb.xmin, aabb.xmax, o.xmin, o.xmax)
            dz = _overlap_len(aabb.zmin, aabb.zmax, o.zmin, o.zmax)
            total_contact += dx * dz

        if abs(aabb.ymax - o.ymin) <= _FACE_TOLERANCE and _overlap_2d(
            (aabb.xmin, aabb.xmax), (o.xmin, o.xmax),
            (aabb.zmin, aabb.zmax), (o.zmin, o.zmax),
        ):
            dx = _overlap_len(aabb.xmin, aabb.xmax, o.xmin, o.xmax)
            dz = _overlap_len(aabb.zmin, aabb.zmax, o.zmin, o.zmax)
            total_contact += dx * dz

        if abs(aabb.zmin - o.zmax) <= _FACE_TOLERANCE and _overlap_2d(
            (aabb.xmin, aabb.xmax), (o.xmin, o.xmax),
            (aabb.ymin, aabb.ymax), (o.ymin, o.ymax),
        ):
            dx = _overlap_len(aabb.xmin, aabb.xmax, o.xmin, o.xmax)
            dy = _overlap_len(aabb.ymin, aabb.ymax, o.ymin, o.ymax)
            total_contact += dx * dy

        if abs(aabb.zmax - o.zmin) <= _FACE_TOLERANCE and _overlap_2d(
            (aabb.xmin, aabb.xmax), (o.xmin, o.xmax),
            (aabb.ymin, aabb.ymax), (o.ymin, o.ymax),
        ):
            dx = _overlap_len(aabb.xmin, aabb.xmax, o.xmin, o.xmax)
            dy = _overlap_len(aabb.ymin, aabb.ymax, o.ymin, o.ymax)
            total_contact += dx * dy

    return min(total_contact / max_possible, 1.0)


def _overlap_len(a1: float, a2: float, b1: float, b2: float) -> float:
    return max(0.0, min(a2, b2) - max(a1, b1))


def _overlap_2d(
    a1: tuple[float, float], a2: tuple[float, float],
    b1: tuple[float, float], b2: tuple[float, float],
) -> bool:
    return _overlap_len(a1[0], a1[1], a2[0], a2[1]) > 0 and \
           _overlap_len(b1[0], b1[1], b2[0], b2[1]) > 0


def _score_face_contact(aabb: AABB, others: list[AABB],
                        container: Container) -> float:
    count = 0

    if aabb.zmin == 0:
        count += 1

    if aabb.xmin == 0 or aabb.xmax == container.length:
        count += 1

    if aabb.ymin == 0 or aabb.ymax == container.width:
        count += 1

    for o in others:
        if len(others) <= count:
            break
        if abs(aabb.xmin - o.xmax) <= _FACE_TOLERANCE:
            if _overlap_2d(
                (aabb.ymin, aabb.ymax), (o.ymin, o.ymax),
                (aabb.zmin, aabb.zmax), (o.zmin, o.zmax),
            ):
                count += 1

        if abs(aabb.xmax - o.xmin) <= _FACE_TOLERANCE:
            if _overlap_2d(
                (aabb.ymin, aabb.ymax), (o.ymin, o.ymax),
                (aabb.zmin, aabb.zmax), (o.zmin, o.zmax),
            ):
                count += 1

        if abs(aabb.ymin - o.ymax) <= _FACE_TOLERANCE:
            if _overlap_2d(
                (aabb.xmin, aabb.xmax), (o.xmin, o.xmax),
                (aabb.zmin, aabb.zmax), (o.zmin, o.zmax),
            ):
                count += 1

        if abs(aabb.ymax - o.ymin) <= _FACE_TOLERANCE:
            if _overlap_2d(
                (aabb.xmin, aabb.xmax), (o.xmin, o.xmax),
                (aabb.zmin, aabb.zmax), (o.zmin, o.zmax),
            ):
                count += 1

        if abs(aabb.zmin - o.zmax) <= _FACE_TOLERANCE:
            if _overlap_2d(
                (aabb.xmin, aabb.xmax), (o.xmin, o.xmax),
                (aabb.ymin, aabb.ymax), (o.ymin, o.ymax),
            ):
                count += 1

        if abs(aabb.zmax - o.zmin) <= _FACE_TOLERANCE:
            if _overlap_2d(
                (aabb.xmin, aabb.xmax), (o.xmin, o.xmax),
                (aabb.ymin, aabb.ymax), (o.ymin, o.ymax),
            ):
                count += 1

    return min(count / 6.0, 1.0)


def _score_compactness(aabb: AABB, others: list[AABB]) -> float:
    c = _centroid(aabb)
    min_dist = float("inf")
    for o in others:
        oc = _centroid(o)
        dist = ((c[0] - oc[0]) ** 2 +
                (c[1] - oc[1]) ** 2 +
                (c[2] - oc[2]) ** 2) ** 0.5
        if dist < min_dist:
            min_dist = dist

    if min_dist == float("inf"):
        return 0.0

    return max(0.0, 1.0 - min_dist / 2000.0)


def _score_stack_quality(aabb: AABB, others: list[AABB]) -> float:
    if aabb.zmin == 0:
        return 0.0

    area = (aabb.xmax - aabb.xmin) * (aabb.ymax - aabb.ymin)
    if area <= 0:
        return 0.0

    supported = 0.0
    for o in others:
        if abs(o.zmax - aabb.zmin) <= _FACE_TOLERANCE:
            supported += aabb.overlap_area_xy(o)

    return min(supported / area, 1.0)


def _score_vertical_stability(aabb: AABB, container: Container) -> float:
    if container.height <= 0:
        return 0.0
    mid_z = (aabb.zmin + aabb.zmax) / 2
    return max(0.0, 1.0 - mid_z / container.height)


def _score_z_preference(aabb: AABB, container: Container) -> float:
    if container.height <= 0:
        return 0.0
    return max(0.0, 1.0 - aabb.zmin / container.height)


def _score_x_preference(aabb: AABB, container: Container) -> float:
    """Reward positions closer to front wall (x=0) — innermost-to-door."""
    if container.length <= 0:
        return 0.0
    return max(0.0, 1.0 - aabb.xmin / container.length)


def _score_rear_proximity(aabb: AABB, container: Container) -> float:
    """Penalize packages near the rear door. 1.0 = far from door, 0.0 = at rear wall."""
    if container.length <= 0:
        return 0.0
    gap = container.length - aabb.xmax
    threshold = max(container.length * 0.08, 300.0)
    return min(1.0, gap / threshold)


def _score_y_balance(aabb: AABB, package: Package, placements: list,
                     container: Container) -> float:
    """Score how evenly the load is balanced left-to-right (Y axis).

    Computes the Y-center-of-gravity of all packages (existing + candidate)
    using actual package weight. Rewards positions that bring the COG
    closer to the container's Y-center (container.width / 2).
    """
    if container.width <= 0:
        return 0.0

    total_weight = package.weight_kg
    cy = (aabb.ymin + aabb.ymax) / 2
    weighted_y = cy * package.weight_kg

    for pl in placements:
        if pl.package is None:
            continue
        pkg = pl.package
        w = pkg.weight_kg
        if w <= 0:
            continue
        pkg_aabb = _make_aabb(pkg, pl.x, pl.y, pl.z, pl.rotation)
        weighted_y += ((pkg_aabb.ymin + pkg_aabb.ymax) / 2) * w
        total_weight += w

    if total_weight <= 0:
        return 0.0

    center_y = weighted_y / total_weight
    ideal = container.width / 2
    max_dist = container.width / 2
    dist = abs(center_y - ideal)
    return max(0.0, 1.0 - dist / max_dist)


def _score_dead_space_quality(
    aabb: AABB,
    container: Container,
    placements: list,
    remaining_packages: Optional[list] = None,
) -> float:
    """Score 0-1: how usable is the remaining free space for future packages.

    Delegates to the dead_space module. Returns 1.0 (no penalty) when
    there are no remaining packages or the module estimate is unavailable.
    """
    if remaining_packages is None:
        return 1.0
    if not remaining_packages:
        return 1.0
    from .dead_space import compute_dead_space_quality
    return compute_dead_space_quality(
        aabb, container, placements, remaining_packages,
    )


def score_placement(
    package: Package,
    x: float,
    y: float,
    z: float,
    rotation: int,
    placements: list,
    container: Container,
    debug: bool = False,
    remaining_packages: Optional[list] = None,
) -> PlacementScore:
    aabb = _make_aabb(package, x, y, z, rotation)
    others = _build_others(placements)
    weights = SCORING_WEIGHTS
    warnings: list[str] = []

    raw = {
        "floor_contact": _score_floor_contact(aabb),
        "wall_contact": _score_wall_contact(aabb, container),
        "package_contact": _score_package_contact(aabb, others),
        "face_contact": _score_face_contact(aabb, others, container),
        "compactness": _score_compactness(aabb, others),
        "stack_quality": _score_stack_quality(aabb, others),
        "vertical_stability": _score_vertical_stability(aabb, container),
        "z_preference": _score_z_preference(aabb, container),
        "x_preference": _score_x_preference(aabb, container),
        "rear_proximity": _score_rear_proximity(aabb, container),
        "y_balance": _score_y_balance(aabb, package, placements, container),
        "dead_space_quality": _score_dead_space_quality(
            aabb, container, placements, remaining_packages,
        ),
    }

    breakdown = {}
    total = 0.0
    for key, raw_score in raw.items():
        sub = raw_score * weights.get(key, 0)
        breakdown[key] = sub
        total += sub

    total = min(total, 100.0)

    if raw["compactness"] < 0.3 and len(placements) > 0:
        warnings.append("Package is isolated from others")
    if raw["vertical_stability"] < 0.3:
        warnings.append("Package placed high \u2014 may reduce load stability")
    if raw["stack_quality"] < 0.5 and aabb.zmin > 0:
        warnings.append("Low support percentage for stacked package")

    metadata = {
        "position": {"x": x, "y": y, "z": z},
        "rotation": rotation,
        "package_name": package.name,
        "neighbor_count": len(others),
    }

    if debug:
        print(f"\n  Score for '{package.name}' @ ({x:.0f}, {y:.0f}, {z:.0f})")
        for key in weights:
            print(f"    {key:20s} {raw[key]:5.2f} \u00d7 {weights[key]:2d} = {breakdown[key]:.1f}")
        print(f"    {'total':20s} {total:.1f} / 100")
        if warnings:
            print(f"    warnings: {warnings}")

    return PlacementScore(
        total=total,
        breakdown=breakdown,
        warnings=warnings,
        metadata=metadata,
    )
