from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Optional, Callable
from .package import Package
from .placement import Placement

MAX_POSSIBLE_SCORE = 100.0


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
    the highest-scoring valid position for each package."""

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
                p.stackable,
                -(p.length_mm * p.width_mm * p.height_mm),
                -(p.length_mm * p.width_mm),
                -p.weight_kg,
            ),
        )

        result = AutoArrangeResult()
        total = len(sorted_packages)

        for i, pkg in enumerate(sorted_packages):
            if cancel_callback and cancel_callback():
                result.warnings.append("Auto Arrange cancelled by user")
                break

            # Get candidate positions from the planner
            base_candidates = planner.get_candidate_points()

            # Add a right-wall candidate for better left-right balance.
            # The default extreme points start at (0,0,0), biasing everything
            # to the left wall. Adding a right-wall candidate lets the
            # scorer decide which side is better for each package.
            container = planner.container
            clearance = getattr(pkg, 'clearance_mm', 10)
            right_y = container.width - pkg.width_mm - clearance
            if right_y > clearance:
                right_candidate = (0, right_y, 0)
                if right_candidate not in base_candidates:
                    base_candidates = [right_candidate] + list(base_candidates)

            # Expand candidates: try both 0 and (if allowed) 90-degree rotations
            expanded = self._expand_candidates(base_candidates, pkg.allow_rotation)

            best_pos = None
            best_score = -1.0
            best_debug_entry = None

            for candidate in expanded:
                vresult = planner.validate_position(
                    pkg, candidate["x"], candidate["y"], candidate["z"],
                    candidate["rotation"],
                )
                if not vresult.valid:
                    continue

                score = planner.evaluate_position(
                    pkg, candidate["x"], candidate["y"], candidate["z"],
                    candidate["rotation"], debug=False,
                )

                if score.total > best_score:
                    best_score = score.total
                    best_pos = candidate
                    best_debug_entry = {
                        "package_name": pkg.name,
                        "candidates_evaluated": len(expanded),
                        "best_score": round(score.total, 1),
                        "chosen_position": candidate,
                        "score_breakdown": score.breakdown,
                        "valid_candidates_found": True,
                    }

                    if best_score >= MAX_POSSIBLE_SCORE - 0.01:
                        break

            if best_pos is not None:
                p_result = planner.place_package(
                    pkg, best_pos["x"], best_pos["y"], best_pos["z"],
                    best_pos["rotation"],
                )
                if p_result.valid:
                    result.placed_packages += 1
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
                for candidate in slide_cands:
                    vresult = planner.validate_position(
                        pkg, candidate["x"], candidate["y"], candidate["z"],
                        candidate["rotation"],
                    )
                    if not vresult.valid:
                        continue
                    score = planner.evaluate_position(
                        pkg, candidate["x"], candidate["y"], candidate["z"],
                        candidate["rotation"], debug=False,
                    )
                    if score.total > best_score:
                        best_score = score.total
                        best_pos = candidate
                        best_debug_entry = {
                            "package_name": pkg.name,
                            "candidates_evaluated": len(expanded) + len(slide_cands),
                            "best_score": round(score.total, 1),
                            "chosen_position": candidate,
                            "score_breakdown": score.breakdown,
                            "valid_candidates_found": True,
                            "slide_pass": True,
                        }
                        if best_score >= MAX_POSSIBLE_SCORE - 0.01:
                            break

                if best_pos is not None:
                    p_result = planner.place_package(
                        pkg, best_pos["x"], best_pos["y"], best_pos["z"],
                        best_pos["rotation"],
                    )
                    if p_result.valid:
                        result.placed_packages += 1
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


StrategyRegistry.register("largest_first", LargestFirstStrategy)
