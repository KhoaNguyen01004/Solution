"""Tests for the background route refresher's geofence advance.

Why this file exists
--------------------
``app/routes/trips.py`` had no tests. The 2026-08-06 audit found that its
geofence loop opened an explicit ``conn.execute('BEGIN')`` inside a per-trip
``for``, which can never work:

  * Python's sqlite3 already opens a transaction implicitly before the
    driver-name ``UPDATE`` that precedes it, so the explicit BEGIN raised
    ``cannot start a transaction within a transaction``; and
  * on the normal path (vehicle not yet at its stop) neither commit branch
    ran, so the transaction stayed open and the *next* iteration's BEGIN
    raised the same error.

The per-trip ``except`` printed and moved on, so the symptom was not an error
anybody saw — it was trips that quietly stopped advancing. That is the worst
shape of bug to have no test for, hence these.

``test_all_active_trips_are_processed`` and
``test_a_later_trip_still_advances_its_phase`` both fail against the pre-fix
code; the rest pin the behaviour the restructure had to preserve.
"""
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_BOOT_FD, _BOOT_DB = tempfile.mkstemp(suffix="-trips-boot.db")
os.close(_BOOT_FD)
os.environ["DB_PATH"] = _BOOT_DB

from app import config, state                      # noqa: E402
from app.database import init_db                   # noqa: E402
from app.routes import trips as trips_module       # noqa: E402


# A square around (10.80, 106.60), ~0.02 degrees a side. The shape is copied
# from a real entry in manual_locations.json — a "polygons" list of [lat, lng]
# pairs — rather than invented. A fixture in a format production never sends
# asserts a contract that does not exist, which is exactly how the delivery
# suite came to pass against code that could not work (audit T-01/T-02).
DEPOT_POLYGON = {
    "polygons": [[
        [10.79, 106.59],
        [10.81, 106.59],
        [10.81, 106.61],
        [10.79, 106.61],
    ]],
    "type": "multi_polygon",
}
INSIDE = (10.80, 106.60)
OUTSIDE = (10.50, 106.20)


@pytest.fixture
def db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    monkeypatch.setattr(config, "DB_PATH", path)
    yield path
    os.unlink(path)


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch):
    """`state` is process-global and the refresher writes the route cache."""
    monkeypatch.setattr(state, "known_locations", {"Depot": DEPOT_POLYGON})
    monkeypatch.setattr(state, "route_data_cache", {})
    monkeypatch.setattr(state, "last_manual_update", 0)
    yield


@pytest.fixture(autouse=True)
def no_network():
    """Never let a test reach OpenRouteService.

    `do_refresh_route_data` calls get_route_coords once per trip after the
    geofence block; the real one falls back to a straight line on failure, but
    only after a request attempt.
    """
    with patch.object(trips_module, "get_route_coords", return_value={
        "coordinates": [[106.6, 10.8], [106.7, 10.9]],
        "distance": 12.3,
        "duration": 900,
        "status": "ok",
    }):
        yield


def _add_trip(db, vehicle_id, *, status="active", phase=1, driver_name="Old Driver",
              dest_name="Depot", dest=INSIDE, queue_order=0, waypoints=None):
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO vehicle_trips (vehicle_id, vehicle_name, destination_lat, "
        "destination_lng, destination_name, status, queue_order, phase, "
        "driver_name, waypoints) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (str(vehicle_id), f"Truck {vehicle_id}", dest[0], dest[1], dest_name,
         status, queue_order, str(phase), driver_name,
         json.dumps(waypoints) if waypoints else None),
    )
    trip_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    return trip_id


def _raw_ttas(vehicle_id, lat, lng, driver="New Driver"):
    """A raw TTAS DevList item, the shape fetch_vehicle_data returns."""
    return {
        "id": str(vehicle_id),
        "devimei": f"IMEI-{vehicle_id}",
        "biensoxe": f"50E-1846{vehicle_id}",
        "latitude": str(lat),
        "longitude": str(lng),
        "speed": "Chạy 42km/h",
        "ad3": "Nổ",
        "trktime": "06/08/2026 09:00:00",
        "driver": driver,
    }


def _with_positions(*items):
    return patch.object(trips_module, "fetch_vehicle_data",
                        return_value=(list(items), "live", None))


def _trip(db, trip_id):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return dict(conn.execute(
            "SELECT * FROM vehicle_trips WHERE id = ?", (trip_id,)).fetchone())
    finally:
        conn.close()


class TestGeofenceLoop:

    def test_all_active_trips_are_processed(self, db, capsys):
        """Three trips, none arrived, all with a changed driver name.

        Against the pre-fix code every one of these raised
        "cannot start a transaction within a transaction" and was swallowed by
        the per-trip handler. The driver-name write is the observable proof
        the iteration actually ran to its commit.
        """
        ids = [_add_trip(db, v) for v in (1, 2, 3)]

        with _with_positions(*[_raw_ttas(v, *OUTSIDE) for v in (1, 2, 3)]):
            assert trips_module.do_refresh_route_data() is True

        assert "cannot start a transaction" not in capsys.readouterr().out
        for trip_id in ids:
            assert _trip(db, trip_id)["driver_name"] == "New Driver"

    def test_a_later_trip_still_advances_its_phase(self, db):
        """The third trip arrives; the first two have not.

        Pre-fix, iterations 2 and 3 never reached the geofence check at all,
        so this trip could not advance no matter where its truck was.
        """
        _add_trip(db, 1)
        _add_trip(db, 2)
        arriving = _add_trip(db, 3)

        with _with_positions(_raw_ttas(1, *OUTSIDE),
                             _raw_ttas(2, *OUTSIDE),
                             _raw_ttas(3, *INSIDE)):
            trips_module.do_refresh_route_data()

        # One stop (destination only), so arriving completes the trip.
        assert _trip(db, arriving)["status"] == "completed"

    def test_no_transaction_is_left_open(self, db):
        """The leftover open transaction is what held a RESERVED lock across
        this function's ORS calls. A second connection writing afterwards is
        the direct test of that."""
        _add_trip(db, 1)

        with _with_positions(_raw_ttas(1, *OUTSIDE)):
            trips_module.do_refresh_route_data()

        conn = sqlite3.connect(db, timeout=1.0)
        try:
            conn.execute("UPDATE vehicle_trips SET customer_name = 'x'")
            conn.commit()
        finally:
            conn.close()

    def test_arrival_at_final_stop_activates_the_queued_trip(self, db):
        """Pins the branch whose `continue` the restructure removed."""
        arriving = _add_trip(db, 1, queue_order=0)
        queued = _add_trip(db, 1, status="queued", queue_order=1)

        with _with_positions(_raw_ttas(1, *INSIDE)):
            trips_module.do_refresh_route_data()

        assert _trip(db, arriving)["status"] == "completed"
        assert _trip(db, queued)["status"] == "active"
        # `phase` has TEXT affinity (added by migrations.py), so the integer
        # the handler writes comes back as '1'. Compared as int deliberately —
        # the column's type is not what this test is about.
        assert int(_trip(db, queued)["phase"]) == 1

    def test_multi_stop_trip_advances_phase_instead_of_completing(self, db):
        """Two stops: arriving at the waypoint advances to phase 2, and the
        trip stays active. The `else` branch of the same if/else."""
        trip_id = _add_trip(
            db, 1, dest_name="Far Place", dest=OUTSIDE,
            waypoints=[{"name": "Depot", "lat": INSIDE[0], "lng": INSIDE[1]}],
        )

        with _with_positions(_raw_ttas(1, *INSIDE)):
            trips_module.do_refresh_route_data()

        row = _trip(db, trip_id)
        assert row["status"] == "active"
        assert int(row["phase"]) == 2

    def test_one_failing_trip_does_not_stop_the_others(self, db):
        """The per-trip handler stays deliberately broad. A trip whose
        waypoint JSON is missing 'lat' raises inside the geofence block; the
        others must still commit their work."""
        broken = _add_trip(db, 1, dest_name="Depot", dest=INSIDE,
                           waypoints=[{"name": "Nowhere"}])
        healthy = _add_trip(db, 2)

        with _with_positions(_raw_ttas(1, *INSIDE), _raw_ttas(2, *OUTSIDE)):
            assert trips_module.do_refresh_route_data() is True

        assert _trip(db, broken)["status"] == "active"          # rolled back
        assert _trip(db, healthy)["driver_name"] == "New Driver"  # committed

    def test_a_rolled_back_trip_keeps_its_previous_driver_name(self, db):
        """The driver-name UPDATE moved inside the transaction, so it has to
        roll back with the rest of the iteration rather than leak through."""
        broken = _add_trip(db, 1, driver_name="Old Driver",
                           dest_name="Depot", dest=INSIDE,
                           waypoints=[{"name": "Nowhere"}])

        with _with_positions(_raw_ttas(1, *INSIDE, driver="New Driver")):
            trips_module.do_refresh_route_data()

        assert _trip(db, broken)["driver_name"] == "Old Driver"
