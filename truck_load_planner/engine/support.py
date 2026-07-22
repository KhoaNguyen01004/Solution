"""
Stacking support validation.
Ensures packages are placed on adequate support below them using a
combined-support model.  The union of XY overlap regions from all
supporting packages must cover a configurable percentage of the
candidate's footprint, and the candidate's footprint centre must lie
within the combined support region to prevent unstable bridging.

Stacking decisions use a capacity-based model rather than a simple
boolean: each base package may specify a maximum top weight, a
maximum number of stack layers, or a stacking mode (NONE / LIGHT_ONLY
/ NORMAL) to better reflect real warehouse practice.
"""

from .geometry import AABB
from .placement import Placement
from .package import Package, StackingMode


_GRID_SAMPLES = 20    # samples per axis for union coverage estimation


def _footprint_centre(aabb: AABB) -> tuple[float, float]:
    return (aabb.xmin + aabb.xmax) / 2, (aabb.ymin + aabb.ymax) / 2


def _count_above(placements, base_pl) -> int:
    """Count how many packages are stacked directly on top of *base_pl*."""
    base = base_pl.package
    if base is None:
        return 0
    base_top = base_pl.z + (
        base.height_mm if hasattr(base, 'height_mm')
        else getattr(base, 'height', 0)
    )
    count = 0
    for pl in placements:
        if pl is base_pl:
            continue
        if abs(pl.z - base_top) < 0.001:
            count += 1
    return count


def _check_stacking_rules(
    below_pl,
    top_package: Package,
    placements: list,
) -> tuple[bool, list[str]]:
    """Check capacity-based stacking rules for one below package.

    Returns (valid, reasons).
    """
    pa = below_pl.package
    if pa is None:
        return True, []

    reasons = []

    # ── Top package is unstackable: cannot sit on anything ──────────
    top_mode = getattr(top_package, 'stacking_mode', StackingMode.NORMAL)
    if top_mode == StackingMode.NONE:
        return False, [f"'{top_package.name}' is unstackable (cannot be placed on top of other packages)"]

    mode = getattr(pa, 'stacking_mode', StackingMode.NORMAL)
    max_top = getattr(pa, 'max_top_weight_kg', 0.0)
    max_layers = getattr(pa, 'max_stack_layers', 0)

    # ── StackingMode.NONE: nothing allowed above ───────────────────
    if mode == StackingMode.NONE:
        return False, [f"Cannot stack on '{pa.name}' (stacking mode: NONE)"]

    # ── StackingMode.LIGHT_ONLY: lightweight packages only ──────────
    if mode == StackingMode.LIGHT_ONLY:
        if max_top > 0 and top_package.weight_kg > max_top:
            return False, [
                f"'{top_package.name}' ({top_package.weight_kg} kg) "
                f"exceeds '{pa.name}' max_top_weight ({max_top} kg)"
            ]

    # ── Max stack layers ────────────────────────────────────────────
    if max_layers > 0:
        current_above = _count_above(placements, below_pl)
        if current_above >= max_layers:
            return False, [
                f"'{pa.name}' already has {current_above} packages "
                f"on top (max: {max_layers})"
            ]

    # ── Weight rule (all modes): top must be lighter than base ──────
    if top_package.weight_kg is not None and pa.weight_kg is not None:
        if top_package.weight_kg > pa.weight_kg:
            return False, [
                f"'{top_package.name}' ({top_package.weight_kg} kg) heavier "
                f"than '{pa.name}' ({pa.weight_kg} kg)"
            ]

    # ── Footprint area rule: top footprint must be ≤ base footprint ──
    top_fp = top_package.length_mm * top_package.width_mm
    base_fp = pa.length_mm * pa.width_mm
    if top_fp > base_fp:
        return False, [
            f"'{top_package.name}' footprint ({top_fp:.0f} mm²) larger "
            f"than '{pa.name}' footprint ({base_fp:.0f} mm²)"
        ]

    return True, []


def check_support(
    placements: list,
    candidate_aabb: AABB,
    package: Package = None,
    support_threshold: float = 0.50,
) -> dict:
    """Validate that the candidate has adequate support below.

    Rules:
      1. If z=0 (floor) → always supported.
      2. Each package directly below is checked against capacity-based
         stacking rules (stacking mode, max top weight, max layers).
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
            (default 0.50 = 50%).

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

    # ── Verify each below package: stacking rules + weight ────────────
    below_aabbs = []
    for pl in below_placements:
        pa = pl.package
        if pa is None:
            continue

        # Capacity-based stacking check
        if package is not None:
            ok, reasons = _check_stacking_rules(pl, package, placements)
            if not ok:
                return {"valid": False, "reasons": reasons}

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
