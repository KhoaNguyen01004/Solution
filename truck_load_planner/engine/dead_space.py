"""
Dead Space Quality — estimates how much remaining free space around a
candidate placement remains usable for future packages.

Design:
  For each exposed face, measure the gap distance to the nearest obstacle
  (package or container wall). Uses the spatial index (if available) to
  limit the search to nearby packages. Scores each gap continuously by
  comparing sorted dimensions against the hardest remaining packages.
  Returns a 0-1 quality score integrated as a normal scoring category.

Complexity: O(faces x reference_set_size) ~ O(1) per candidate.
  With spatial index: O(faces x nearby_candidates) instead of O(N).
"""

from typing import Optional, Callable
from .package import Package
from .geometry import AABB
from .container import Container

DEAD_SPACE_WEIGHT = 10
MIN_GAP_MM = 10.0
REFERENCE_SET_SIZE = 3


def _build_actual_aabb(package, x, y, z, rotation):
    return AABB.from_dimensions(
        x, y, z,
        package.length_mm,
        package.width_mm,
        package.height_mm,
        rotation,
        clearance=0,
    )


def _select_hardest(packages, n):
    """Select the n hardest-to-place remaining packages.

    Returns list of (difficulty, package) tuples sorted descending.
    "Hard" = large volume x extreme aspect ratio.
    Kept isolated for easy refinement later.
    """
    if not packages:
        return []

    scored = []
    for pkg in packages:
        vol = pkg.length_mm * pkg.width_mm * pkg.height_mm
        if vol <= 0:
            continue
        max_dim = max(pkg.length_mm, pkg.width_mm, pkg.height_mm)
        min_dim = max(min(pkg.length_mm, pkg.width_mm, pkg.height_mm), 1.0)
        aspect = max_dim / min_dim
        difficulty = vol * aspect
        scored.append((difficulty, pkg))

    scored.sort(key=lambda x: -x[0])
    return scored[:n]


def _build_probe(aabb, direction, container):
    """Build a thin AABB from the face outward to the container wall.

    Used with the spatial index to find only packages that intersect
    the space in front of/behind/beside a face.
    """
    tol = 1.0
    if direction == '-x':
        return AABB(-tol, aabb.ymin - tol, aabb.zmin - tol,
                     aabb.xmin, aabb.ymax + tol, aabb.zmax + tol)
    if direction == '+x':
        return AABB(aabb.xmax, aabb.ymin - tol, aabb.zmin - tol,
                     container.length + tol, aabb.ymax + tol, aabb.zmax + tol)
    if direction == '-y':
        return AABB(aabb.xmin - tol, -tol, aabb.zmin - tol,
                     aabb.xmax + tol, aabb.ymin, aabb.zmax + tol)
    if direction == '+y':
        return AABB(aabb.xmin - tol, aabb.ymax, aabb.zmin - tol,
                     aabb.xmax + tol, container.width + tol, aabb.zmax + tol)
    if direction == '-z':
        return AABB(aabb.xmin - tol, aabb.ymin - tol, -tol,
                     aabb.xmax + tol, aabb.ymax + tol, aabb.zmin)
    if direction == '+z':
        return AABB(aabb.xmin - tol, aabb.ymin - tol, aabb.zmax,
                     aabb.xmax + tol, aabb.ymax + tol, container.height + tol)
    return AABB(0, 0, 0, 0, 0, 0)


def _gap_distance(aabb, direction, container, others):
    """Compute gap distance from face to nearest obstacle.

    direction: '-x'/'+x'/'-y'/'+y'/'-z'/'+z'
    Returns distance in mm to nearest obstacle (package or container wall).
    Only considers obstacles that overlap the face's projection on both
    perpendicular axes.
    """
    if direction == '-x':
        nearest = aabb.xmin
        for o in others:
            if o.xmax >= aabb.xmin:
                continue
            if o.ymax <= aabb.ymin or o.ymin >= aabb.ymax:
                continue
            if o.zmax <= aabb.zmin or o.zmin >= aabb.zmax:
                continue
            dist = aabb.xmin - o.xmax
            if dist < nearest:
                nearest = dist
        return nearest

    if direction == '+x':
        nearest = container.length - aabb.xmax
        for o in others:
            if o.xmin <= aabb.xmax:
                continue
            if o.ymax <= aabb.ymin or o.ymin >= aabb.ymax:
                continue
            if o.zmax <= aabb.zmin or o.zmin >= aabb.zmax:
                continue
            dist = o.xmin - aabb.xmax
            if dist < nearest:
                nearest = dist
        return nearest

    if direction == '-y':
        nearest = aabb.ymin
        for o in others:
            if o.ymax >= aabb.ymin:
                continue
            if o.xmax <= aabb.xmin or o.xmin >= aabb.xmax:
                continue
            if o.zmax <= aabb.zmin or o.zmin >= aabb.zmax:
                continue
            dist = aabb.ymin - o.ymax
            if dist < nearest:
                nearest = dist
        return nearest

    if direction == '+y':
        nearest = container.width - aabb.ymax
        for o in others:
            if o.ymin <= aabb.ymax:
                continue
            if o.xmax <= aabb.xmin or o.xmin >= aabb.xmax:
                continue
            if o.zmax <= aabb.zmin or o.zmin >= aabb.zmax:
                continue
            dist = o.ymin - aabb.ymax
            if dist < nearest:
                nearest = dist
        return nearest

    if direction == '-z':
        nearest = aabb.zmin
        for o in others:
            if o.zmax >= aabb.zmin:
                continue
            if o.xmax <= aabb.xmin or o.xmin >= aabb.xmax:
                continue
            if o.ymax <= aabb.ymin or o.ymin >= aabb.ymax:
                continue
            dist = aabb.zmin - o.zmax
            if dist < nearest:
                nearest = dist
        return nearest

    if direction == '+z':
        nearest = container.height - aabb.zmax
        for o in others:
            if o.zmin <= aabb.zmax:
                continue
            if o.xmax <= aabb.xmin or o.xmin >= aabb.xmax:
                continue
            if o.ymax <= aabb.ymin or o.ymin >= aabb.ymax:
                continue
            dist = o.zmin - aabb.zmax
            if dist < nearest:
                nearest = dist
        return nearest

    return 0.0


def _get_nearby_actual(placements, probe):
    """Build actual (non-inflated) AABBs from placements intersecting probe."""
    result = []
    for pl in placements:
        if pl.package is None:
            continue
        a = _build_actual_aabb(pl.package, pl.x, pl.y, pl.z, pl.rotation)
        if probe.intersects(a):
            result.append(a)
    return result


def _get_nearby_spatial(query_aabb_fn, probe):
    """Use spatial index to find placements near probe, return actual AABBs."""
    result = []
    for pl, _ in query_aabb_fn(probe):
        if pl.package is None:
            continue
        result.append(_build_actual_aabb(
            pl.package, pl.x, pl.y, pl.z, pl.rotation,
        ))
    return result


def _gap_fit_score(gap_dims, pkg):
    """Continuous score 0-1 for how well a package fits in a gap box.

    Sorts dimensions for orientation invariance.
    Product of clamped dimension ratios gives smooth degradation.
    """
    g = sorted(gap_dims)
    p = sorted([pkg.length_mm, pkg.width_mm, pkg.height_mm])

    score = 1.0
    for i in range(3):
        if p[i] <= 0:
            continue
        ratio = g[i] / p[i]
        score *= min(ratio, 1.0)

    return score


def compute_dead_space_quality(
    aabb: AABB,
    container: Container,
    placements: list,
    remaining_packages: list[Package],
    query_aabb_fn: Optional[Callable] = None,
) -> float:
    """Estimate how usable the remaining free space will be after placement.

    Returns a 0-1 score where:
      1.0 = all exposed faces open to large, usable gaps
      0.0 = all exposed faces are tightly enclosed with no usable space

    The score is the area-weighted average of per-face gap usability
    against the hardest remaining packages. Faces flush against a wall
    or another package (gap <= MIN_GAP_MM) are excluded.

    Uses the spatial index (via query_aabb_fn) when available for O(nearby)
    per-face search instead of O(all_placements).

    Args:
        aabb: Candidate package's actual (non-inflated) AABB.
        container: Container being loaded into.
        placements: List of existing Placements.
        remaining_packages: Packages not yet placed.
        query_aabb_fn: Optional spatial query function (PlanningState.query_aabb).
    """
    if not remaining_packages:
        return 1.0

    # Build actual AABBs for existing placements
    # Use spatial index when available for efficiency
    if query_aabb_fn is not None:
        # Build a full-container query to get all placed packages
        probe_all = AABB(-1, -1, -1,
                          container.length + 1,
                          container.width + 1,
                          container.height + 1)
        others = _get_nearby_spatial(query_aabb_fn, probe_all)
    else:
        others = []
        for pl in placements:
            if pl.package is None:
                continue
            others.append(_build_actual_aabb(
                pl.package, pl.x, pl.y, pl.z, pl.rotation,
            ))

    scored_ref = _select_hardest(remaining_packages, REFERENCE_SET_SIZE)
    if not scored_ref:
        return 1.0

    l = aabb.xmax - aabb.xmin
    w = aabb.ymax - aabb.ymin
    h = aabb.zmax - aabb.zmin

    faces = [
        (w, h, '-x', w * h),
        (w, h, '+x', w * h),
        (l, h, '-y', l * h),
        (l, h, '+y', l * h),
        (l, w, '-z', l * w),
        (l, w, '+z', l * w),
    ]

    total_weight = 0.0
    weighted_score = 0.0

    for face_dim1, face_dim2, direction, weight in faces:
        gap_dist = _gap_distance(aabb, direction, container, others)
        if gap_dist <= MIN_GAP_MM:
            continue

        gap_dims = (gap_dist, face_dim1, face_dim2)

        # Difficulty-weighted average: harder packages dominate
        ref_score = 0.0
        ref_weight = 0.0
        for diff, pkg in scored_ref:
            s = _gap_fit_score(gap_dims, pkg)
            ref_score += s * diff
            ref_weight += diff

        face_score = ref_score / ref_weight if ref_weight > 0 else 0.0

        weighted_score += face_score * weight
        total_weight += weight

    if total_weight == 0.0:
        return 1.0

    return weighted_score / total_weight
