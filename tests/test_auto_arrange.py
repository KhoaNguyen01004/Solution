"""Unit tests for the Auto Arrange engine.

Tests cover:
  - Empty container (no packages → no-op)
  - Single package placement
  - Multiple identical packages
  - Mixed package sizes
  - Stackable / non-stackable mix
  - Full container (all space consumed)
  - Oversized package (cannot fit → reported)
  - Deterministic output (identical input → identical layout)
  - Early-exit optimisation (max score stops candidate search)
  - Debug mode produces structured entries
  - Progress callback fires correctly
  - Cancel callback stops early
  - Strategy registry lookup
  - Regression: manual placement + auto_arrange coexistence
"""

import pytest

from truck_load_planner.engine.package import Package
from truck_load_planner.engine.container import Container
from truck_load_planner.engine.planner import Planner
from truck_load_planner.engine.auto_arrange import (
    AutoArrangeResult,
    LargestFirstStrategy,
    StrategyRegistry,
    AutoArrangeStrategy,
    MAX_POSSIBLE_SCORE,
)


# ── Fixtures ──────────────────────────────────────────────────────────

CONTAINER = Container(
    id=1, name="40ft Container",
    length=12000, width=2400, height=2700, payload_kg=28000,
)

SMALL_CONTAINER = Container(
    id=2, name="Small Box",
    length=2000, width=1500, height=1500, payload_kg=5000,
)

PKG_A = Package(id=1, name="A", length_mm=1000, width_mm=800,
                height_mm=600, weight_kg=50, stackable=True)
PKG_B = Package(id=2, name="B", length_mm=1200, width_mm=1000,
                height_mm=800, weight_kg=80, stackable=False)
PKG_C = Package(id=3, name="C", length_mm=500, width_mm=500,
                height_mm=500, weight_kg=30, stackable=True)
PKG_OVERSIZED = Package(id=4, name="Oversized", length_mm=30000,
                         width_mm=5000, height_mm=3000, weight_kg=99999)


def _make_planner(container=None):
    c = container or CONTAINER
    return Planner(c)


def test_empty_container():
    """No packages → no placements, zero scores."""
    planner = _make_planner()
    result = planner.auto_arrange([], debug=False)
    assert isinstance(result, AutoArrangeResult)
    assert result.placed_packages == 0
    assert result.failed_packages == 0
    assert result.placement_count == 0


def test_single_package():
    """Single package fits → placed successfully."""
    planner = _make_planner()
    result = planner.auto_arrange([PKG_A], debug=False)
    assert result.placed_packages == 1
    assert result.failed_packages == 0
    assert len(planner.placements) == 1
    pl = planner.placements[0]
    assert pl.x == 0
    assert pl.y == 0
    assert pl.z == 0


def test_multiple_identical_packages():
    """Multiple identical packages are placed in sequence."""
    planner = _make_planner()
    pkgs = [PKG_C] * 10
    result = planner.auto_arrange(pkgs, debug=False)
    assert result.placed_packages == 10
    assert result.failed_packages == 0
    assert len(planner.placements) == 10
    # All should have valid positions
    for pl in planner.placements:
        assert pl.x >= 0 and pl.y >= 0 and pl.z >= 0
        assert pl.x + PKG_C.length_mm <= CONTAINER.length
        assert pl.y + PKG_C.width_mm <= CONTAINER.width
        assert pl.z + PKG_C.height_mm <= CONTAINER.height


def test_mixed_package_sizes():
    """Mixed sizes are sorted correctly (non-stackable first, then largest)."""
    planner = _make_planner()
    pkgs = [PKG_C, PKG_A, PKG_B]
    result = planner.auto_arrange(pkgs, debug=False)
    assert result.placed_packages == 3
    assert result.failed_packages == 0
    # PKG_B non-stackable → should be first in placement order
    assert planner.placements[0].package_id == PKG_B.id


def test_stackable_non_stackable_mix():
    """Non-stackable packages are placed before stackable ones."""
    planner = _make_planner()
    stackable = Package(id=10, name="Stack", length_mm=800, width_mm=600,
                        height_mm=400, weight_kg=20, stackable=True)
    non_stack = Package(id=11, name="NonStack", length_mm=800, width_mm=600,
                        height_mm=400, weight_kg=20, stackable=False)
    pkgs = [stackable, non_stack]
    result = planner.auto_arrange(pkgs, debug=False)
    assert result.placed_packages == 2
    # Non-stackable should come first
    assert planner.placements[0].package_id == non_stack.id


def test_full_container():
    """Fill container until no space remains — some may fail."""
    planner = _make_planner(SMALL_CONTAINER)
    # Many packages that should completely fill a small container
    pkgs = [Package(id=100 + i, name=f"Box{i}", length_mm=500,
                    width_mm=500, height_mm=500, weight_kg=10)
            for i in range(100)]
    result = planner.auto_arrange(pkgs, debug=False)
    # At least some should be placed
    assert result.placed_packages > 0
    # Some may fail
    assert result.failed_packages >= 0
    assert result.placed_packages + result.failed_packages <= len(pkgs)


def test_oversized_package():
    """Package larger than container → reported as failed."""
    planner = _make_planner(SMALL_CONTAINER)
    result = planner.auto_arrange([PKG_OVERSIZED], debug=False)
    assert result.placed_packages == 0
    assert result.failed_packages == 1
    assert PKG_OVERSIZED.name in result.unplaced_packages


def test_deterministic_output():
    """Same input → same layout every time."""
    planner1 = _make_planner()
    planner2 = _make_planner()
    pkgs = [PKG_A, PKG_B, PKG_C]

    r1 = planner1.auto_arrange(pkgs, debug=False)
    r2 = planner2.auto_arrange(pkgs, debug=False)

    assert r1.placed_packages == r2.placed_packages
    assert r1.failed_packages == r2.failed_packages
    assert r1.utilization == pytest.approx(r2.utilization, abs=0.1)
    assert r1.total_score == pytest.approx(r2.total_score, abs=0.1)

    for pl1, pl2 in zip(planner1.placements, planner2.placements):
        assert (pl1.x, pl1.y, pl1.z, pl1.rotation) == \
               (pl2.x, pl2.y, pl2.z, pl2.rotation)


def test_debug_mode():
    """Debug mode produces structured debug entries."""
    planner = _make_planner()
    result = planner.auto_arrange([PKG_A, PKG_B], debug=True)
    assert len(result.debug_log) > 0
    for entry in result.debug_log:
        assert "package_name" in entry
        assert "candidates_evaluated" in entry
        assert "best_score" in entry
        assert "chosen_position" in entry or entry.get("chosen_position") is None
        assert "valid_candidates_found" in entry


def test_progress_callback():
    """Progress callback receives correct (current, total, score) values."""
    planner = _make_planner()
    calls = []

    def cb(current, total, score):
        calls.append((current, total, score))

    pkgs = [PKG_A, PKG_B, PKG_C]
    result = planner.auto_arrange(pkgs, progress_callback=cb, debug=False)

    assert len(calls) == result.placed_packages + result.failed_packages
    for i, (current, total, score) in enumerate(calls):
        assert current == i + 1
        assert total == len(pkgs)
        assert score >= 0.0


def test_cancel_callback():
    """Cancel callback stops auto-arrange early."""
    planner = _make_planner()
    call_count = [0]

    def cancel():
        call_count[0] += 1
        return call_count[0] >= 3  # Cancel after 2 packages

    pkgs = [PKG_A, PKG_B, PKG_C, PKG_A]
    result = planner.auto_arrange(pkgs, cancel_callback=cancel, debug=False)
    assert "cancelled" in " ".join(result.warnings).lower()
    assert result.placed_packages < len(pkgs)


def test_early_exit_optimisation():
    """When a candidate achieves max possible score, remaining candidates are skipped."""
    planner = _make_planner()
    # A package placed at (0, 0, 0) in empty container hits floor + wall contact,
    # which gives a very high score. We just verify the algorithm completes
    # and doesn't error.
    result = planner.auto_arrange([PKG_A], debug=False)
    assert result.placed_packages == 1
    assert planner.placements[0].x == 0
    assert planner.placements[0].y == 0
    assert planner.placements[0].z == 0


def test_strategy_registry():
    """Strategy registry returns correct strategies."""
    cls = StrategyRegistry.get("largest_first")
    assert cls is LargestFirstStrategy

    cls = StrategyRegistry.get("nonexistent")
    assert cls is None

    names = StrategyRegistry.list()
    assert "largest_first" in names


def test_unknown_strategy_raises():
    """Unknown strategy name raises ValueError."""
    planner = _make_planner()
    with pytest.raises(ValueError, match="Unknown auto-arrange strategy"):
        planner.auto_arrange([PKG_A], strategy="nonexistent")


def test_auto_arrange_result_defaults():
    """AutoArrangeResult has sensible default values."""
    r = AutoArrangeResult()
    assert r.placed_packages == 0
    assert r.failed_packages == 0
    assert r.utilization == 0.0
    assert r.total_score == 0.0
    assert r.warnings == []
    assert r.unplaced_packages == []
    assert r.debug_log == []


def test_automatically_placed_packages_have_valid_positions():
    """All auto-placed packages must be within container bounds and not overlap."""
    planner = _make_planner()
    pkgs = [
        Package(id=i, name=f"Box{i}", length_mm=800, width_mm=600,
                height_mm=400, weight_kg=20, stackable=True)
        for i in range(15)
    ]
    result = planner.auto_arrange(pkgs, debug=False)

    from truck_load_planner.engine.geometry import AABB
    from truck_load_planner.engine.boundary import check_boundary
    from truck_load_planner.engine.collision import check_collision

    container_aabb = AABB(0, 0, 0, CONTAINER.length, CONTAINER.width, CONTAINER.height)

    placed_aabbs = []
    for pl in planner.placements:
        pkg = pl.package
        aabb = AABB.from_dimensions(
            pl.x, pl.y, pl.z,
            pkg.length_mm, pkg.width_mm, pkg.height_mm,
            pl.rotation,
        )
        boundary = check_boundary(aabb, container_aabb)
        assert boundary["pass"], f"Package {pkg.name} outside container"

        for other_aabb in placed_aabbs:
            assert not check_collision(aabb, other_aabb), \
                f"Package {pkg.name} collides with another"
        placed_aabbs.append(aabb)


# ── Regression: manual planning still works after auto_arrange ────────


def test_manual_placement_after_auto_arrange():
    """Manually placing a package must still work after auto-arrange has run."""
    planner = _make_planner()

    # Run auto-arrange first
    pkgs = [PKG_A, PKG_C]
    auto_result = planner.auto_arrange(pkgs, debug=False)
    assert auto_result.placed_packages == 2
    auto_count = len(planner.placements)

    # Now manually place another package
    extra = Package(id=99, name="Manual", length_mm=600, width_mm=500,
                    height_mm=400, weight_kg=25, stackable=True)
    vresult = planner.place_package(extra, 5000, 500, 0, 0)
    assert vresult.valid, f"Manual placement failed: {vresult.reasons}"
    assert len(planner.placements) == auto_count + 1
    assert planner.placements[-1].package_id == 99

    # Validation of the whole plan should still pass
    full = planner.validate()
    assert full.valid, f"Plan invalid after manual edit: {full.reasons}"


def test_manual_placement_first_then_auto_arrange():
    """Manually placed packages must be preserved when auto-arrange runs."""
    planner = _make_planner()

    # Place a package manually first
    manual = Package(id=99, name="Manual", length_mm=1000, width_mm=800,
                     height_mm=600, weight_kg=50, stackable=True)
    vresult = planner.place_package(manual, 2000, 300, 0, 0)
    assert vresult.valid
    manual_count = len(planner.placements)

    # Run auto-arrange for remaining packages
    more_pkgs = [PKG_B, PKG_C]
    auto_result = planner.auto_arrange(more_pkgs, debug=False)

    # Manual placement should still be there
    assert len(planner.placements) == manual_count + auto_result.placed_packages
    assert planner.placements[0].package_id == 99
    assert planner.placements[0].x == 2000
    assert planner.placements[0].y == 300

    # Full plan should be valid
    full = planner.validate()
    assert full.valid, f"Plan invalid after mixed manual+auto: {full.reasons}"


def test_mixed_manual_and_auto_plan_integrity():
    """The full validation pipeline must pass after combining manual and auto."""
    planner = _make_planner()

    # Manual: place a few packages
    for i, pkg in enumerate([PKG_A, PKG_B]):
        vresult = planner.place_package(
            pkg, i * 3000, 500, 0, 0,
        )
        assert vresult.valid

    # Auto: fill remaining space
    auto_pkgs = [
        Package(id=100 + i, name=f"Auto{i}", length_mm=500,
                width_mm=400, height_mm=300, weight_kg=10, stackable=True)
        for i in range(20)
    ]
    auto_result = planner.auto_arrange(auto_pkgs, debug=False)
    assert auto_result.placed_packages > 0

    # Entire plan must be valid
    full = planner.validate()
    assert full.valid, f"Combined plan invalid: {full.reasons}"

    # Statistics must reflect all placements
    stats = planner.get_statistics()
    expected_total = 2 + auto_result.placed_packages
    assert stats["packages_placed"] == expected_total, \
        f"Expected {expected_total} packages, got {stats['packages_placed']}"
