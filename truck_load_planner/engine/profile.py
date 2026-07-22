from dataclasses import dataclass
from typing import Optional


@dataclass
class PlannerProfile:
    """Single source of truth for all optimization decisions.

    Every tunable parameter lives here — no scattered booleans or
    hardcoded constants in the engine modules.

    Key performance controls:
      - tighten_step_mm: larger = fewer iterations in tighten_position
      - compact_passes: number of full compaction passes
      - compact_step_mm: step used during compaction passes
      - enable_stack_compaction: whether to move entire stack groups
      - candidate_limit: max candidates evaluated per package
    """

    name: str
    enable_rearrangement: bool = True
    enable_repair: bool = False
    floor_rearrangement_limit: int = 10
    max_repair_passes: int = 3
    enable_adaptive_repair: bool = True
    candidate_limit: Optional[int] = None
    repair_time_limit_sec: Optional[float] = None
    optimization_budget_ms: Optional[int] = None
    tighten_step_mm: float = 50.0
    compact_passes: int = 2
    compact_step_mm: float = 50.0
    enable_stack_compaction: bool = True


FAST = PlannerProfile(
    name="fast",
    enable_rearrangement=False,
    enable_repair=False,
    tighten_step_mm=200.0,
    compact_passes=1,
    compact_step_mm=100.0,
    enable_stack_compaction=False,
    candidate_limit=15,
)

BALANCED = PlannerProfile(
    name="balanced",
    enable_rearrangement=True,
    enable_repair=False,
    floor_rearrangement_limit=10,
    tighten_step_mm=50.0,
    compact_passes=2,
    compact_step_mm=50.0,
    enable_stack_compaction=True,
)

MAXIMUM_QUALITY = PlannerProfile(
    name="maximum_quality",
    enable_rearrangement=True,
    enable_repair=True,
    floor_rearrangement_limit=10,
    max_repair_passes=3,
    enable_adaptive_repair=True,
    repair_time_limit_sec=120.0,
    tighten_step_mm=20.0,
    compact_passes=3,
    compact_step_mm=20.0,
    enable_stack_compaction=True,
)

PROFILES: dict[str, PlannerProfile] = {
    "fast": FAST,
    "balanced": BALANCED,
    "maximum_quality": MAXIMUM_QUALITY,
}
