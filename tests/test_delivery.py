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
from services.delivery.database import init_delivery_tables
from app.db import DatabaseManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    """Mimics Flask's FileStorage for testing."""
    def __init__(self, content: bytes, filename: str):
        self.content = content
        self.filename = filename

    def save(self, path):
        with open(path, "wb") as f:
            f.write(self.content)


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
        plan_id = _create_plan(db_path)
        assignment_id = _create_vehicle_assignment(db_path, plan_id)

        prog = execution_service.get_assignment_progress(db_path, assignment_id)
        assert prog["total"] == 1  # fallback to avoid div-by-zero
        assert prog["progress_pct"] == 0.0

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
