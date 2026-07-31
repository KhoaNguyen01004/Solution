import io
import os
import sys
import json
import sqlite3
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.delivery import plan_service
from services.delivery import execution_service
from services.delivery import eta_service
from services.delivery import image_service
from services.delivery import tracking_service
from services import vehicle_identity
from services.delivery.database import init_delivery_tables
from app.db import DatabaseManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_upload_root(tmp_path, monkeypatch):
    """Keep uploaded test images out of the repository.

    image_service derives UPLOAD_ROOT from its own file location, so the image
    tests were writing real .jpg files into the project's DeliveryPlans/ folder
    and leaving them behind — dozens had accumulated across previous runs. It
    also made test_delete_image_removes_file depend on the checkout being
    writable, which it isn't on every machine.
    """
    from services.delivery import image_service

    root = tmp_path / "DeliveryPlans"
    root.mkdir()
    monkeypatch.setattr(image_service, "BASE_DIR", tmp_path)
    monkeypatch.setattr(image_service, "UPLOAD_ROOT", root)
    yield root


@pytest.fixture
def db_path():
    """Create a fresh SQLite database with all delivery + vehicles tables."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Init delivery tables first
    init_delivery_tables(path)

    # Also create vehicles table (normally created by app.py init_db)
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number TEXT NOT NULL UNIQUE,
            vehicle_type TEXT DEFAULT '',
            current_driver TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("INSERT INTO vehicles (plate_number, current_driver) VALUES ('TEST-01', 'Test Driver')")
    conn.commit()
    conn.close()

    yield path

    os.unlink(path)


def _create_plan(db_path, name="Test Plan", plan_date="2026-07-26"):
    return plan_service.create_plan(db_path, name, plan_date)


def _create_vehicle_assignment(db_path, plan_id, vehicle_id=1):
    return plan_service.create_assignment(db_path, plan_id, vehicle_id, sequence=1)


def _create_stop(db_path, assignment_id, seq, station_name="Stop", lat=10.8, lng=106.6):
    return plan_service.create_stop(
        db_path, assignment_id, seq,
        station_code=f"S{seq:03d}", station_name=station_name,
        address=f"{seq} Test St", lat=lat, lng=lng,
        manager_name="Mr T", manager_phone="0900000000",
        product_description="Test Product",
    )


# ===========================================================================
# 1. ETA Calculation Tests
# ===========================================================================

class TestEtaService:
    """Tests for eta_service.py: Haversine fallback and ORS integration."""

    def test_get_distance_meters(self):
        d = eta_service.get_distance_meters(10.8, 106.6, 10.9, 106.7)
        assert d > 10000  # ~15 km
        assert d < 20000

    def test_get_distance_meters_zero(self):
        d = eta_service.get_distance_meters(10.8, 106.6, 10.8, 106.6)
        assert d == 0.0

    def test_calculate_eta_no_api_key_fallback(self):
        result = eta_service.calculate_eta("", "", 10.8, 106.6, 10.9, 106.7)
        assert result["source"] == "haversine"
        assert result["distance_km"] > 10
        assert result["duration_sec"] is None

    @patch("services.delivery.eta_service.requests.get")
    def test_calculate_eta_ors_success(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "features": [{
                "geometry": {"coordinates": [[106.6, 10.8], [106.7, 10.9]]},
                "properties": {"segments": [{"distance": 15000, "duration": 900}]}
            }]
        }
        result = eta_service.calculate_eta("fake_key", "https://api.ors/v2/directions", 10.8, 106.6, 10.9, 106.7)
        assert result["source"] == "ors"
        assert result["distance_km"] == 15.0
        assert result["duration_sec"] == 900
        # GeoJSON [lng, lat] must be converted to Leaflet [lat, lng]
        assert result["geometry"] == [[10.8, 106.6], [10.9, 106.7]]

    def test_calculate_eta_no_api_key_has_no_geometry(self):
        result = eta_service.calculate_eta("", "", 10.8, 106.6, 10.9, 106.7)
        assert result["geometry"] is None

    @patch("services.delivery.eta_service.requests.get")
    def test_calculate_eta_ors_failure_fallback(self, mock_get):
        mock_get.side_effect = Exception("Connection error")
        result = eta_service.calculate_eta("fake_key", "https://api.ors/v2/directions", 10.8, 106.6, 10.9, 106.7)
        assert result["source"] == "haversine_fallback"
        assert result["distance_km"] > 10
        assert result["duration_sec"] is None

    @patch("services.delivery.eta_service.calculate_eta")
    def test_calculate_etas_for_stops(self, mock_calc_eta):
        mock_calc_eta.return_value = {"source": "haversine", "distance_km": 5.0, "duration_sec": 300}
        stops = [
            {"id": 1, "lat": 10.81, "lng": 106.61},
            {"id": 2, "lat": 10.82, "lng": 106.62},
            {"id": 3, "lat": None, "lng": None},
        ]
        results = eta_service.calculate_etas_for_stops("", "", 10.8, 106.6, stops)
        assert len(results) == 3
        assert results[0]["cumulative_sec"] == 300
        assert results[1]["cumulative_sec"] == 600
        assert results[2]["cumulative_sec"] is None  # no coords
        assert results[2]["distance_km"] is None

    def test_calculate_etas_empty_list(self):
        assert eta_service.calculate_etas_for_stops("", "", 10.8, 106.6, []) == []

    @patch("services.delivery.eta_service.calculate_eta")
    def test_calculate_etas_tracks_cumulative_km_and_geometry(self, mock_calc_eta):
        mock_calc_eta.return_value = {
            "source": "ors", "distance_km": 5.0, "duration_sec": 300,
            "geometry": [[10.8, 106.6], [10.81, 106.61]],
        }
        stops = [{"id": 1, "lat": 10.81, "lng": 106.61}, {"id": 2, "lat": 10.82, "lng": 106.62}]
        results = eta_service.calculate_etas_for_stops("", "", 10.8, 106.6, stops)
        assert results[0]["cumulative_km"] == 5.0
        assert results[1]["cumulative_km"] == 10.0
        assert results[0]["geometry"] == [[10.8, 106.6], [10.81, 106.61]]

    @patch("services.delivery.eta_service.calculate_eta")
    def test_route_cache_hit_skips_recompute(self, mock_calc_eta):
        mock_calc_eta.return_value = {"source": "haversine", "distance_km": 5.0, "duration_sec": 300, "geometry": None}
        stops = [{"id": 1, "lat": 10.81, "lng": 106.61}]

        r1 = eta_service.calculate_etas_for_stops("", "", 10.8, 106.6, stops, assignment_id=90001)
        r2 = eta_service.calculate_etas_for_stops("", "", 10.8, 106.6, stops, assignment_id=90001)

        assert mock_calc_eta.call_count == 1
        assert r1 == r2

    @patch("services.delivery.eta_service.calculate_eta")
    def test_route_cache_invalidated_by_gps_move(self, mock_calc_eta):
        mock_calc_eta.return_value = {"source": "haversine", "distance_km": 5.0, "duration_sec": 300, "geometry": None}
        stops = [{"id": 1, "lat": 10.81, "lng": 106.61}]

        eta_service.calculate_etas_for_stops("", "", 10.8, 106.6, stops, assignment_id=90002)
        eta_service.calculate_etas_for_stops("", "", 11.5, 107.3, stops, assignment_id=90002)

        assert mock_calc_eta.call_count == 2

    @patch("services.delivery.eta_service.calculate_eta")
    def test_route_cache_tolerates_tiny_gps_jitter(self, mock_calc_eta):
        mock_calc_eta.return_value = {"source": "haversine", "distance_km": 5.0, "duration_sec": 300, "geometry": None}
        stops = [{"id": 1, "lat": 10.81, "lng": 106.61}]

        eta_service.calculate_etas_for_stops("", "", 10.80000, 106.60000, stops, assignment_id=90003)
        eta_service.calculate_etas_for_stops("", "", 10.80001, 106.60001, stops, assignment_id=90003)

        assert mock_calc_eta.call_count == 1

    @patch("services.delivery.eta_service.calculate_eta")
    def test_route_cache_invalidated_by_stop_change(self, mock_calc_eta):
        mock_calc_eta.return_value = {"source": "haversine", "distance_km": 5.0, "duration_sec": 300, "geometry": None}
        stops1 = [{"id": 1, "lat": 10.81, "lng": 106.61}]
        stops2 = [{"id": 2, "lat": 10.82, "lng": 106.62}]

        eta_service.calculate_etas_for_stops("", "", 10.8, 106.6, stops1, assignment_id=90004)
        eta_service.calculate_etas_for_stops("", "", 10.8, 106.6, stops2, assignment_id=90004)

        assert mock_calc_eta.call_count == 2

    @patch("services.delivery.eta_service.calculate_eta")
    def test_route_cache_bypassed_without_assignment_id(self, mock_calc_eta):
        mock_calc_eta.return_value = {"source": "haversine", "distance_km": 5.0, "duration_sec": 300, "geometry": None}
        stops = [{"id": 1, "lat": 10.81, "lng": 106.61}]

        eta_service.calculate_etas_for_stops("", "", 10.8, 106.6, stops)
        eta_service.calculate_etas_for_stops("", "", 10.8, 106.6, stops)

        assert mock_calc_eta.call_count == 2

    def test_travelled_distance_zero_when_nothing_passed(self):
        stops = [{"id": 1, "lat": 10.81, "lng": 106.61, "planned_sequence": 1, "execution_status": "planned"}]
        assert eta_service.calculate_travelled_distance_km(stops, 10.8, 106.6) == 0.0

    def test_travelled_distance_sums_passed_stops(self):
        stops = [
            {"id": 1, "lat": 10.81, "lng": 106.61, "planned_sequence": 1, "execution_status": "completed"},
            {"id": 2, "lat": 10.82, "lng": 106.62, "planned_sequence": 2, "execution_status": "skipped"},
            {"id": 3, "lat": 10.83, "lng": 106.63, "planned_sequence": 3, "execution_status": "planned"},
        ]
        result = eta_service.calculate_travelled_distance_km(stops, 10.82, 106.62)
        assert result > 0


# ===========================================================================
# 1b. Tracking Service Tests (defensive speed parsing)
# ===========================================================================

def _raw_ttas(**overrides):
    """A raw TTAS DevList item — the actual input contract of
    normalize_gps_position(). Keys are TTAS's own, NOT normalize_vehicle()'s
    output names."""
    item = {
        "biensoxe": "50E-18463",
        "latitude": "10.8",
        "longitude": "106.6",
        "speed": "Chạy 42km/h",
        "ad3": "Nổ",
        "trktime": "2026-07-30 10:00:00",
        "driver": "Nguyen Van A",
    }
    item.update(overrides)
    return item


class TestTrackingService:
    """Tests for tracking_service.py.

    These previously fed hand-written dicts keyed on speed_status /
    vehicle_status / last_update — the OUTPUT names of normalize_vehicle(),
    not the raw TTAS input names the function actually receives. They passed
    against a function that could never work in production (audit C-02/T-02).
    They now use real raw-TTAS field names.
    """

    def test_emits_device_name_and_plate_key(self):
        # The regression that broke the entire dashboard: no device_name was
        # emitted, so no GPS position could ever be matched to a vehicle.
        result = tracking_service.normalize_gps_position(_raw_ttas())
        assert result["device_name"] == "50E-18463"
        assert result["plate_key"] == "18463"

    @pytest.mark.parametrize("plate,expected_key", [
        ("50E-18463", "18463"),
        ("50E18463", "18463"),
        ("50E 18463", "18463"),
        ("18463", "18463"),
        ("50e-18463", "18463"),
    ])
    def test_plate_key_is_stable_across_formats(self, plate, expected_key):
        result = tracking_service.normalize_gps_position(_raw_ttas(biensoxe=plate))
        assert result["plate_key"] == expected_key

    def test_reads_raw_ttas_field_names(self):
        result = tracking_service.normalize_gps_position(_raw_ttas())
        assert result["speed"] == "Chạy 42km/h"       # from "speed", not "speed_status"
        assert result["engine_status"] == "Nổ"         # from "ad3"
        assert result["last_update"] == "2026-07-30 10:00:00"  # from "trktime"
        assert result["driver_name"] == "Nguyen Van A"  # from "driver"
        assert result["vehicle_status"] == "running"    # derived from the speed phrase

    def test_coordinates_are_floats(self):
        result = tracking_service.normalize_gps_position(_raw_ttas())
        assert result["lat"] == pytest.approx(10.8)
        assert result["lng"] == pytest.approx(106.6)

    def test_missing_coordinates_become_none_not_zero(self):
        # safe_float() coerces junk to 0.0; 0,0 is the Gulf of Guinea, not a
        # vehicle position, so it must be reported as "no fix".
        result = tracking_service.normalize_gps_position(
            _raw_ttas(latitude=None, longitude=None)
        )
        assert result["lat"] is None
        assert result["lng"] is None

    def test_malformed_coordinates_do_not_raise(self):
        # A bare float() here used to raise ValueError inside a list
        # comprehension and 500 the whole dashboard request.
        result = tracking_service.normalize_gps_position(_raw_ttas(latitude="", longitude="n/a"))
        assert result["lat"] is None and result["lng"] is None

    def test_vehicle_status_stopped_engine_on_vs_off(self):
        on = tracking_service.normalize_gps_position(_raw_ttas(speed="Dừng đỗ", ad3="Nổ"))
        off = tracking_service.normalize_gps_position(_raw_ttas(speed="Dừng đỗ", ad3="Tắt"))
        assert on["vehicle_status"] == "stopped_engine_on"
        assert off["vehicle_status"] == "stopped_engine_off"

    def test_speed_parses_embedded_number(self):
        result = tracking_service.normalize_gps_position(_raw_ttas(speed="Chạy 42km/h"))
        assert result["speed_kmh"] == 42.0

    def test_speed_parses_decimal(self):
        result = tracking_service.normalize_gps_position(_raw_ttas(speed="Chạy 37.5 km/h"))
        assert result["speed_kmh"] == 37.5

    def test_speed_none_when_unparseable(self):
        result = tracking_service.normalize_gps_position(_raw_ttas(speed="Dừng đỗ"))
        assert result["speed_kmh"] is None

    def test_speed_none_when_missing(self):
        result = tracking_service.normalize_gps_position(_raw_ttas(speed=""))
        assert result["speed_kmh"] is None

    def test_speed_never_defaults_to_zero(self):
        # A genuine 0 km/h reading and "we don't know" must stay distinguishable.
        unparseable = tracking_service.normalize_gps_position(_raw_ttas(speed="unknown state"))
        assert unparseable["speed_kmh"] is None
        stopped = tracking_service.normalize_gps_position(_raw_ttas(speed="Chạy 0km/h"))
        assert stopped["speed_kmh"] == 0.0


# ===========================================================================
# 2. Stop Progression Tests (advance, skip, cancel)
# ===========================================================================

class TestStopProgression:
    """Tests for execution_service.py: current stop, advance, skip, cancel."""

    def test_current_stop_none(self, db_path):
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        stop = execution_service.get_current_stop(db_path, assignment_id)
        assert stop is None

    def test_advance_planned_to_completed(self, db_path):
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        stop_id = _create_stop(db_path, assignment_id, 1)

        stop = execution_service.get_current_stop(db_path, assignment_id)
        assert stop["id"] == stop_id
        assert stop["execution_status"] == "planned"

        ok, msg = execution_service.advance_stop(db_path, stop_id)
        assert ok
        assert msg == "advanced"

        stop = execution_service.get_stop_execution(db_path, stop_id)
        assert stop["status"] == "arrived"
        assert stop["actual_arrival_at"] is not None

        ok, msg = execution_service.advance_stop(db_path, stop_id)
        assert ok

        stop = execution_service.get_stop_execution(db_path, stop_id)
        assert stop["status"] == "completed"
        assert stop["completed_at"] is not None

    def test_advance_already_completed_fails(self, db_path):
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        stop_id = _create_stop(db_path, assignment_id, 1)

        execution_service.advance_stop(db_path, stop_id)
        execution_service.advance_stop(db_path, stop_id)
        ok, msg = execution_service.advance_stop(db_path, stop_id)
        assert not ok
        assert "Cannot advance" in msg

    def test_current_stop_advances_to_next(self, db_path):
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        s1 = _create_stop(db_path, assignment_id, 1, "Stop A")
        s2 = _create_stop(db_path, assignment_id, 2, "Stop B")

        cs = execution_service.get_current_stop(db_path, assignment_id)
        assert cs["id"] == s1

        execution_service.advance_stop(db_path, s1)
        execution_service.advance_stop(db_path, s1)

        cs = execution_service.get_current_stop(db_path, assignment_id)
        assert cs["id"] == s2

    def test_skip_stop(self, db_path):
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        stop_id = _create_stop(db_path, assignment_id, 1)

        ok = execution_service.skip_stop(db_path, stop_id, "Out of stock")
        assert ok

        exec_ = execution_service.get_stop_execution(db_path, stop_id)
        assert exec_["status"] == "skipped"
        assert exec_["skip_reason"] == "Out of stock"

    def test_cancel_stop(self, db_path):
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        stop_id = _create_stop(db_path, assignment_id, 1)

        ok = execution_service.cancel_stop(db_path, stop_id, "Customer cancelled")
        assert ok

        exec_ = execution_service.get_stop_execution(db_path, stop_id)
        assert exec_["status"] == "cancelled"
        assert exec_["cancel_reason"] == "Customer cancelled"

    def test_skip_advances_current_stop(self, db_path):
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        s1 = _create_stop(db_path, assignment_id, 1, "Stop A")
        s2 = _create_stop(db_path, assignment_id, 2, "Stop B")

        execution_service.skip_stop(db_path, s1)
        cs = execution_service.get_current_stop(db_path, assignment_id)
        assert cs["id"] == s2


# ===========================================================================
# 2b. Plan Auto-Completion Tests
# ===========================================================================

class TestPlanAutoCompletion:
    """Tests for execution_service.py: a plan auto-completes once every
    stop across every vehicle assignment under it reaches a terminal
    state (completed/skipped/cancelled) — otherwise nothing ever leaves
    the dashboard's active (confirmed/executing) view."""

    def test_plan_completes_when_all_stops_terminal(self, db_path):
        plan_id = _create_plan(db_path)
        plan_service.update_plan(db_path, plan_id, status="confirmed")
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        s1 = _create_stop(db_path, assignment_id, 1)
        s2 = _create_stop(db_path, assignment_id, 2)

        execution_service.advance_stop(db_path, s1)  # planned -> arrived
        execution_service.advance_stop(db_path, s1)  # arrived -> completed
        assert plan_service.get_plan(db_path, plan_id)["status"] == "confirmed"

        execution_service.skip_stop(db_path, s2)
        assert plan_service.get_plan(db_path, plan_id)["status"] == "completed"

    def test_plan_not_completed_while_a_stop_remains(self, db_path):
        plan_id = _create_plan(db_path)
        plan_service.update_plan(db_path, plan_id, status="confirmed")
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        s1 = _create_stop(db_path, assignment_id, 1)
        _create_stop(db_path, assignment_id, 2)

        execution_service.cancel_stop(db_path, s1, "test")
        assert plan_service.get_plan(db_path, plan_id)["status"] == "confirmed"

    def test_plan_requires_every_assignment_terminal(self, db_path):
        plan_id = _create_plan(db_path)
        plan_service.update_plan(db_path, plan_id, status="executing")
        a1 = _create_vehicle_assignment(db_path, plan_id)
        a2 = _create_vehicle_assignment(db_path, plan_id)
        s1 = _create_stop(db_path, a1, 1)
        s2 = _create_stop(db_path, a2, 1)

        execution_service.cancel_stop(db_path, s1, "done")
        assert plan_service.get_plan(db_path, plan_id)["status"] == "executing"

        execution_service.cancel_stop(db_path, s2, "done")
        assert plan_service.get_plan(db_path, plan_id)["status"] == "completed"

    def test_insert_temp_stop_reopens_completed_plan(self, db_path):
        plan_id = _create_plan(db_path)
        plan_service.update_plan(db_path, plan_id, status="executing")
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        s1 = _create_stop(db_path, assignment_id, 1)
        execution_service.skip_stop(db_path, s1)
        assert plan_service.get_plan(db_path, plan_id)["status"] == "completed"

        execution_service.insert_temp_stop(db_path, assignment_id, after_sequence=1, station_name="New Stop")
        assert plan_service.get_plan(db_path, plan_id)["status"] == "executing"


# ===========================================================================
# 3. Stop Reordering Tests
# ===========================================================================

class TestStopReordering:
    """Tests for execution_service.py: reorder_stops and insert_temp_stop."""

    def test_reorder_stops(self, db_path):
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        s1 = _create_stop(db_path, assignment_id, 1, "First")
        s2 = _create_stop(db_path, assignment_id, 2, "Second")
        s3 = _create_stop(db_path, assignment_id, 3, "Third")

        execution_service.reorder_stops(db_path, assignment_id, [s3, s1, s2])

        cs = execution_service.get_current_stop(db_path, assignment_id)
        assert cs["id"] == s3  # s3 is now first in execution order

    def test_reorder_affects_current_stop(self, db_path):
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        s1 = _create_stop(db_path, assignment_id, 1, "A")
        s2 = _create_stop(db_path, assignment_id, 2, "B")
        s3 = _create_stop(db_path, assignment_id, 3, "C")

        execution_service.reorder_stops(db_path, assignment_id, [s3, s2, s1])
        cs = execution_service.get_current_stop(db_path, assignment_id)
        assert cs["id"] == s3

        execution_service.skip_stop(db_path, s3)
        cs = execution_service.get_current_stop(db_path, assignment_id)
        assert cs["id"] == s2

    def test_insert_temp_stop(self, db_path):
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        s1 = _create_stop(db_path, assignment_id, 1, "A")
        s2 = _create_stop(db_path, assignment_id, 2, "B")

        new_id = execution_service.insert_temp_stop(
            db_path, assignment_id, after_sequence=0,
            station_name="Temp", lat=10.85, lng=106.65,
        )
        assert new_id is not None

        cs = execution_service.get_current_stop(db_path, assignment_id)
        assert cs["id"] == new_id

    def test_insert_temp_stop_after_first(self, db_path):
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        s1 = _create_stop(db_path, assignment_id, 1, "A")
        s2 = _create_stop(db_path, assignment_id, 2, "B")

        execution_service.insert_temp_stop(
            db_path, assignment_id, after_sequence=1,
            station_name="Inserted", lat=10.85, lng=106.65,
        )

        stops = plan_service.list_stops(db_path, assignment_id)
        names = [s["station_name"] for s in stops]
        assert "A" in names
        assert "B" in names
        assert "Inserted" in names

    def test_insert_temp_stop_updates_execution_sequences(self, db_path):
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        s1 = _create_stop(db_path, assignment_id, 1, "A")
        s2 = _create_stop(db_path, assignment_id, 2, "B")

        execution_service.insert_temp_stop(
            db_path, assignment_id, after_sequence=1,
            station_name="Inserted",
        )

        stops = plan_service.list_stops(db_path, assignment_id)
        for s in stops:
            if s["station_name"] == "Inserted":
                assert s["execution_sequence"] == 2
            elif s["station_name"] == "B":
                assert s["execution_sequence"] == 3


# ===========================================================================
# 4. Image Upload Tests
# ===========================================================================

class FakeFileStorage:
    """Mimics Werkzeug's FileStorage for testing.

    Now exposes ``.stream`` because that is what a real FileStorage provides
    and what image_service._validate_upload seeks over to size the upload
    without buffering it. The previous fake had only ``.filename`` and
    ``.save()``, which let it pass tests that a real upload could not.
    """
    def __init__(self, content: bytes, filename: str):
        self.content = content
        self.filename = filename
        self.stream = io.BytesIO(content)

    def save(self, path):
        self.stream.seek(0)
        with open(path, "wb") as f:
            f.write(self.stream.read())


class TestImageService:
    """Tests for image_service.py: upload, list, get, delete."""

    def test_upload_and_list_images(self, db_path):
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        stop_id = _create_stop(db_path, assignment_id, 1)

        fake_file = FakeFileStorage(b"fake_image_data", "test_photo.jpg")

        img_id = image_service.upload_image(
            db_path, stop_id, fake_file,
            category="delivery",
            uploaded_by="Tester",
        )
        assert img_id is not None

        images = image_service.list_images(db_path, stop_id)
        assert len(images) == 1
        assert images[0]["category"] == "delivery"
        assert images[0]["original_filename"] == "test_photo.jpg"

        img = image_service.get_image(db_path, img_id)
        assert img is not None
        assert img["id"] == img_id

    def test_upload_multiple_categories(self, db_path):
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        stop_id = _create_stop(db_path, assignment_id, 1)

        for cat in ("loading", "delivery", "extra"):
            f = FakeFileStorage(b"data", f"{cat}.jpg")
            image_service.upload_image(db_path, stop_id, f, category=cat)

        images = image_service.list_images(db_path, stop_id)
        assert len(images) == 3
        cats = {i["category"] for i in images}
        assert cats == {"loading", "delivery", "extra"}

    def test_delete_image_removes_file(self, db_path):
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        stop_id = _create_stop(db_path, assignment_id, 1)

        f = FakeFileStorage(b"data", "delete_me.jpg")
        img_id = image_service.upload_image(db_path, stop_id, f)

        img = image_service.get_image(db_path, img_id)
        file_path = image_service.BASE_DIR / img["relative_path"]
        assert file_path.exists()

        ok = image_service.delete_image(db_path, img_id)
        assert ok
        assert not file_path.exists()
        assert image_service.get_image(db_path, img_id) is None

    def test_list_images_empty_stop(self, db_path):
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        stop_id = _create_stop(db_path, assignment_id, 1)

        images = image_service.list_images(db_path, stop_id)
        assert images == []

    def test_upload_to_nonexistent_stop_returns_none(self, db_path):
        f = FakeFileStorage(b"data", "orphan.jpg")
        img_id = image_service.upload_image(db_path, 99999, f)
        assert img_id is None


# ===========================================================================
# 5. Progress & Dashboard Tests
# ===========================================================================

class TestProgress:
    """Tests for execution_service.py: progress calculation."""

    def test_progress_all_planned(self, db_path):
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        _create_stop(db_path, assignment_id, 1)
        _create_stop(db_path, assignment_id, 2)
        _create_stop(db_path, assignment_id, 3)

        prog = execution_service.get_assignment_progress(db_path, assignment_id)
        assert prog["total"] == 3
        assert prog["completed"] == 0
        assert prog["remaining"] == 3
        assert prog["progress_pct"] == 0.0

    def test_progress_partial(self, db_path):
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        s1 = _create_stop(db_path, assignment_id, 1)
        _create_stop(db_path, assignment_id, 2)
        _create_stop(db_path, assignment_id, 3)

        execution_service.advance_stop(db_path, s1)
        execution_service.advance_stop(db_path, s1)

        prog = execution_service.get_assignment_progress(db_path, assignment_id)
        assert prog["completed"] == 1
        assert prog["remaining"] == 2
        assert prog["progress_pct"] == 33.3

    def test_progress_skipped_counts_as_completed(self, db_path):
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        s1 = _create_stop(db_path, assignment_id, 1)
        _create_stop(db_path, assignment_id, 2)

        execution_service.skip_stop(db_path, s1)

        prog = execution_service.get_assignment_progress(db_path, assignment_id)
        assert prog["completed"] == 1
        assert prog["remaining"] == 1

    def test_progress_empty(self, db_path):
        """An assignment with no stops has no stops.

        This test previously asserted `total == 1` with the comment "fallback
        to avoid div-by-zero" — it encoded audit bug C-09 as intended
        behaviour. The `or 1` guard belonged on the division, not the total,
        and the wrong version made the dashboard report "1 remaining" for an
        assignment that had nothing in it.
        """
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)

        prog = execution_service.get_assignment_progress(db_path, assignment_id)
        assert prog["total"] == 0
        assert prog["completed"] == 0
        assert prog["remaining"] == 0
        assert prog["progress_pct"] == 0.0
        assert prog["breakdown"] == {}

    def test_dashboard_data(self, db_path):
        plan_id = _create_plan(db_path, "Dash Plan")
        plan_service.update_plan(db_path, plan_id, status="executing")
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        _create_stop(db_path, assignment_id, 1)

        data = execution_service.get_dashboard_data(db_path)
        assert len(data) == 1
        assert data[0]["plan_name"] == "Dash Plan"
        assert data[0]["current_stop"] is not None
        assert data[0]["progress"]["total"] == 1


# ===========================================================================
# 6. Transaction / Rollback Tests
# ===========================================================================

class TestTransactions:
    """Verify multi-table operations roll back on failure."""

    def test_create_stop_rollback_on_failure(self, db_path):
        with pytest.raises(Exception):
            with DatabaseManager(db_path).connect() as conn:
                conn.execute(
                    "INSERT INTO delivery_plan_stops (vehicle_assignment_id, planned_sequence) VALUES (999, 1)"
                )

        with DatabaseManager(db_path).connect() as conn:
            rows = conn.execute(
                "SELECT COUNT(*) as cnt FROM delivery_plan_stops WHERE vehicle_assignment_id = 999"
            ).fetchone()
            assert rows["cnt"] == 0

    def test_delete_plan_cascades(self, db_path):
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        _create_stop(db_path, assignment_id, 1)
        _create_stop(db_path, assignment_id, 2)

        plan_service.delete_plan(db_path, plan_id)

        assert plan_service.get_plan(db_path, plan_id) is None
        assert plan_service.get_assignment(db_path, assignment_id) is None
        assert len(plan_service.list_stops(db_path, assignment_id)) == 0


# ===========================================================================
# 8. Vehicle Identity Service (Phase 2 — audit C-05, L-03, §5)
# ===========================================================================

def _add_vehicle(db_path, plate):
    with DatabaseManager(db_path).connect() as conn:
        conn.execute("INSERT INTO vehicles (plate_number) VALUES (?)", (plate,))
        return conn.execute("SELECT id FROM vehicles WHERE plate_number = ?", (plate,)).fetchone()["id"]


def _count_vehicles(db_path):
    with DatabaseManager(db_path).connect() as conn:
        return conn.execute("SELECT COUNT(*) c FROM vehicles").fetchone()["c"]


class TestVehicleIdentity:
    """services/vehicle_identity.py — the resolver that replaces five
    mutually incompatible plate-matching schemes (audit §5)."""

    @pytest.mark.parametrize("stored,lookup,matched_by", [
        ("50E-18463", "50E-18463", "exact"),
        ("50E-18463", "50E18463", "canonical"),
        ("50E-18463", "50E 18463", "canonical"),
        ("50E-18463", "50e-18463", "canonical"),
        ("50E-18463", "  50E-18463  ", "exact"),
        ("50E-18463", "18463", "serial"),
        ("50E18463", "50E-18463", "canonical"),
    ])
    def test_resolves_every_plate_format(self, db_path, stored, lookup, matched_by):
        vid = _add_vehicle(db_path, stored)
        with DatabaseManager(db_path).connect() as conn:
            ref = vehicle_identity.resolve(conn, lookup)
        assert ref is not None, f"{lookup!r} failed to resolve against stored {stored!r}"
        assert ref.id == vid
        assert ref.matched_by == matched_by

    def test_unknown_plate_returns_none_and_never_creates(self, db_path):
        before = _count_vehicles(db_path)
        with DatabaseManager(db_path).connect() as conn:
            assert vehicle_identity.resolve(conn, "99Z-00000") is None
        assert _count_vehicles(db_path) == before

    @pytest.mark.parametrize("empty", ["", "   ", None])
    def test_empty_identifier_resolves_to_none(self, db_path, empty):
        with DatabaseManager(db_path).connect() as conn:
            assert vehicle_identity.resolve(conn, empty) is None

    def test_full_plate_wins_over_bare_serial_duplicate(self, db_path):
        """The exact duplicate shape merge_duplicate_vehicles.py cleans up:
        a stray '09473' row alongside the real '50H-09473'."""
        full = _add_vehicle(db_path, "50H-09473")
        _add_vehicle(db_path, "09473")
        with DatabaseManager(db_path).connect() as conn:
            ref = vehicle_identity.resolve(conn, "09473")
        assert ref.id == full and ref.plate_number == "50H-09473"

    def test_ambiguous_serial_refuses_to_guess(self, db_path):
        """Two different full plates sharing a 5-digit serial must not be
        silently collapsed — stops would attach to the wrong truck."""
        a = _add_vehicle(db_path, "50H-18463")
        _add_vehicle(db_path, "51C-18463")
        with DatabaseManager(db_path).connect() as conn:
            assert vehicle_identity.resolve(conn, "18463") is None
            # An exact plate is still unambiguous and must still resolve.
            assert vehicle_identity.resolve(conn, "50H-18463").id == a

    def test_module_exposes_no_write_path(self):
        """Adding a vehicle is a Vehicle Management action. This module must
        never grow a create/insert helper — that is how duplicate rows got
        into `vehicles` in the first place."""
        writes = [n for n in dir(vehicle_identity)
                  if any(w in n.lower() for w in ("create", "insert", "add", "save"))
                  and not n.startswith("_")]
        assert writes == [], f"vehicle_identity must stay read-only, found: {writes}"

    @pytest.mark.parametrize("raw,expected", [
        ("50E-18463", "50E18463"),
        ("50e 18463", "50E18463"),
        ("  50E--18463 ", "50E18463"),
        ("", ""),
        (None, ""),
    ])
    def test_canonical_plate(self, raw, expected):
        assert vehicle_identity.canonical_plate(raw) == expected


class TestImportVehicleResolution:
    """confirm_import must resolve plate variants onto existing rows instead
    of silently creating duplicates (audit C-05) and must not split one truck
    across two assignments (audit L-03)."""

    def _rows(self, *vehicle_keys):
        return [
            {"vehicle": v, "sequence": i + 1, "station_code": f"S{i+1}",
             "station_name": f"Stop {i+1}", "lat": 10.8, "lng": 106.6}
            for i, v in enumerate(vehicle_keys)
        ]

    def test_plate_variants_resolve_to_one_existing_vehicle(self, db_path):
        vid = _add_vehicle(db_path, "50E-18463")
        before = _count_vehicles(db_path)
        plan_id = _create_plan(db_path)

        # Four spellings of the same truck in one file.
        summary = plan_service.confirm_import(
            db_path, plan_id,
            self._rows("50E-18463", "50E18463", "50E 18463", "18463"),
        )

        assert _count_vehicles(db_path) == before, "import created duplicate vehicles (C-05)"
        assert summary["assignments_created"] == 1, "one truck split into multiple assignments (L-03)"
        assert summary["stops_created"] == 4

        plan = plan_service.get_plan(db_path, plan_id)
        assert len(plan["assignments"]) == 1
        assert plan["assignments"][0]["vehicle_id"] == vid

    def test_unknown_vehicle_raises_and_writes_nothing(self, db_path):
        _add_vehicle(db_path, "50E-18463")
        before = _count_vehicles(db_path)
        plan_id = _create_plan(db_path)

        with pytest.raises(plan_service.UnknownVehicles) as exc:
            plan_service.confirm_import(db_path, plan_id, self._rows("50E-18463", "99Z-00000"))

        assert "99Z-00000" in exc.value.identifiers
        assert "50E-18463" not in exc.value.identifiers
        # The whole import is one transaction — a partial write would leave
        # the plan half-imported with no way to tell.
        assert _count_vehicles(db_path) == before
        assert plan_service.get_plan(db_path, plan_id)["assignments"] == []
        assert plan_service.get_plan(db_path, plan_id)["status"] == "draft"

    def test_import_never_creates_a_vehicle_under_any_flag(self, db_path):
        """There is no override. An unknown plate always aborts, and no
        keyword argument can turn the import into a vehicle-creation path."""
        before = _count_vehicles(db_path)
        plan_id = _create_plan(db_path)

        with pytest.raises(plan_service.UnknownVehicles):
            plan_service.confirm_import(db_path, plan_id, self._rows("51D-77777"))
        assert _count_vehicles(db_path) == before

        import inspect
        params = inspect.signature(plan_service.confirm_import).parameters
        assert set(params) == {"db_path", "plan_id", "import_data"}, \
            "confirm_import must not accept a vehicle-creation escape hatch"

    def test_error_names_every_unknown_plate_once(self, db_path):
        """Variants of the same unknown plate collapse to one entry, so the
        dispatcher sees one problem to fix rather than three."""
        plan_id = _create_plan(db_path)
        with pytest.raises(plan_service.UnknownVehicles) as exc:
            plan_service.confirm_import(
                db_path, plan_id, self._rows("51D-77777", "51D77777", "77777")
            )
        assert len(exc.value.identifiers) == 1

    def test_plan_marked_confirmed_once(self, db_path):
        _add_vehicle(db_path, "50E-18463")
        _add_vehicle(db_path, "50H-93571")
        plan_id = _create_plan(db_path)

        summary = plan_service.confirm_import(
            db_path, plan_id, self._rows("50E-18463", "50H-93571"),
        )

        assert summary["plan_confirmed"] is True
        plan = plan_service.get_plan(db_path, plan_id)
        assert plan["status"] == "confirmed"
        assert plan["imported_at"] is not None

    def test_empty_import_leaves_plan_in_draft(self, db_path):
        """Used to return success while the plan silently stayed 'draft' and
        never reached the dashboard (audit L-06) — now reported honestly."""
        plan_id = _create_plan(db_path)
        summary = plan_service.confirm_import(db_path, plan_id, [])
        assert summary["plan_confirmed"] is False
        assert summary["assignments_created"] == 0
        assert plan_service.get_plan(db_path, plan_id)["status"] == "draft"


class TestPreviewImportResolution:
    def test_preview_reports_resolution_when_given_a_db(self, db_path):
        _add_vehicle(db_path, "50E-18463")
        rows = [
            {"vehicle": "50E18463", "sequence": 1, "station_code": "S1", "lat": 10.8, "lng": 106.6},
            {"vehicle": "99Z-00000", "sequence": 1, "station_code": "S2", "lat": 10.8, "lng": 106.6},
        ]
        preview = plan_service.preview_import(rows, db_path=db_path)

        assert preview["vehicles_checked"] is True
        assert preview["unknown_vehicles"] == ["99Z-00000"]
        by_id = {a["vehicle_identifier"]: a for a in preview["assignments"]}
        assert by_id["50E18463"]["resolved"] is True
        assert by_id["50E18463"]["resolved_plate"] == "50E-18463"
        assert by_id["50E18463"]["matched_by"] == "canonical"
        assert by_id["99Z-00000"]["resolved"] is False

    def test_preview_without_db_keeps_old_behaviour(self, db_path):
        rows = [{"vehicle": "50E-18463", "sequence": 1, "station_code": "S1"}]
        preview = plan_service.preview_import(rows)
        assert preview["vehicles_checked"] is False
        assert preview["total_assignments"] == 1
        assert preview["unknown_vehicles"] == []


# ===========================================================================
# 9. Execution correctness (Phase 3 — audit C-07, C-09, reorder validation)
# ===========================================================================

class TestAdvanceAtomicity:
    """A stop must not be walked two steps by one accidental double-tap
    (audit C-07). Dispatch is used on phones; a double-tap is routine."""

    def _stop(self, db_path):
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        return _create_stop(db_path, assignment_id, 1)

    def test_double_advance_with_expected_status_is_refused(self, db_path):
        stop_id = self._stop(db_path)

        ok, msg = execution_service.advance_stop(db_path, stop_id, expected_status="planned")
        assert ok and msg == "advanced"
        assert execution_service.get_stop_execution(db_path, stop_id)["status"] == "arrived"

        # The second tap carries the same token the button was rendered with.
        ok, msg = execution_service.advance_stop(db_path, stop_id, expected_status="planned")
        assert ok is False
        assert "already" in msg.lower()
        # Critically: still 'arrived', not skipped through to 'completed'.
        assert execution_service.get_stop_execution(db_path, stop_id)["status"] == "arrived"

    def test_arrival_is_not_erased_by_a_double_tap(self, db_path):
        """The damage wasn't only the status — arrival and departure were
        stamped in the same second, destroying dwell time."""
        stop_id = self._stop(db_path)
        execution_service.advance_stop(db_path, stop_id, expected_status="planned")
        execution_service.advance_stop(db_path, stop_id, expected_status="planned")

        e = execution_service.get_stop_execution(db_path, stop_id)
        assert e["actual_arrival_at"] is not None
        assert e["actual_departure_at"] is None, "stop was completed by the second tap"

    def test_deliberate_two_step_progression_still_works(self, db_path):
        """The guard must not break the normal flow: a dispatcher advancing
        twice, each time from the status actually on screen."""
        stop_id = self._stop(db_path)

        ok, msg = execution_service.advance_stop(db_path, stop_id, expected_status="planned")
        assert (ok, msg) == (True, "advanced")
        ok, msg = execution_service.advance_stop(db_path, stop_id, expected_status="arrived")
        assert (ok, msg) == (True, "completed")
        assert execution_service.get_stop_execution(db_path, stop_id)["status"] == "completed"

    def test_advance_without_token_still_supported(self, db_path):
        """expected_status is optional — older callers keep working."""
        stop_id = self._stop(db_path)
        assert execution_service.advance_stop(db_path, stop_id)[0] is True
        assert execution_service.get_stop_execution(db_path, stop_id)["status"] == "arrived"

    def test_cannot_advance_a_terminal_stop(self, db_path):
        stop_id = self._stop(db_path)
        execution_service.skip_stop(db_path, stop_id, "no access")
        ok, msg = execution_service.advance_stop(db_path, stop_id)
        assert ok is False and "skipped" in msg


class TestReorderValidation:
    """reorder_stops accepted any list and applied it stop-by-stop, so a
    partial list left duplicate execution_sequence values and ids from another
    assignment silently no-opped while reporting success."""

    def _assignment_with_stops(self, db_path, n=3):
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)
        ids = [_create_stop(db_path, assignment_id, i) for i in range(1, n + 1)]
        return assignment_id, ids

    def test_full_reorder_succeeds(self, db_path):
        aid, ids = self._assignment_with_stops(db_path)
        ok, msg = execution_service.reorder_stops(db_path, aid, [ids[2], ids[0], ids[1]])
        assert ok is True and msg == "reordered"
        assert [s["id"] for s in plan_service.list_stops(db_path, aid)] == [ids[2], ids[0], ids[1]]

    def test_partial_list_is_rejected(self, db_path):
        aid, ids = self._assignment_with_stops(db_path)
        before = [s["id"] for s in plan_service.list_stops(db_path, aid)]

        ok, msg = execution_service.reorder_stops(db_path, aid, [ids[2], ids[1]])
        assert ok is False and "missing" in msg

        # Nothing partially applied — no duplicate sequences left behind.
        assert [s["id"] for s in plan_service.list_stops(db_path, aid)] == before
        seqs = [s["execution_sequence"] for s in plan_service.list_stops(db_path, aid)]
        assert len(seqs) == len(set(seqs)), f"duplicate execution_sequence values: {seqs}"

    def test_foreign_stop_ids_are_rejected(self, db_path):
        aid, ids = self._assignment_with_stops(db_path, n=1)
        other_aid, other_ids = self._assignment_with_stops(db_path, n=1)

        ok, msg = execution_service.reorder_stops(db_path, aid, other_ids)
        assert ok is False
        assert "not in this assignment" in msg

    def test_duplicate_ids_are_rejected(self, db_path):
        aid, ids = self._assignment_with_stops(db_path, n=2)
        ok, msg = execution_service.reorder_stops(db_path, aid, [ids[0], ids[0]])
        assert ok is False and "duplicate" in msg.lower()

    def test_empty_assignment_is_rejected(self, db_path):
        plan_id = _create_plan(db_path)
        aid = _create_vehicle_assignment(db_path, plan_id)
        ok, msg = execution_service.reorder_stops(db_path, aid, [])
        assert ok is False and "no stops" in msg


class TestProgressWithoutStops:
    """audit C-09 — `total = sum(...) or 1` leaked a division guard into the
    reported totals."""

    def test_dashboard_reports_zero_not_one(self, db_path):
        plan_id = _create_plan(db_path, "Empty")
        plan_service.update_plan(db_path, plan_id, status="confirmed")
        _create_vehicle_assignment(db_path, plan_id)

        entry = execution_service.get_dashboard_data(db_path)[0]
        assert entry["progress"]["total"] == 0
        assert entry["progress"]["remaining"] == 0, "dispatcher would chase a stop that doesn't exist"
        assert entry["progress"]["progress_pct"] == 0.0

    def test_percentage_still_correct_with_stops(self, db_path):
        plan_id = _create_plan(db_path)
        aid = _create_vehicle_assignment(db_path, plan_id)
        ids = [_create_stop(db_path, aid, i) for i in range(1, 5)]
        execution_service.skip_stop(db_path, ids[0], "x")

        prog = execution_service.get_assignment_progress(db_path, aid)
        assert (prog["total"], prog["completed"], prog["remaining"]) == (4, 1, 3)
        assert prog["progress_pct"] == 25.0
