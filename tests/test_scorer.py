import pytest

from truck_load_planner.engine.package import Package
from truck_load_planner.engine.placement import Placement
from truck_load_planner.engine.container import Container
from truck_load_planner.engine.scorer import (
    score_placement,
    _score_floor_contact,
    _score_package_contact,
    _score_x_preference,
    _score_y_balance,
    _make_aabb,
    _build_others,
    SCORING_WEIGHTS,
    PlacementScore,
)
from truck_load_planner.engine.geometry import AABB


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


def test_determinism():
    placements = [_make(Package(id=2, name="A", length_mm=500,
                                width_mm=500, height_mm=500), 0, 0, 0)]
    s1 = score_placement(PACKAGE, 1200, 0, 0, 0, placements, CONTAINER)
    s2 = score_placement(PACKAGE, 1200, 0, 0, 0, placements, CONTAINER)
    assert s1.total == s2.total
    assert s1.breakdown == s2.breakdown


def test_floor_contact_on_floor():
    aabb = _make_aabb(PACKAGE, 0, 0, 0, 0)
    assert _score_floor_contact(aabb) == 1.0


def test_floor_contact_floating():
    aabb = _make_aabb(PACKAGE, 0, 0, 500, 0)
    assert _score_floor_contact(aabb) == 0.0


def test_floor_contact_stacked():
    aabb = _make_aabb(PACKAGE, 0, 0, 600, 0)
    assert _score_floor_contact(aabb) == 0.0


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


def test_x_preference_deep():
    aabb = _make_aabb(PACKAGE, 0, 0, 0, 0)
    score = _score_x_preference(aabb, CONTAINER)
    # xmax = 1000mm (package length), container length = 12000mm
    # ratio = 1000/12000, score = (1 - 1000/12000)^3
    assert score == pytest.approx(0.770, abs=0.01)


def test_x_preference_door():
    aabb = _make_aabb(PACKAGE, CONTAINER.length - PACKAGE.length_mm, 0, 0, 0)
    score = _score_x_preference(aabb, CONTAINER)
    assert score < 0.01


def test_y_balance_centered():
    w = CONTAINER.width
    pkg = Package(id=2, name="Center", length_mm=500, width_mm=500,
                  height_mm=500, weight_kg=50)
    aabb = _make_aabb(pkg, 0, (w - 500) / 2, 0, 0)
    score = _score_y_balance(aabb, pkg, [], CONTAINER)
    assert score == pytest.approx(1.0, abs=0.01)


def test_y_balance_edge():
    pkg = Package(id=2, name="Edge", length_mm=500, width_mm=500,
                  height_mm=500, weight_kg=50)
    aabb = _make_aabb(pkg, 0, 0, 0, 0)
    score = _score_y_balance(aabb, pkg, [], CONTAINER)
    assert score < 0.5


def test_placement_score_to_dict():
    score = PlacementScore(
        total=85.3,
        breakdown={"contact": 50.0, "x": 20.0},
        warnings=["Test warning"],
        metadata={"key": "value"},
    )
    d = score.to_dict()
    assert d["total"] == 85.3
    assert d["breakdown"]["contact"] == 50.0
    assert d["warnings"] == ["Test warning"]
    assert d["metadata"]["key"] == "value"


def test_score_placement_returns_placementscore():
    result = score_placement(
        PACKAGE, 0, 0, 0, 0, [], CONTAINER,
    )
    assert isinstance(result, PlacementScore)
    "package_contact" in result.breakdown
    "x_preference" in result.breakdown
    "floor_contact" in result.breakdown
    "y_balance" in result.breakdown


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


def test_weights_are_configurable():
    assert "package_contact" in SCORING_WEIGHTS
    assert "x_preference" in SCORING_WEIGHTS
    assert "floor_contact" in SCORING_WEIGHTS
    assert "y_balance" in SCORING_WEIGHTS


def test_zero_sized_package():
    tiny = Package(id=99, name="Tiny", length_mm=1, width_mm=1,
                   height_mm=1)
    result = score_placement(tiny, 0, 0, 0, 0, [], CONTAINER)
    assert isinstance(result, PlacementScore)


def test_empty_placements_list():
    result = score_placement(PACKAGE, 0, 0, 0, 0, [], CONTAINER)
    assert isinstance(result, PlacementScore)
    assert result.breakdown["package_contact"] == 0.0
