from dataclasses import dataclass, field
from typing import Optional
from .package import Package
from .placement import Placement
from .container import Container
from .geometry import AABB

SCORING_WEIGHTS = {
    "package_contact": 1000,
    "x_preference": 200,
    "floor_contact": 100,
    "y_balance": 50,
}


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


_FACE_TOLERANCE = 1.0


def _overlap_len(a1: float, a2: float, b1: float, b2: float) -> float:
    return max(0.0, min(a2, b2) - max(a1, b1))


def _overlap_2d(
    a1: tuple[float, float], a2: tuple[float, float],
    b1: tuple[float, float], b2: tuple[float, float],
) -> bool:
    return _overlap_len(a1[0], a1[1], a2[0], a2[1]) > 0 and \
           _overlap_len(b1[0], b1[1], b2[0], b2[1]) > 0


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


def _score_x_preference(aabb: AABB, container: Container) -> float:
    if container.length <= 0:
        return 0.0
    ratio = min(1.0, aabb.xmax / container.length)
    return max(0.0, 1.0 - ratio) ** 3


def _score_floor_contact(aabb: AABB) -> float:
    return 1.0 if aabb.zmin == 0 else 0.0


def _score_y_balance(aabb: AABB, package: Package, placements: list,
                     container: Container) -> float:
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
        "package_contact": _score_package_contact(aabb, others),
        "x_preference": _score_x_preference(aabb, container),
        "floor_contact": _score_floor_contact(aabb),
        "y_balance": _score_y_balance(aabb, package, placements, container),
    }

    breakdown = {}
    total = 0.0
    for key, raw_score in raw.items():
        sub = raw_score * weights.get(key, 0)
        breakdown[key] = sub
        total += sub

    if raw["package_contact"] < 0.1 and len(placements) > 0:
        warnings.append("Package is isolated from others")

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
        print(f"    {'total':20s} {total:.1f}")
        if warnings:
            print(f"    warnings: {warnings}")

    return PlacementScore(
        total=total,
        breakdown=breakdown,
        warnings=warnings,
        metadata=metadata,
    )
