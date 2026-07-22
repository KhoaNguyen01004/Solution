from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Optional, Callable
from .package import Package
from .placement import Placement
from .candidate_points import tighten_position, generate_floor_anchors
from .trace_mutations import M


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

        for pkg in sorted_packages:
            if cancel_callback and cancel_callback():
                result.warnings.append("Auto Arrange cancelled by user")
                break

            base_candidates = planner.get_candidate_points()

            container = planner.container
            h_clr = getattr(pkg, 'horizontal_clearance_mm', 10.0)
            right_y = container.width - pkg.width_mm - h_clr
            if right_y > h_clr:
                right_candidate = (0, right_y, 0)
                if right_candidate not in base_candidates:
                    base_candidates = [right_candidate] + list(base_candidates)

            floor_anchors = generate_floor_anchors(
                planner.placements, container, pkg, max_regions=2,
            )
            for anchor in floor_anchors:
                if anchor not in base_candidates:
                    base_candidates.append(anchor)

            expanded = self._expand_candidates(base_candidates, pkg.allow_rotation)

            max_cands = getattr(planner, '_candidate_limit', None)
            if max_cands and len(expanded) > max_cands:
                expanded = expanded[:max_cands]

            best_pos = None
            best_score = float("-inf")
            best_debug_entry = None
            candidates_tried = 0
            all_candidate_details = []

            for candidate in expanded:
                candidates_tried += 1
                candidate_detail = {"input_pos": dict(candidate)}
                tx, ty, tz, trot = tighten_position(
                    planner, pkg, candidate["x"], candidate["y"], candidate["z"], candidate["rotation"],
                )
                vresult = planner.validate_position(pkg, tx, ty, tz, trot)
                if not vresult.valid:
                    candidate_detail["valid"] = False
                    candidate_detail["reason"] = str(vresult.reasons)
                else:
                    candidate_detail["valid"] = True
                    candidate_detail["tightened_pos"] = {"x": tx, "y": ty, "z": tz, "rotation": trot}

                    score = planner.evaluate_position(
                        pkg, tx, ty, tz, trot, debug=False,
                    )
                    candidate_detail["raw_score"] = round(score.total, 1)
                    if hasattr(score, 'breakdown'):
                        candidate_detail["breakdown"] = {k: round(v, 2) for k, v in score.breakdown.items()}
                    if score.total > best_score:
                        best_score = score.total
                        best_pos = {"x": tx, "y": ty, "z": tz, "rotation": trot}

                all_candidate_details.append(candidate_detail)

            if best_pos is not None:
                best_debug_entry = {
                    "package_name": pkg.name,
                    "candidates_evaluated": candidates_tried,
                    "all_candidate_details": all_candidate_details,
                    "best_score": round(best_score, 1),
                    "chosen_position": best_pos,
                    "valid_candidates_found": True,
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
                else:
                    result.failed_packages += 1
                    result.unplaced_packages.append(pkg.name)
                    if best_debug_entry:
                        best_debug_entry["valid_candidates_found"] = False
            else:
                result.failed_packages += 1
                result.unplaced_packages.append(pkg.name)
                best_debug_entry = {
                    "package_name": pkg.name,
                    "candidates_evaluated": candidates_tried,
                    "best_score": 0.0,
                    "chosen_position": None,
                    "valid_candidates_found": False,
                }

            if debug and best_debug_entry:
                result.debug_log.append(best_debug_entry)

            if progress_callback:
                progress_callback(result.placed_packages + result.failed_packages, total, best_score if best_score > 0 else 0.0)

        from .distribution import reassign_load_sequences
        reassign_load_sequences(planner.placements)

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
