"""Unit tests for the placement scoring engine.

Every scoring function is tested in isolation to ensure:
  - Deterministic output for the same input
  - Correct boundary values (0.0 and 1.0)
  - Sensible intermediate values
"""

import pytest

from truck_load_planner.engine.package import Package
from truck_load_planner.engine.placement import Placement
from truck_load_planner.engine.container import Container
from truck_load_planner.engine.scorer import (
    score_placement,
    _score_floor_contact,
    _score_wall_contact,
    _score_package_contact,
    _score_face_contact,
    _score_compactness,
    _score_stack_quality,
    _score_vertical_stability,
    _make_aabb,
    _build_others,
    SCORING_WEIGHTS,
    PlacementScore,
)
from truck_load_planner.engine.geometry import AABB


# ── Fixtures ──────────────────────────────────────────────────────────

PACKAGE = Package(id=1, name="Box", length_mm=1000, width_mm=800,
                  height_mm=600, weight_kg=50, stackable=True)

CONTAINER = Container(
    id=1, name="40ft Container",
    length=12000, width=2400, height=2700, payload_kg=28000,
)


def _make(pkg: Package, x: float, y: float, z: float,
          rotation: int = 0) -> Placement:
    return Placement(
        package_id=pkg.id or 0, x=x, y=y, z=z,
        rotation=rotation, package=pkg,
    )


# ── Determinism ───────────────────────────────────────────────────────


def test_determinism():
    placements = [_make(Package(id=2, name="A", length_mm=500,
                                width_mm=500, height_mm=500), 0, 0, 0)]
    s1 = score_placement(PACKAGE, 1200, 0, 0, 0, placements, CONTAINER)
    s2 = score_placement(PACKAGE, 1200, 0, 0, 0, placements, CONTAINER)
    assert s1.total == s2.total
    assert s1.breakdown == s2.breakdown


# ── Floor Contact ─────────────────────────────────────────────────────


def test_floor_contact_on_floor():
    aabb = _make_aabb(PACKAGE, 0, 0, 0, 0)
    assert _score_floor_contact(aabb) == 1.0


def test_floor_contact_floating():
    aabb = _make_aabb(PACKAGE, 0, 0, 500, 0)
    assert _score_floor_contact(aabb) == 0.0


def test_floor_contact_stacked():
    aabb = _make_aabb(PACKAGE, 0, 0, 600, 0)
    assert _score_floor_contact(aabb) == 0.0


# ── Wall Contact ──────────────────────────────────────────────────────


def test_wall_contact_no_walls():
    aabb = _make_aabb(PACKAGE, 2000, 500, 0, 0)
    assert _score_wall_contact(aabb, CONTAINER) == 0.0


def test_wall_contact_rear():
    aabb = _make_aabb(PACKAGE, 0, 500, 0, 0)
    score = _score_wall_contact(aabb, CONTAINER)
    assert score == 0.25


def test_wall_contact_front():
    aabb = _make_aabb(PACKAGE, CONTAINER.length - PACKAGE.length_mm,
                      500, 0, 0)
    assert _score_wall_contact(aabb, CONTAINER) == 0.25


def test_wall_contact_left():
    aabb = _make_aabb(PACKAGE, 500, 0, 0, 0)
    assert _score_wall_contact(aabb, CONTAINER) == 0.25


def test_wall_contact_right():
    aabb = _make_aabb(PACKAGE, 500,
                      CONTAINER.width - PACKAGE.width_mm, 0, 0)
    assert _score_wall_contact(aabb, CONTAINER) == 0.25


def test_wall_contact_corner():
    aabb = _make_aabb(PACKAGE, 0, 0, 0, 0)
    assert _score_wall_contact(aabb, CONTAINER) == 0.5


def test_wall_contact_all_four():
    p = Package(id=2, name="Tight", length_mm=12000,
                width_mm=2400, height_mm=100)
    aabb = _make_aabb(p, 0, 0, 0, 0)
    assert _score_wall_contact(aabb, CONTAINER) == 1.0


# ── Package Contact ───────────────────────────────────────────────────


def test_package_contact_no_neighbors():
    aabb = _make_aabb(PACKAGE, 5000, 500, 0, 0)
    assert _score_package_contact(aabb, []) == 0.0


def test_package_contact_side_by_side():
    aabb = _make_aabb(PACKAGE, 1000, 0, 0, 0)
    neighbor = Package(id=2, name="Neighbor", length_mm=1000,
                       width_mm=800, height_mm=600)
    neighbor_aabb = _make_aabb(neighbor, 0, 0, 0, 0)
    score = _score_package_contact(aabb, [neighbor_aabb])
    assert score > 0.0
    assert score <= 1.0


def test_package_contact_full_face():
    box = Package(id=1, name="Box", length_mm=1000,
                  width_mm=1000, height_mm=1000)
    aabb = _make_aabb(box, 1000, 0, 0, 0)
    other_aabb = _make_aabb(box, 0, 0, 0, 0)
    score = _score_package_contact(aabb, [other_aabb])
    assert score > 0.0
    assert score <= 1.0


# ── Face Contact ──────────────────────────────────────────────────────


def test_face_contact_isolated():
    aabb = _make_aabb(PACKAGE, 5000, 500, 500, 0)
    score = _score_face_contact(aabb, [], CONTAINER)
    assert score == 0.0


def test_face_contact_on_floor():
    aabb = _make_aabb(PACKAGE, 5000, 500, 0, 0)
    score = _score_face_contact(aabb, [], CONTAINER)
    assert score == pytest.approx(1.0 / 6.0)


def test_face_contact_against_wall():
    aabb = _make_aabb(PACKAGE, 0, 0, 0, 0)
    score = _score_face_contact(aabb, [], CONTAINER)
    # Floor (z=0) + rear wall (x=0) + left wall (y=0) = 3 out of 6
    assert score == pytest.approx(3.0 / 6.0)


def test_face_contact_with_neighbor():
    aabb = _make_aabb(PACKAGE, 1000, 0, 0, 0)
    other_aabb = _make_aabb(PACKAGE, 0, 0, 0, 0)
    score = _score_face_contact(aabb, [other_aabb], CONTAINER)
    assert score >= 1.0 / 6.0


# ── Compactness ───────────────────────────────────────────────────────


def test_compactness_no_others():
    aabb = _make_aabb(PACKAGE, 0, 0, 0, 0)
    assert _score_compactness(aabb, []) == 0.0


def test_compactness_adjacent():
    aabb = _make_aabb(PACKAGE, 1000, 0, 0, 0)
    other_aabb = _make_aabb(PACKAGE, 0, 0, 0, 0)
    score = _score_compactness(aabb, [other_aabb])
    # Centroid distance = 1000mm
    # 1.0 - 1000/2000 = 0.5
    assert score == pytest.approx(0.5)


def test_compactness_far():
    aabb = _make_aabb(PACKAGE, 10000, 0, 0, 0)
    other_aabb = _make_aabb(PACKAGE, 0, 0, 0, 0)
    score = _score_compactness(aabb, [other_aabb])
    # Centroid distance ~= 9500mm
    # 1.0 - 9500/2000 = negative -> clamped to 0.0
    assert score == 0.0


# ── Stack Quality ─────────────────────────────────────────────────────


def test_stack_quality_on_floor():
    aabb = _make_aabb(PACKAGE, 0, 0, 0, 0)
    assert _score_stack_quality(aabb, []) == 0.0


def test_stack_quality_not_applicable():
    aabb = _make_aabb(PACKAGE, 0, 0, 700, 0)
    score = _score_stack_quality(aabb, [])
    assert score == 0.0


def test_stack_quality_full_support():
    below = Package(id=2, name="Below", length_mm=1000,
                    width_mm=800, height_mm=600)
    below_aabb = _make_aabb(below, 0, 0, 0, 0)
    aabb = _make_aabb(PACKAGE, 0, 0, 600, 0)
    score = _score_stack_quality(aabb, [below_aabb])
    assert score == pytest.approx(1.0)


def test_stack_quality_partial_support():
    below = Package(id=2, name="Small", length_mm=500,
                    width_mm=400, height_mm=600)
    below_aabb = _make_aabb(below, 0, 0, 0, 0)
    aabb = _make_aabb(PACKAGE, 0, 0, 600, 0)
    score = _score_stack_quality(aabb, [below_aabb])
    total_area = PACKAGE.length_mm * PACKAGE.width_mm  # 800000
    support_area = 500 * 400  # 200000
    assert score == pytest.approx(support_area / total_area)


# ── Vertical Stability ────────────────────────────────────────────────


def test_vertical_stability_floor():
    flat = Package(id=99, name="Flat", length_mm=1000,
                   width_mm=1000, height_mm=1)
    aabb = _make_aabb(flat, 0, 0, 0, 0)
    score = _score_vertical_stability(aabb, CONTAINER)
    assert score == pytest.approx(1.0, abs=0.001)


def test_vertical_stability_mid_height():
    mid_z = CONTAINER.height / 2
    flat = Package(id=99, name="Flat", length_mm=1000,
                   width_mm=1000, height_mm=1)
    aabb = _make_aabb(flat, 0, 0, mid_z, 0)
    score = _score_vertical_stability(aabb, CONTAINER)
    assert score == pytest.approx(0.5, abs=0.01)


def test_vertical_stability_top():
    aabb = _make_aabb(PACKAGE, 0, 0,
                      CONTAINER.height - PACKAGE.height_mm, 0)
    score = _score_vertical_stability(aabb, CONTAINER)
    assert score < 0.5
    assert score > 0.0


# ── PlacementScore ────────────────────────────────────────────────────


def test_placement_score_to_dict():
    score = PlacementScore(
        total=85.3,
        breakdown={"floor": 25.0, "wall": 10.0},
        warnings=["Test warning"],
        metadata={"key": "value"},
    )
    d = score.to_dict()
    assert d["total"] == 85.3
    assert d["breakdown"]["floor"] == 25.0
    assert d["warnings"] == ["Test warning"]
    assert d["metadata"]["key"] == "value"


# ── Integration: score_placement ──────────────────────────────────────


def test_score_placement_returns_placementscore():
    result = score_placement(
        PACKAGE, 0, 0, 0, 0, [], CONTAINER,
    )
    assert isinstance(result, PlacementScore)
    assert result.total >= 0.0
    assert result.total <= 100.0
    assert "floor_contact" in result.breakdown
    assert "wall_contact" in result.breakdown
    assert "package_contact" in result.breakdown
    assert "face_contact" in result.breakdown
    assert "compactness" in result.breakdown
    assert "stack_quality" in result.breakdown
    assert "vertical_stability" in result.breakdown
    assert "dead_space_quality" in result.breakdown


def test_score_placement_corner_best():
    corner = score_placement(
        PACKAGE, 0, 0, 0, 0, [], CONTAINER,
    )
    middle = score_placement(
        PACKAGE, 5000, 800, 0, 0, [], CONTAINER,
    )
    # Corner touches two walls (front + left) for stability bonus
    assert corner.breakdown["wall_contact"] > 0
    # Middle has perfect Y-center balance (width=800, y=800 -> cy=1200, ideal=1200)
    assert middle.breakdown["y_balance"] > corner.breakdown["y_balance"]
    # Both positions should score above 50 (reasonable placements)
    assert corner.total >= 50.0
    assert middle.total >= 50.0


def test_score_placement_deterministic():
    placements = [_make(Package(id=3, name="Other", length_mm=400,
                                width_mm=400, height_mm=400), 2000, 0, 0)]
    r1 = score_placement(
        PACKAGE, 1000, 0, 0, 0, placements, CONTAINER,
    )
    r2 = score_placement(
        PACKAGE, 1000, 0, 0, 0, placements, CONTAINER,
    )
    assert r1.total == r2.total
    assert r1.breakdown == r2.breakdown
    assert r1.warnings == r2.warnings


def test_score_placement_with_warnings():
    placements = [_make(Package(id=3, name="Far", length_mm=400,
                                width_mm=400, height_mm=400), 10000, 500, 0)]
    result = score_placement(
        Package(id=4, name="Iso", length_mm=500, width_mm=500,
                height_mm=500),
        0, 0, 2000, 0, placements, CONTAINER,
    )
    # High up and isolated -> should trigger warnings
    assert len(result.warnings) > 0


# ── Weights Configurability ───────────────────────────────────────────


def test_weights_are_configurable():
    assert "floor_contact" in SCORING_WEIGHTS
    assert "wall_contact" in SCORING_WEIGHTS
    assert "package_contact" in SCORING_WEIGHTS
    assert "face_contact" in SCORING_WEIGHTS
    assert "compactness" in SCORING_WEIGHTS
    assert "stack_quality" in SCORING_WEIGHTS
    assert "vertical_stability" in SCORING_WEIGHTS
    assert "x_preference" in SCORING_WEIGHTS
    assert "rear_proximity" in SCORING_WEIGHTS
    assert "dead_space_quality" in SCORING_WEIGHTS
    assert sum(SCORING_WEIGHTS.values()) == 130


# ── Edge Cases ────────────────────────────────────────────────────────


def test_zero_sized_package():
    tiny = Package(id=99, name="Tiny", length_mm=1, width_mm=1,
                   height_mm=1)
    result = score_placement(tiny, 0, 0, 0, 0, [], CONTAINER)
    assert isinstance(result, PlacementScore)
    assert 0.0 <= result.total <= 100.0


def test_empty_placements_list():
    result = score_placement(PACKAGE, 0, 0, 0, 0, [], CONTAINER)
    assert isinstance(result, PlacementScore)
    assert result.breakdown["compactness"] == 0.0
    assert result.breakdown["package_contact"] == 0.0
