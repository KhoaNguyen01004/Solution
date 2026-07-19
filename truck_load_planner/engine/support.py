"""
Stacking support validation.
Ensures packages are placed on adequate support below them using a
combined-support model.  The union of XY overlap regions from all
supporting packages must cover a configurable percentage of the
candidate's footprint, and the candidate's footprint centre must lie
within the combined support region to prevent unstable bridging.
"""

from .geometry import AABB
from .placement import Placement
from .package import Package


_GRID_SAMPLES = 20    # samples per axis for union coverage estimation


def _footprint_centre(aabb: AABB) -> tuple[float, float]:
    return (aabb.xmin + aabb.xmax) / 2, (aabb.ymin + aabb.ymax) / 2


def check_support(
    placements: list,
    candidate_aabb: AABB,
    package: Package = None,
    support_threshold: float = 0.90,
) -> dict:
    """Validate that the candidate has adequate support below.

    Rules:
      1. If z=0 (floor) → always supported.
      2. Every package directly below must be stackable.
      3. Top package must be lighter than every package directly below.
      4. The union of XY-overlap regions from all below packages must
         cover at least ``support_threshold`` (0-1) of the candidate's
         footprint area.
      5. The candidate's XY footprint centre must lie within at least
         one below package's XY extent.

    Args:
        placements: Current list of Placement objects.
        candidate_aabb: AABB of the package being placed.
        package: The package being placed (for weight check).
        support_threshold: Minimum fraction of candidate footprint that
            must be covered by the union of below-package XY overlap
            (default 0.90 = 90%).

    Returns:
        {"valid": True, "reasons": []} or
        {"valid": False, "reasons": ["..."]}
    """
    z_bottom = candidate_aabb.zmin
    if z_bottom == 0:
        return {"valid": True, "reasons": []}

    candidate_l = candidate_aabb.xmax - candidate_aabb.xmin
    candidate_w = candidate_aabb.ymax - candidate_aabb.ymin
    candidate_area = candidate_l * candidate_w
    if candidate_area <= 0:
        return {"valid": False, "reasons": ["Package has zero footprint"]}

    # ── Collect packages directly below ──────────────────────────────
    below_placements = []
    for pl in placements:
        pa = pl.package
        if pa is None:
            continue
        pkg_zmax = pl.z + (
            pa.height_mm if hasattr(pa, 'height_mm')
            else getattr(pa, 'height', 0)
        )
        if abs(pkg_zmax - z_bottom) < 0.001:
            below_placements.append(pl)

    if not below_placements:
        return {"valid": False, "reasons": ["No support below package"]}

    # ── Verify each below package: stackable + weight ─────────────────
    below_aabbs = []
    for pl in below_placements:
        pa = pl.package

        if pa and not pa.stackable:
            return {
                "valid": False,
                "reasons": [f"Cannot stack on '{pa.name}' (not stackable)"],
            }

        if pa and package is not None and package.weight_kg is not None \
                and pa.weight_kg is not None:
            if package.weight_kg > pa.weight_kg:
                return {
                    "valid": False,
                    "reasons": [
                        f"'{package.name}' ({package.weight_kg} kg) heavier "
                        f"than '{pa.name}' ({pa.weight_kg} kg)"
                    ],
                }

        pkg_len = pa.length_mm if hasattr(pa, 'length_mm') \
                  else getattr(pa, 'length', 0)
        pkg_wid = pa.width_mm if hasattr(pa, 'width_mm') \
                  else getattr(pa, 'width', 0)
        pkg_hei = pa.height_mm if hasattr(pa, 'height_mm') \
                  else getattr(pa, 'height', 0)

        below_aabb = AABB.from_dimensions(
            pl.x, pl.y, pl.z,
            pkg_len, pkg_wid, pkg_hei,
            pl.rotation, clearance=0,
        )
        below_aabbs.append(below_aabb)

    # ── Combined-support coverage ─────────────────────────────────────
    # Grid-sample the candidate's XY footprint and check which sample
    # points fall inside *any* below package AABB.
    cx_min, cx_max = candidate_aabb.xmin, candidate_aabb.xmax
    cy_min, cy_max = candidate_aabb.ymin, candidate_aabb.ymax
    step_x = (cx_max - cx_min) / _GRID_SAMPLES if _GRID_SAMPLES > 0 else 1
    step_y = (cy_max - cy_min) / _GRID_SAMPLES if _GRID_SAMPLES > 0 else 1

    supported_samples = 0
    total_samples = 0
    for i in range(_GRID_SAMPLES):
        px = cx_min + (i + 0.5) * step_x
        for j in range(_GRID_SAMPLES):
            py = cy_min + (j + 0.5) * step_y
            total_samples += 1
            for ba in below_aabbs:
                if ba.xmin <= px <= ba.xmax and ba.ymin <= py <= ba.ymax:
                    supported_samples += 1
                    break

    coverage = supported_samples / total_samples if total_samples > 0 else 0.0
    if coverage < support_threshold:
        return {
            "valid": False,
            "reasons": [
                f"Combined support coverage {coverage:.1%} < "
                f"{support_threshold:.0%} of candidate footprint"
            ],
        }

    # ── Centre-of-mass check: the candidate's XY centre must be
    #    within the XY bounds of at least one below package ──────────
    cx, cy = _footprint_centre(candidate_aabb)
    centre_supported = any(
        ba.xmin <= cx <= ba.xmax and ba.ymin <= cy <= ba.ymax
        for ba in below_aabbs
    )
    if not centre_supported:
        return {
            "valid": False,
            "reasons": [
                f"Candidate footprint centre ({cx:.0f}, {cy:.0f}) not "
                f"supported by any package below"
            ],
        }

    return {"valid": True, "reasons": []}
