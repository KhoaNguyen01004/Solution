from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol, Optional, Callable
from .package import Package
from .placement import Placement
from .candidate_points import tighten_position, generate_floor_anchors, settle_package
from .frontier import FrontierTracker
from .trace_mutations import M

MAX_POSSIBLE_SCORE = 200.0

# Stack column tracking: bucket grid size in mm.
# Packages spanning multiple buckets are registered in all covered buckets.
# Smaller = finer column control; 500mm is a good default for truck loads.
_COLUMN_GRID_MM = 500

# Hard ceiling for stackable columns: if adding this package would push the
# column above this height, strongly prefer a floor-level position instead.
MAX_STACK_HEIGHT_MM = 1800


def _get_column_top(column_heights: dict, x: float, y: float, dx: float, dy: float) -> float:
    """Return the current max top-Z for all grid cells covered by the footprint.

    Packages that span multiple buckets (common for long/wide items) are
    registered in every cell they touch, so this returns the true local
    ceiling height over the entire footprint.
    """
    cs = _COLUMN_GRID_MM
    x0 = int(x // cs)
    x1 = int((x + dx - 0.001) // cs) if dx > 0 else x0
    y0 = int(y // cs)
    y1 = int((y + dy - 0.001) // cs) if dy > 0 else y0
    max_h = 0.0
    for xc in range(x0, x1 + 1):
        for yc in range(y0, y1 + 1):
            h = column_heights.get((xc, yc), 0.0)
            if h > max_h:
                max_h = h
    return max_h


def _update_column_heights(
    column_heights: dict, x: float, y: float, dx: float, dy: float, top_z: float
) -> None:
    """Update column height for every grid cell covered by the footprint."""
    cs = _COLUMN_GRID_MM
    x0 = int(x // cs)
    x1 = int((x + dx - 0.001) // cs) if dx > 0 else x0
    y0 = int(y // cs)
    y1 = int((y + dy - 0.001) // cs) if dy > 0 else y0
    for xc in range(x0, x1 + 1):
        for yc in range(y0, y1 + 1):
            key = (xc, yc)
            if column_heights.get(key, 0.0) < top_z:
                column_heights[key] = top_z


@dataclass
class AutoArrangeResult:
    placed_packages: int = 0
    failed_packages: int = 0
    utilization: float = 0.0
    total_score: float = 0.0
    warnings: list[str] = field(default_factory=list)
    unplaced_packages: list[str] = field(default_factory=list)
    placement_count: int = 0
    debug_log: list[dict] = field(default_factory=list)


class AutoArrangeStrategy(Protocol):
    def arrange(
        self,
        planner: Planner,
        packages: list[Package],
        progress_callback: Optional[Callable] = None,
        cancel_callback: Optional[Callable] = None,
        debug: bool = False,
    ) -> AutoArrangeResult:
        ...


class LargestFirstStrategy:
    """Place non-stackable packages first, then by descending volume,
    footprint, and weight. Evaluates all candidate positions and picks
    the highest-scoring valid position for each package.

    Stack column tracking enforces MAX_STACK_HEIGHT_MM: when a candidate
    would push a column above that ceiling, it receives a heavy score
    penalty, encouraging the algorithm to start a new floor-level column
    instead of building an unstable tower.
    """

    def arrange(
        self,
        planner: Planner,
        packages: list[Package],
        progress_callback: Optional[Callable] = None,
        cancel_callback: Optional[Callable] = None,
        debug: bool = False,
    ) -> AutoArrangeResult:
        sorted_packages = sorted(
            packages,
            key=lambda p: (
                0 if not p.stackable else 1,
                -(p.length_mm * p.width_mm * p.height_mm),
                -p.weight_kg,
                -(p.length_mm * p.width_mm),
            ),
        )

        result = AutoArrangeResult()
        total = len(sorted_packages)

        # Track max top-Z per grid bucket for stack-height enforcement
        column_heights: dict[tuple[int, int], float] = {}

        # Track max X per Y-strip to detect and penalise gaps
        frontier = FrontierTracker(planner.container.width, strip_width_mm=250)

        for i, pkg in enumerate(sorted_packages):
            if cancel_callback and cancel_callback():
                result.warnings.append("Auto Arrange cancelled by user")
                break

            remaining_pkgs = sorted_packages[i + 1:]

            # Get candidate positions from the planner
            base_candidates = planner.get_candidate_points()

            # Add a right-wall candidate for better left-right balance.
            # The default extreme points start at (0,0,0), biasing everything
            # to the left wall. Adding a right-wall candidate lets the
            # scorer decide which side is better for each package.
            container = planner.container
            h_clr = getattr(pkg, 'horizontal_clearance_mm', 10.0)
            right_y = container.width - pkg.width_mm - h_clr
            if right_y > h_clr:
                right_candidate = (0, right_y, 0)
                if right_candidate not in base_candidates:
                    base_candidates = [right_candidate] + list(base_candidates)

            # Augment with floor anchors from largest empty floor regions
            floor_anchors = generate_floor_anchors(
                planner.placements, container, pkg, max_regions=2,
            )
            for anchor in floor_anchors:
                if anchor not in base_candidates:
                    base_candidates.append(anchor)

            # Expand candidates: try both 0 and (if allowed) 90-degree rotations
            expanded = self._expand_candidates(base_candidates, pkg.allow_rotation)

            # Sort by cheap candidate_priority so good candidates are tried first
            from .distribution import candidate_priority
            expanded.sort(key=lambda pos: candidate_priority(pkg, pos, container), reverse=True)
            # Apply candidate limit from profile
            max_cands = getattr(planner, '_candidate_limit', None)
            if max_cands and len(expanded) > max_cands:
                expanded = expanded[:max_cands]

            # Tighten + validate + score — stop early if ideal position found
            best_pos = None
            best_score = float("-inf")
            best_debug_entry = None
            candidates_tried = 0
            EARLY_EXIT_SCORE = 199.0  # near-perfect score → stop searching
            all_candidate_details = []   # captures EVERY candidate evaluation

            for candidate in expanded:
                candidates_tried += 1
                candidate_detail = {"input_pos": dict(candidate)}
                tx, ty, tz, trot = tighten_position(
                    planner, pkg, candidate["x"], candidate["y"], candidate["z"], candidate["rotation"],
                )
                is_invalid = False
                vresult = planner.validate_position(pkg, tx, ty, tz, trot)
                if not vresult.valid:
                    candidate_detail["valid"] = False
                    candidate_detail["reason"] = str(vresult.reasons)
                    is_invalid = True
                else:
                    candidate_detail["valid"] = True
                    candidate_detail["tightened_pos"] = {"x": tx, "y": ty, "z": tz, "rotation": trot}

                if not is_invalid:
                    # Stack-column height check: penalise candidates that would
                    # push this footprint above the configured ceiling.
                    if trot in (90, 270):
                        cdx, cdy = pkg.width_mm, pkg.length_mm
                    else:
                        cdx, cdy = pkg.length_mm, pkg.width_mm
                    col_top = _get_column_top(column_heights, tx, ty, cdx, cdy)
                    stack_ceiling_penalty = 0.0
                    if tz > 0.001 and (tz + pkg.height_mm) > MAX_STACK_HEIGHT_MM:
                        stack_ceiling_penalty = -300.0
                    elif tz > 0.001 and col_top > MAX_STACK_HEIGHT_MM * 0.85:
                        stack_ceiling_penalty = -50.0
                    candidate_detail["col_top"] = round(col_top, 1)
                    candidate_detail["stack_ceiling_penalty"] = stack_ceiling_penalty

                    # Gap penalty: penalise floor candidates that leave space behind frontier
                    gap_penalty = 0.0
                    if tz < 0.001:
                        gap_dist = frontier.gap_distance(tx, ty, cdy)
                        gap_ratio_val = frontier.gap_ratio(tx, ty, cdy)
                        if gap_dist > 0:
                            gap_penalty = -min(gap_dist * (0.5 + gap_ratio_val * 0.5), 500.0)
                        candidate_detail["gap_dist"] = round(gap_dist, 1)
                        candidate_detail["gap_ratio"] = round(gap_ratio_val, 3)
                    candidate_detail["gap_penalty"] = round(gap_penalty, 1)

                    score = planner.evaluate_position(
                        pkg, tx, ty, tz, trot, debug=False,
                        remaining_packages=remaining_pkgs,
                    )
                    candidate_detail["raw_score"] = round(score.total, 1)
                    if hasattr(score, 'breakdown'):
                        candidate_detail["breakdown"] = {k: round(v, 2) for k, v in score.breakdown.items()}
                    adjusted_score = score.total + stack_ceiling_penalty + gap_penalty
                    candidate_detail["adjusted_score"] = round(adjusted_score, 1)
                    if adjusted_score > best_score:
                        best_score = adjusted_score
                        best_pos = {"x": tx, "y": ty, "z": tz, "rotation": trot}
                        if adjusted_score >= EARLY_EXIT_SCORE:
                            all_candidate_details.append(candidate_detail)
                            break

                all_candidate_details.append(candidate_detail)

            if best_pos is not None:
                best_debug_entry = {
                    "package_name": pkg.name,
                    "candidates_evaluated": candidates_tried,
                    "all_candidate_details": all_candidate_details,
                    "best_score": round(best_score, 1),
                    "chosen_position": best_pos,
                    "score_breakdown": {},
                    "valid_candidates_found": True,
                    "tightened": True,
                }

            if best_pos is not None:
                pkg_name = pkg.name if pkg else "?"
                p_result = planner.place_package(
                    pkg, best_pos["x"], best_pos["y"], best_pos["z"],
                    best_pos["rotation"],
                    _trace_reason=f"largest_first/main/{pkg_name}",
                )
                if p_result.valid:
                    result.placed_packages += 1
                    # Update frontier tracker for floor-level placements
                    pl = planner.placements[-1]
                    frontier.update_from_placement(pl)
                    # Update column height tracker for the placed package
                    brot = best_pos["rotation"]
                    if brot in (90, 270):
                        bdx, bdy = pkg.width_mm, pkg.length_mm
                    else:
                        bdx, bdy = pkg.length_mm, pkg.width_mm
                    _update_column_heights(
                        column_heights,
                        best_pos["x"], best_pos["y"], bdx, bdy,
                        best_pos["z"] + pkg.height_mm,
                    )
                else:
                    result.failed_packages += 1
                    result.unplaced_packages.append(pkg.name)
                    if best_debug_entry:
                        best_debug_entry["valid_candidates_found"] = False
            else:
                # ── Y-slide pass: try sliding candidates left/right ──
                from .candidate_points import generate_slide_candidates
                container = planner.container
                slide_cands = generate_slide_candidates(base_candidates, pkg, container)
                slide_details = []
                for candidate in slide_cands:
                    sd = {"input_pos": dict(candidate)}
                    tx, ty, tz, trot = tighten_position(
                        planner, pkg, candidate["x"], candidate["y"], candidate["z"], candidate["rotation"],
                    )
                    vresult = planner.validate_position(pkg, tx, ty, tz, trot)
                    if not vresult.valid:
                        sd["valid"] = False
                        sd["reason"] = str(vresult.reasons)
                        slide_details.append(sd)
                        continue

                    sd["valid"] = True
                    sd["tightened_pos"] = {"x": tx, "y": ty, "z": tz, "rotation": trot}

                    # Gap penalty for Y-slide candidates too
                    gap_penalty = 0.0
                    if tz < 0.001:
                        if trot in (90, 270):
                            sdy = pkg.length_mm
                        else:
                            sdy = pkg.width_mm
                        gd = frontier.gap_distance(tx, ty, sdy)
                        gr = frontier.gap_ratio(tx, ty, sdy)
                        if gd > 0:
                            gap_penalty = -min(gd * (0.5 + gr * 0.5), 500.0)
                        sd["gap_dist"] = round(gd, 1)
                        sd["gap_ratio"] = round(gr, 3)
                    sd["gap_penalty"] = round(gap_penalty, 1)

                    score = planner.evaluate_position(
                        pkg, tx, ty, tz, trot, debug=False,
                        remaining_packages=remaining_pkgs,
                    )
                    sd["raw_score"] = round(score.total, 1)
                    if hasattr(score, 'breakdown'):
                        sd["breakdown"] = {k: round(v, 2) for k, v in score.breakdown.items()}
                    tight_candidate = {"x": tx, "y": ty, "z": tz, "rotation": trot}
                    adjusted = score.total + gap_penalty
                    sd["adjusted_score"] = round(adjusted, 1)
                    slide_details.append(sd)
                    if adjusted > best_score:
                        best_score = adjusted
                        best_pos = tight_candidate
                        best_debug_entry = {
                            "package_name": pkg.name,
                            "candidates_evaluated": len(expanded) + len(slide_cands),
                            "slide_details": slide_details,
                            "best_score": round(score.total, 1),
                            "chosen_position": candidate,
                            "score_breakdown": score.breakdown,
                            "valid_candidates_found": True,
                            "slide_pass": True,
                        }
                        if best_score >= MAX_POSSIBLE_SCORE - 0.01:
                            break

                if best_pos is not None:
                    pkg_name = pkg.name if pkg else "?"
                    p_result = planner.place_package(
                        pkg, best_pos["x"], best_pos["y"], best_pos["z"],
                        best_pos["rotation"],
                        _trace_reason=f"largest_first/slide/{pkg_name}",
                    )
                    if p_result.valid:
                        result.placed_packages += 1
                        pl = planner.placements[-1]
                        frontier.update_from_placement(pl)
                    else:
                        result.failed_packages += 1
                        result.unplaced_packages.append(pkg.name)
                else:
                    result.failed_packages += 1
                    result.unplaced_packages.append(pkg.name)
                    best_debug_entry = {
                        "package_name": pkg.name,
                        "candidates_evaluated": len(expanded) + len(slide_cands),
                        "best_score": 0.0,
                        "chosen_position": None,
                        "score_breakdown": {},
                        "valid_candidates_found": False,
                    }

            if debug and best_debug_entry:
                result.debug_log.append(best_debug_entry)

            if progress_callback:
                progress_callback(i + 1, total, best_score if best_score > 0 else 0.0)

        # ── Gap-filling pass: try to fit unplaced small packages ────
        if result.unplaced_packages:
            # Track which specific package instances failed (by id),
            # because multiple packages can share the same name.
            failed_ids: set[int] = set()
            for i, pkg in enumerate(packages):
                if pkg.name in result.unplaced_packages:
                    # Count how many of this name failed
                    if result.unplaced_packages.count(pkg.name) > 0:
                        # Only mark the package as failed if we haven't
                        # already accounted for all failures of this name
                        pass
            remaining = Counter(result.unplaced_packages)
            gap_candidates: list[Package] = []
            for pkg in packages:
                if remaining.get(pkg.name, 0) > 0:
                    gap_candidates.append(pkg)
                    remaining[pkg.name] -= 1
            gap_candidates.sort(key=lambda p: p.length_mm * p.width_mm * p.height_mm)
            still_unplaced_names: list[str] = []
            for pkg in gap_candidates:
                base_candidates = planner.get_candidate_points()
                expanded = self._expand_candidates(base_candidates, pkg.allow_rotation)
                scored = []
                for candidate in expanded:
                    tx, ty, tz, trot = tighten_position(
                        planner, pkg, candidate["x"], candidate["y"], candidate["z"], candidate["rotation"],
                    )
                    vresult = planner.validate_position(pkg, tx, ty, tz, trot)
                    if not vresult.valid:
                        continue

                    gap_penalty = 0.0
                    if tz < 0.001:
                        if trot in (90, 270):
                            gdy = pkg.length_mm
                        else:
                            gdy = pkg.width_mm
                        gd = frontier.gap_distance(tx, ty, gdy)
                        gr = frontier.gap_ratio(tx, ty, gdy)
                        if gd > 0:
                            gap_penalty = -min(gd * (0.5 + gr * 0.5), 500.0)

                    score = planner.evaluate_position(
                        pkg, tx, ty, tz, trot, debug=False,
                    )
                    scored.append((score.total + gap_penalty, score, {"x": tx, "y": ty, "z": tz, "rotation": trot}))
                best_pos = None
                best_score = float("-inf")
                if scored:
                    scored.sort(key=lambda x: x[0], reverse=True)
                    best_score = scored[0][0]
                    best_pos = scored[0][2]
                if best_pos is not None:
                    pkg_name = pkg.name if pkg else "?"
                    p_result = planner.place_package(
                        pkg, best_pos["x"], best_pos["y"], best_pos["z"],
                        best_pos["rotation"],
                        _trace_reason=f"largest_first/gap_fill/{pkg_name}",
                    )
                    if p_result.valid:
                        result.placed_packages += 1
                        frontier.update_from_placement(planner.placements[-1])
                    else:
                        still_unplaced_names.append(pkg.name)
                else:
                    still_unplaced_names.append(pkg.name)
            result.unplaced_packages = still_unplaced_names
            result.failed_packages = len(still_unplaced_names)

        # Post-placement compaction pipeline:
        # 1. Frontier-based analytical gap-fill — closes gaps behind frontier
        # 2. Step-compaction with Y/Z fallback (closes cases analytical missed)
        # 3. Whole-stack group compaction
        # 4. Final frontier sweep
        from .distribution import (reassign_load_sequences, compact_placements,
                                    compact_stacks, fill_frontier_gaps)
        M.stage("== fill_frontier_gaps (1) ==")
        M.snapshot(planner.placements, "before_fill_frontier_gaps_1")
        fill_frontier_gaps(planner, frontier)
        M.check_integrity(planner.placements, "after_fill_frontier_gaps_1")
        M.stage("== compact_placements ==")
        M.snapshot(planner.placements, "before_compact_placements")
        compact_placements(planner, passes=3, step=5.0)
        M.check_integrity(planner.placements, "after_compact_placements")
        M.stage("== compact_stacks ==")
        M.snapshot(planner.placements, "before_compact_stacks")
        compact_stacks(planner, step=5.0)
        M.check_integrity(planner.placements, "after_compact_stacks")
        M.stage("== fill_frontier_gaps (2) ==")
        M.snapshot(planner.placements, "before_fill_frontier_gaps_2")
        fill_frontier_gaps(planner, frontier)
        M.check_integrity(planner.placements, "after_fill_frontier_gaps_2")
        M.stage("== reassign_load_sequences ==")
        reassign_load_sequences(planner.placements)

        # Compute final statistics
        stats = planner.get_statistics()
        result.utilization = stats.get("volume_used_pct", 0.0)
        result.placement_count = stats.get("packages_placed", 0)

        plan_score = planner.evaluate_plan()
        result.total_score = round(plan_score.total, 1)

        return result

    def _expand_candidates(
        self, base_candidates: list, allow_rotation: bool,
    ) -> list[dict]:
        expanded = []
        seen = set()
        for pos in base_candidates:
            if isinstance(pos, dict):
                x, y, z = pos.get("x", 0), pos.get("y", 0), pos.get("z", 0)
            else:
                x, y, z = pos[0], pos[1], pos[2]

            key0 = (x, y, z, 0)
            if key0 not in seen:
                seen.add(key0)
                expanded.append({"x": x, "y": y, "z": z, "rotation": 0})

            if allow_rotation:
                key90 = (x, y, z, 90)
                if key90 not in seen:
                    seen.add(key90)
                    expanded.append({"x": x, "y": y, "z": z, "rotation": 90})

        return expanded


class StrategyRegistry:
    _strategies: dict[str, type] = {}

    @classmethod
    def register(cls, name: str, strategy_cls: type) -> None:
        cls._strategies[name] = strategy_cls

    @classmethod
    def get(cls, name: str) -> Optional[type]:
        return cls._strategies.get(name)

    @classmethod
    def list(cls) -> list[str]:
        return list(cls._strategies.keys())


MAX_STACK_HEIGHT_MM = 1800


class ColumnStrategy:
    """Simple wall-to-door column-based placement strategy.

    Implements the 5-step algorithm using the existing spatial index
    for fast validation rather than brute-force O(n2) collision loops.

    1. Sort largest items first
    2. Place items deep inside (lowest X) on floor — uses existing
       extreme points + tighten_position + validate_position
    3. Items close to each other — scoring prefers compactness
    4. Stack height limited to MAX_STACK_HEIGHT_MM; if too tall,
       package stays on floor to form a new column
    5. Final compaction pass pushes everything forward
    """

    def __init__(self, max_stack_height_mm: float = MAX_STACK_HEIGHT_MM):
        self.max_stack_height_mm = max_stack_height_mm

    @staticmethod
    def _simple_score(pkg, x, y, z, rotation, container, placements, max_stack_height):
        """Simplified scoring: deep + floor + compact, penalize tall stacks."""
        score = 0.0

        # Deep placement (x near 0 = front wall)
        if container.length > 0:
            deep = (1.0 - x / container.length)
            score += deep * 120.0

        # Floor preference
        if z < 0.001:
            score += 50.0
        else:
            # Penalize stacks above max height
            if z > max_stack_height:
                score -= 100.0

        # Compactness: prefer being near other packages
        if placements:
            pkg_l = pkg.length_mm if rotation == 0 else pkg.width_mm
            pkg_w = pkg.width_mm if rotation == 0 else pkg.length_mm
            cx, cy = x + pkg_l / 2, y + pkg_w / 2
            min_dist = float("inf")
            for pl in placements:
                if pl.package is None:
                    continue
                pl_l = pl.package.length_mm if pl.rotation == 0 else pl.package.width_mm
                pl_w = pl.package.width_mm if pl.rotation == 0 else pl.package.length_mm
                pcx, pcy = pl.x + pl_l / 2, pl.y + pl_w / 2
                d = ((cx - pcx)**2 + (cy - pcy)**2)**0.5
                if d < min_dist:
                    min_dist = d
            if min_dist < 2000:
                score += 20.0 * (1.0 - min_dist / 2000)

        return score

    def arrange(
        self,
        planner: Planner,
        packages: list[Package],
        progress_callback: Optional[Callable] = None,
        cancel_callback: Optional[Callable] = None,
        debug: bool = False,
    ) -> AutoArrangeResult:
        result = AutoArrangeResult()
        container = planner.container

        # Step 1: sort packages by volume descending (largest first)
        sorted_pkgs = sorted(
            packages,
            key=lambda p: (
                0 if not p.stackable else 1,
                -(p.length_mm * p.width_mm * p.height_mm),
                -p.weight_kg,
            ),
        )

        total = len(sorted_pkgs)
        for i, pkg in enumerate(sorted_pkgs):
            if cancel_callback and cancel_callback():
                result.warnings.append("Auto Arrange cancelled by user")
                break

            # Use existing extreme points + spatial index (fast path)
            candidates = list(planner.get_candidate_points())

            # Add right-wall candidate for Y balance
            h_clr = getattr(pkg, 'horizontal_clearance_mm', 10.0)
            right_y = container.width - pkg.width_mm - h_clr
            if right_y > h_clr and (0, right_y, 0) not in candidates:
                candidates.insert(0, (0, right_y, 0))

            # Add floor anchors (empty floor regions)
            from .candidate_points import generate_floor_anchors
            floor_anchors = generate_floor_anchors(
                planner.placements, container, pkg, max_regions=2,
            )
            for anchor in floor_anchors:
                if anchor not in candidates:
                    candidates.append(anchor)

            # Expand with rotations
            from .distribution import expand_candidates
            expanded = expand_candidates(candidates, pkg.allow_rotation)

            # Step 2-3: tighten + validate + score (uses spatial index)
            from .candidate_points import tighten_position
            best_pos = None
            best_score = float("-inf")

            for pos in expanded:
                tx, ty, tz, trot = tighten_position(
                    planner, pkg, pos["x"], pos["y"], pos["z"], pos["rotation"],
                )
                vresult = planner.validate_position(pkg, tx, ty, tz, trot)
                if not vresult.valid:
                    continue
                score = self._simple_score(
                    pkg, tx, ty, tz, trot,
                    container, planner.placements,
                    self.max_stack_height_mm,
                )
                if score > best_score:
                    best_score = score
                    best_pos = {"x": tx, "y": ty, "z": tz, "rotation": trot}

            # Fallback: Y-slide / X-slide candidates
            if best_pos is None:
                from .candidate_points import generate_slide_candidates
                slide_cands = generate_slide_candidates(candidates, pkg, container)
                for pos in slide_cands:
                    tx, ty, tz, trot = tighten_position(
                        planner, pkg, pos["x"], pos["y"], pos["z"], pos["rotation"],
                    )
                    vresult = planner.validate_position(pkg, tx, ty, tz, trot)
                    if not vresult.valid:
                        continue
                    score = self._simple_score(
                        pkg, tx, ty, tz, trot,
                        container, planner.placements,
                        self.max_stack_height_mm,
                    )
                    if score > best_score:
                        best_score = score
                        best_pos = {"x": tx, "y": ty, "z": tz, "rotation": trot}

            if best_pos is not None:
                pkg_name = pkg.name if pkg else "?"
                p_result = planner.place_package(
                    pkg, best_pos["x"], best_pos["y"],
                    best_pos["z"], best_pos["rotation"],
                    _trace_reason=f"column_strategy/{pkg_name}",
                )
                if p_result.valid:
                    result.placed_packages += 1
                else:
                    result.failed_packages += 1
                    result.unplaced_packages.append(pkg.name)
            else:
                result.failed_packages += 1
                result.unplaced_packages.append(pkg.name)

            if progress_callback:
                progress_callback(i + 1, total, max(0, best_score))

        # Step 5: final compaction - frontier gap-fill then step compaction
        from .distribution import (reassign_load_sequences, compact_placements,
                                    compact_stacks, fill_frontier_gaps)
        from .frontier import FrontierTracker
        frontier = FrontierTracker(container.width, strip_width_mm=250)
        for pl in planner.placements:
            frontier.update_from_placement(pl)
        M.stage("== Column: fill_frontier_gaps (1) ==")
        fill_frontier_gaps(planner, frontier)
        M.stage("== Column: compact_placements ==")
        compact_placements(planner, passes=3, step=5.0)
        M.stage("== Column: compact_stacks ==")
        compact_stacks(planner, step=5.0)
        for pl in planner.placements:
            frontier.update_from_placement(pl)
        M.stage("== Column: fill_frontier_gaps (2) ==")
        fill_frontier_gaps(planner, frontier)
        reassign_load_sequences(planner.placements)

        stats = planner.get_statistics()
        result.utilization = stats.get("volume_used_pct", 0.0)
        result.placement_count = stats.get("packages_placed", 0)
        result.total_score = round(planner.evaluate_plan().total, 1)

        return result


StrategyRegistry.register("largest_first", LargestFirstStrategy)
StrategyRegistry.register("column", ColumnStrategy)
