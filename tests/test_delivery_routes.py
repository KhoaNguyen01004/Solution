"""Route-layer tests for the delivery/dispatch HTTP API.

Why this file exists
--------------------
Before 2026-07-31 the delivery module had 49 tests, all of which imported
service modules directly. **Nothing exercised the route layer**, and that is
exactly where every Critical bug in docs/DELIVERY_AUDIT_2026-07-31.md lived:

  - C-01, the import that made GPS silently return an empty list, was one
    line inside a request handler;
  - C-02/C-03, the normalization and plate-matching failures, were only
    observable in an assembled response;
  - C-04, the total absence of authentication, is a property of routes;
  - C-05's duplicate-vehicle write happened behind an endpoint.

A service-level suite cannot see any of those. Worse, the GPS tests that did
exist asserted the *wrong* input contract, so they passed against a function
that could never work in production — false confidence precisely where the
bugs were (audit T-01, T-02).

These tests drive real HTTP through `app.test_client()` with TTAS mocked, so
they cover the assembled request → service → database → JSON path.
"""
import io
import os
import sqlite3
import sys
import tempfile
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# app/config.py reads DB_PATH at import time and app/__init__.py runs
# init_db() against it, so both must point somewhere disposable before the
# application package is imported. An absolute path overrides config's
# BASE_DIR join.
_BOOT_FD, _BOOT_DB = tempfile.mkstemp(suffix="-boot.db")
os.close(_BOOT_FD)
os.environ["DB_PATH"] = _BOOT_DB

from app import create_app                                    # noqa: E402
from app.database.migrations import add_vehicle_envelope_columns  # noqa: E402
from services.delivery import plan_service, execution_service  # noqa: E402
from services.delivery.database import init_delivery_tables    # noqa: E402

# A raw TTAS DevList item. Note the plate has no hyphen while the fleet
# stores "50E-18463" — the mismatch that produced audit C-03.
#
# `trktime` is day-first, as TTAS actually writes it. This fixture used ISO
# until 2026-08-01, which is precisely why nothing here noticed that the
# dashboard was reading the date month-first and reporting every vehicle
# ~205 days stale. A fixture in a format production never sends is a test
# asserting a contract that does not exist.
TTAS_PAYLOAD = [{
    "biensoxe": "50E18463",
    "latitude": "10.8500",
    "longitude": "106.6500",
    "speed": "Chạy 42km/h",
    "ad3": "Nổ",
    "trktime": "31/07/2026 09:00:00",
    "driver": "Driver A",
    "devimei": "IMEI-1",
}]


@pytest.fixture(autouse=True)
def isolated_upload_root(tmp_path, monkeypatch):
    """Redirect proof-of-delivery uploads into a per-test temp directory.

    image_service resolves UPLOAD_ROOT from its own file location, so without
    this the suite writes real .jpg files into the repository's DeliveryPlans/
    folder and leaves them there — the existing service tests have been doing
    exactly that, accumulating stray files across runs.
    """
    from services.delivery import image_service

    root = tmp_path / "DeliveryPlans"
    root.mkdir()
    monkeypatch.setattr(image_service, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(image_service, "UPLOAD_ROOT", root)
    yield root


@pytest.fixture(scope="module")
def app():
    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture
def db(app):
    """A fresh delivery database per test, wired into the app."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_delivery_tables(path)

    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number TEXT NOT NULL UNIQUE,
            vehicle_type TEXT NOT NULL DEFAULT '',
            current_driver TEXT NOT NULL DEFAULT '',
            container_config_id INTEGER DEFAULT NULL
        )
    """)
    # Run the real migration rather than restating its column list here: this
    # fixture hand-writes `vehicles` (the delivery schema doesn't own it), and
    # a duplicated list drifts silently until a query on the new columns blows
    # up in a suite that has nothing to do with them.
    add_vehicle_envelope_columns(conn)
    conn.execute(
        "INSERT INTO vehicles (plate_number, vehicle_type, current_driver) "
        "VALUES ('50E-18463', 'Box Truck', 'Original Driver')"
    )
    conn.commit()
    conn.close()

    app.config["DB_PATH"] = path
    yield path
    os.unlink(path)


@pytest.fixture
def client(app, db):
    """HTTP client. Every endpoint is open — the dispatcher password was
    removed 2026-07-31, so there is no authenticated variant of this."""
    with app.test_client() as c:
        yield c


@pytest.fixture
def plan(db):
    """A confirmed plan with one assignment and three stops, dated *today*.

    The date matters now: correctability is decided per plan-day
    (execution_service.can_revert), so a hard-coded past date would silently
    put every revert test on the refusal path.
    """
    plan_id = plan_service.create_plan(db, "Route Plan", date.today().isoformat())
    plan_service.update_plan(db, plan_id, status="confirmed")
    assignment_id = plan_service.create_assignment(db, plan_id, 1, sequence=1)
    stop_ids = [
        plan_service.create_stop(
            db, assignment_id, i, station_code=f"S{i}", station_name=f"Stop {i}",
            address=f"{i} Main St", lat=10.8 + i / 100, lng=106.6 + i / 100,
            manager_name="Mr T", manager_phone="0900000000",
        )
        for i in (1, 2, 3)
    ]
    return {"plan_id": plan_id, "assignment_id": assignment_id, "stop_ids": stop_ids}


def with_gps(payload=None):
    return patch("services.delivery.routes.fetch_vehicle_data",
                 return_value=(TTAS_PAYLOAD if payload is None else payload, "live", None))


def _ddmm(iso_date):
    """`2026-08-02` → `02_08`, the operator's subfolder date format."""
    y, m, d = str(iso_date)[:10].split("-")
    return f"{d}_{m}"


def _give_proof(db_path, stop_id):
    """Attach the photos a completion requires, without touching the disk.

    The gate reads delivery_stop_images rather than the filesystem, so rows
    are enough — and a test that had to post real .jpg files just to reach
    'completed' would be testing the upload path all over again.
    """
    conn = sqlite3.connect(db_path)
    for cat in execution_service.PROOF_CATEGORIES:
        conn.execute(
            "INSERT INTO delivery_stop_images (stop_id, category, filename, relative_path) "
            "VALUES (?, ?, ?, ?)",
            (stop_id, cat, f"{cat}.jpg", f"DeliveryPlans/{cat}.jpg"),
        )
    conn.commit()
    conn.close()


def _age_execution(db_path, stop_id, minutes):
    """Push a stop's action timestamps into the past.

    Used to show correctability is *not* governed by elapsed time: the rule
    is the plan's date, so an action hours old on today's plan must still be
    correctable.
    """
    then = (datetime.now() - timedelta(minutes=minutes)).isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE stop_executions SET "
        "  actual_arrival_at = CASE WHEN actual_arrival_at IS NULL THEN NULL ELSE ? END, "
        "  completed_at      = CASE WHEN completed_at      IS NULL THEN NULL ELSE ? END "
        "WHERE stop_id = ?",
        (then, then, stop_id),
    )
    conn.commit()
    conn.close()


# ===========================================================================
# GPS pipeline (audit C-01, C-02, C-03)
# ===========================================================================

class TestAssignmentDriverName:
    """The driver typed in the plan builder has to reach the dispatch page.

    The service suite is blind to this one: the builder POSTs to
    /api/assignments, and the field was being dropped in the route handler,
    not in plan_service. Everything below therefore goes over HTTP.
    """

    def _post_assignment(self, client, plan_id, **extra):
        return client.post("/api/assignments", json={
            "plan_id": plan_id, "vehicle_id": 1, "sequence": 1, **extra,
        })

    def test_posted_name_reaches_the_dispatch_dashboard(self, client, db):
        plan_id = plan_service.create_plan(db, "P", date.today().isoformat())
        plan_service.update_plan(db, plan_id, status="confirmed")
        r = self._post_assignment(client, plan_id, driver_name="Nguyen Van Thay")
        assert r.status_code == 201

        with with_gps():
            body = client.get("/api/execution/dashboard").get_json()
        assert body["assignments"][0]["current_driver"] == "Nguyen Van Thay", \
            "dispatcher sees the vehicle's default instead of who is driving today"

    def test_omitting_the_name_keeps_the_vehicle_default(self, client, db):
        plan_id = plan_service.create_plan(db, "P", date.today().isoformat())
        plan_service.update_plan(db, plan_id, status="confirmed")
        self._post_assignment(client, plan_id)

        with with_gps():
            body = client.get("/api/execution/dashboard").get_json()
        assert body["assignments"][0]["current_driver"] == "Original Driver"

    def test_the_name_comes_back_when_the_plan_is_reopened(self, client, db):
        plan_id = plan_service.create_plan(db, "P", date.today().isoformat())
        self._post_assignment(client, plan_id, driver_name="Nguyen Van Thay")

        body = client.get(f"/api/plans/{plan_id}").get_json()
        assert body["assignments"][0]["driver_name"] == "Nguyen Van Thay"

    def test_the_name_can_be_changed_by_put(self, client, db):
        plan_id = plan_service.create_plan(db, "P", date.today().isoformat())
        aid = self._post_assignment(client, plan_id, driver_name="First").get_json()["id"]

        assert client.put(f"/api/assignments/{aid}",
                          json={"driver_name": "Second"}).status_code == 200
        assert client.get(f"/api/assignments/{aid}").get_json()["driver_name"] == "Second"

    def test_a_typed_name_does_not_become_a_driver_record(self, client, db):
        plan_id = plan_service.create_plan(db, "P", date.today().isoformat())
        self._post_assignment(client, plan_id, driver_name="One Off Guy")

        names = [d["name"] for d in client.get("/api/drivers").get_json()]
        assert "One Off Guy" not in names, "a one-off stand-in must not join the roster"


class TestDashboardGps:
    def test_gps_reaches_the_dashboard(self, client, plan):
        """C-01: `from app import fetch_vehicle_data` raised ImportError on
        every request, was swallowed, and returned an empty list."""
        with with_gps():
            body = client.get("/api/execution/dashboard").get_json()
        assert body["gps_source"] == "live"
        assert body["gps_error"] is None
        assert body["gps_matched"] == 1

    def test_assignment_carries_a_gps_block(self, client, plan):
        with with_gps():
            body = client.get("/api/execution/dashboard").get_json()
        gps = body["assignments"][0]["gps"]
        assert gps is not None, "no GPS attached — the map would render no markers"
        assert gps["device_name"] == "50E18463"
        assert gps["lat"] == pytest.approx(10.85)
        assert gps["lng"] == pytest.approx(106.65)

    def test_telemetry_is_read_from_raw_ttas_keys(self, client, plan):
        """C-02: the normalizer read normalize_vehicle()'s *output* names off
        a *raw* TTAS item, so everything but lat/lng silently defaulted."""
        with with_gps():
            gps = client.get("/api/execution/dashboard").get_json()["assignments"][0]["gps"]
        assert gps["speed_kmh"] == 42.0          # from "speed"
        assert gps["vehicle_status"] == "running"  # derived from the speed phrase
        assert gps["engine_status"] == "Nổ"       # from "ad3"
        assert gps["last_update"] == "31/07/2026 09:00:00"  # from "trktime", raw
        assert gps["driver_name"] == "Driver A"   # from "driver"

    def test_dashboard_carries_a_parsed_timestamp(self, client, plan):
        """The dashboard computes GPS age from this field. Reading the raw
        day-first text in the browser gave 8 January for 1 August."""
        with with_gps():
            gps = client.get("/api/execution/dashboard").get_json()["assignments"][0]["gps"]
        assert gps["last_update_iso"] == "2026-07-31T09:00:00"

    @pytest.mark.parametrize("ttas_plate", [
        "50E-18463", "50E18463", "50E 18463", "50e-18463", "18463",
    ])
    def test_plate_formats_all_match_the_same_vehicle(self, client, plan, ttas_plate):
        """C-03: matching was `.strip().lower()` on both sides."""
        payload = [{**TTAS_PAYLOAD[0], "biensoxe": ttas_plate}]
        with with_gps(payload):
            body = client.get("/api/execution/dashboard").get_json()
        assert body["gps_matched"] == 1, f"{ttas_plate!r} failed to match 50E-18463"

    def test_unknown_plate_does_not_match(self, client, plan):
        payload = [{**TTAS_PAYLOAD[0], "biensoxe": "99Z-00000"}]
        with with_gps(payload):
            body = client.get("/api/execution/dashboard").get_json()
        assert body["gps_matched"] == 0
        assert body["assignments"][0].get("gps") is None

    def test_zero_coordinates_are_reported_as_no_fix(self, client, plan):
        """0,0 is the Gulf of Guinea, not a vehicle position."""
        payload = [{**TTAS_PAYLOAD[0], "latitude": "0", "longitude": "0"}]
        with with_gps(payload):
            gps = client.get("/api/execution/dashboard").get_json()["assignments"][0]["gps"]
        assert gps["lat"] is None and gps["lng"] is None

    def test_malformed_coordinates_do_not_500(self, client, plan):
        payload = [{**TTAS_PAYLOAD[0], "latitude": "", "longitude": "n/a"}]
        with with_gps(payload):
            resp = client.get("/api/execution/dashboard")
        assert resp.status_code == 200

    def test_gps_failure_is_reported_not_hidden(self, client, plan):
        with patch("services.delivery.routes.fetch_vehicle_data",
                   return_value=([], "error", "TTAS unreachable")):
            body = client.get("/api/execution/dashboard").get_json()
        assert body["gps_source"] == "error"
        assert body["gps_error"] == "TTAS unreachable"
        assert body["gps_matched"] == 0


class TestEtaEndpoint:
    def test_eta_returns_legs_for_a_matched_vehicle(self, client, plan):
        with with_gps():
            body = client.get(f"/api/eta?assignment_id={plan['assignment_id']}").get_json()
        assert "error" not in body
        assert len(body["etas"]) == 3
        assert body["gps"]["lat"] == pytest.approx(10.85)

    def test_eta_is_not_double_normalized(self, client, plan):
        """C-02 follow-on: the handler normalized an already-normalized dict,
        whose keys are lat/lng not latitude/longitude, coercing both to 0.0."""
        with with_gps():
            body = client.get(f"/api/eta?assignment_id={plan['assignment_id']}").get_json()
        assert body["gps"]["lat"] != 0.0
        assert body["gps"]["lng"] != 0.0

    def test_eta_reports_missing_gps_cleanly(self, client, plan):
        with patch("services.delivery.routes.fetch_vehicle_data", return_value=([], "error", "x")):
            body = client.get(f"/api/eta?assignment_id={plan['assignment_id']}").get_json()
        assert body["etas"] == []
        assert "not available" in body["error"]

    def test_eta_requires_assignment_id(self, client):
        assert client.get("/api/eta").status_code == 400


# ===========================================================================
# Open access
#
# The dispatcher password (audit C-04) was removed on 2026-07-31 at the
# operator's request: this runs on an internal network and the login step
# was costing dispatchers time on every shift change. What used to be the
# authentication suite is now the inverse regression guard — it fails if a
# gate is ever reintroduced without the frontend being taught about it,
# which is how a dispatcher ends up staring at a silent failed action.
# ===========================================================================

MUTATING_ENDPOINTS = [
    ("post",   "/api/drivers"),
    ("post",   "/api/plans"),
    ("put",    "/api/plans/1"),
    ("delete", "/api/plans/1"),
    ("post",   "/api/plans/batch-delete"),
    ("post",   "/api/plans/clear"),
    ("post",   "/api/plans/1/confirm"),
    ("post",   "/api/plans/import/parse"),
    ("post",   "/api/plans/import/save"),
    ("post",   "/api/assignments"),
    ("put",    "/api/assignments/1"),
    ("delete", "/api/assignments/1"),
    ("post",   "/api/stops"),
    ("put",    "/api/stops/1"),
    ("delete", "/api/stops/1"),
    ("post",   "/api/stops/1/skip"),
    ("post",   "/api/stops/1/cancel"),
    ("post",   "/api/stops/reorder"),
    ("post",   "/api/stops/insert"),
    ("post",   "/api/execution/advance"),
    ("post",   "/api/execution/revert"),
    ("post",   "/api/stops/1/images"),
    ("delete", "/api/images/1"),
]

READ_ENDPOINTS = [
    "/api/drivers",
    "/api/plans",
    "/api/assignments",
    "/api/execution/dashboard",
]


class TestOpenAccess:
    @pytest.mark.parametrize("method,path", MUTATING_ENDPOINTS)
    def test_mutating_endpoint_needs_no_session(self, client, method, path):
        """A 401 or 503 here means a gate came back. Anything else — 200, 400
        for a bad body, 404 for the id that does not exist — is fine; this
        test is about reachability, not about each endpoint's contract."""
        resp = getattr(client, method)(path, json={})
        assert resp.status_code not in (401, 403, 503), (
            f"{method.upper()} {path} returned {resp.status_code} — it is gated again"
        )

    @pytest.mark.parametrize("path", READ_ENDPOINTS)
    def test_read_endpoint_stays_open(self, client, path):
        with with_gps():
            assert getattr(client, "get")(path).status_code == 200

    def test_clear_plans_needs_no_session(self, client, db, plan):
        """The most destructive endpoint: cascade-deletes everything. It is
        deliberately reachable — the confirm dialog in the UI is the only
        thing standing in front of it."""
        assert client.post("/api/plans/clear").status_code == 200
        assert plan_service.list_plans(db) == []

    def test_login_route_is_gone(self, client):
        assert client.get("/login").status_code == 404


# ===========================================================================
# Stop execution lifecycle (audit C-07, C-09, C-06b)
# ===========================================================================

class TestExecutionLifecycle:
    def test_full_advance_progression(self, client, db, plan):
        stop_id = plan["stop_ids"][0]

        r = client.post("/api/execution/advance",
                             json={"stop_id": stop_id, "expected_status": "planned"})
        assert r.status_code == 200 and r.get_json()["status"] == "advanced"

        _give_proof(db, stop_id)
        r = client.post("/api/execution/advance",
                             json={"stop_id": stop_id, "expected_status": "arrived"})
        assert r.status_code == 200 and r.get_json()["status"] == "completed"

        e = execution_service.get_stop_execution(db, stop_id)
        assert e["actual_arrival_at"] and e["actual_departure_at"]

    def test_double_tap_cannot_skip_arrived(self, client, db, plan):
        """C-07: two taps took a stop planned -> arrived -> completed, marking
        it delivered with arrival and departure in the same second."""
        stop_id = plan["stop_ids"][0]
        body = {"stop_id": stop_id, "expected_status": "planned"}

        assert client.post("/api/execution/advance", json=body).status_code == 200
        second = client.post("/api/execution/advance", json=body)

        assert second.status_code == 409
        assert second.get_json()["conflict"] is True
        e = execution_service.get_stop_execution(db, stop_id)
        assert e["status"] == "arrived"
        assert e["actual_departure_at"] is None

    def test_advance_without_token_still_works(self, client, db, plan):
        r = client.post("/api/execution/advance", json={"stop_id": plan["stop_ids"][0]})
        assert r.status_code == 200

    def test_advance_requires_stop_id(self, client):
        assert client.post("/api/execution/advance", json={}).status_code == 400

    def test_skip_and_cancel(self, client, db, plan):
        skip_id, cancel_id = plan["stop_ids"][0], plan["stop_ids"][1]

        assert client.post(f"/api/stops/{skip_id}/skip",
                                json={"reason": "gate locked"}).status_code == 200
        assert client.post(f"/api/stops/{cancel_id}/cancel",
                                json={"reason": "customer closed"}).status_code == 200

        assert execution_service.get_stop_execution(db, skip_id)["skip_reason"] == "gate locked"
        assert execution_service.get_stop_execution(db, cancel_id)["cancel_reason"] == "customer closed"

    def test_current_stop_advances_to_the_next(self, client, db, plan):
        first, second = plan["stop_ids"][0], plan["stop_ids"][1]
        client.post(f"/api/stops/{first}/skip", json={"reason": "x"})

        current = client.get(
            f"/api/execution/current?assignment_id={plan['assignment_id']}"
        ).get_json()
        assert current["id"] == second

    def test_plan_auto_completes_when_every_stop_is_terminal(self, client, db, plan):
        for stop_id in plan["stop_ids"]:
            client.post(f"/api/stops/{stop_id}/skip", json={"reason": "x"})
        assert plan_service.get_plan(db, plan["plan_id"])["status"] == "completed"

    def test_progress_endpoint(self, client, db, plan):
        client.post(f"/api/stops/{plan['stop_ids'][0]}/skip", json={"reason": "x"})
        prog = client.get(
            f"/api/execution/progress?assignment_id={plan['assignment_id']}"
        ).get_json()
        assert (prog["total"], prog["completed"], prog["remaining"]) == (3, 1, 2)

    def test_empty_assignment_reports_zero_not_one(self, client, db, plan):
        """C-09: `total = sum(...) or 1` made an empty assignment claim it had
        one remaining stop, sending a dispatcher after nothing."""
        empty_id = plan_service.create_assignment(db, plan["plan_id"], 1, sequence=2)
        with with_gps():
            body = client.get("/api/execution/dashboard").get_json()
        entry = next(a for a in body["assignments"] if a["assignment_id"] == empty_id)
        assert entry["progress"]["total"] == 0
        assert entry["progress"]["remaining"] == 0


class TestRevertEndpoint:
    """Undo for a mis-tapped Advance/Skip/Cancel.

    Route-layer coverage matters here for the same reason it did for advance:
    the guard that makes revert safe is the `expected_status` token, which
    only exists in the request body, and the `can_revert` flag the button is
    drawn from is assembled in a response — neither is visible from the
    service suite.
    """

    def _advance(self, client, stop_id, expected):
        return client.post("/api/execution/advance",
                           json={"stop_id": stop_id, "expected_status": expected})

    def test_revert_undoes_an_accidental_advance(self, client, db, plan):
        stop_id = plan["stop_ids"][0]
        self._advance(client, stop_id, "planned")

        r = client.post("/api/execution/revert",
                        json={"stop_id": stop_id, "expected_status": "arrived"})

        assert r.status_code == 200 and r.get_json()["status"] == "planned"
        e = execution_service.get_stop_execution(db, stop_id)
        assert e["status"] == "planned"
        assert e["actual_arrival_at"] is None, "an un-arrived stop kept its arrival time"

    def test_revert_from_completed_restores_arrived_not_planned(self, client, db, plan):
        """One step back, not all the way. The driver really did arrive; only
        the second tap was the mistake."""
        stop_id = plan["stop_ids"][0]
        self._advance(client, stop_id, "planned")
        _give_proof(db, stop_id)
        self._advance(client, stop_id, "arrived")

        r = client.post("/api/execution/revert",
                        json={"stop_id": stop_id, "expected_status": "completed"})

        assert r.status_code == 200 and r.get_json()["status"] == "arrived"
        e = execution_service.get_stop_execution(db, stop_id)
        assert e["status"] == "arrived"
        assert e["actual_arrival_at"] is not None
        assert e["actual_departure_at"] is None and e["completed_at"] is None

    def test_reverted_stop_becomes_current_again(self, client, db, plan):
        """The point of the feature: a mis-advanced stop moves the dashboard
        on to the next one, and reverting has to move it back."""
        first, second = plan["stop_ids"][0], plan["stop_ids"][1]
        client.post(f"/api/stops/{first}/skip", json={"reason": "mis-tap"})
        url = f"/api/execution/current?assignment_id={plan['assignment_id']}"
        assert client.get(url).get_json()["id"] == second

        client.post("/api/execution/revert",
                    json={"stop_id": first, "expected_status": "skipped"})

        assert client.get(url).get_json()["id"] == first

    def test_revert_of_skip_clears_the_reason(self, client, db, plan):
        stop_id = plan["stop_ids"][0]
        client.post(f"/api/stops/{stop_id}/skip", json={"reason": "gate locked"})

        client.post("/api/execution/revert", json={"stop_id": stop_id})

        e = execution_service.get_stop_execution(db, stop_id)
        assert e["status"] == "planned"
        assert e["skip_reason"] == ""
        assert e["completed_at"] is None

    def test_revert_of_a_skip_after_arrival_returns_to_arrived(self, client, db, plan):
        """A stop skipped once the driver was already there has a real arrival
        time. Sending it back to 'planned' would either strand that timestamp
        or destroy it."""
        stop_id = plan["stop_ids"][0]
        self._advance(client, stop_id, "planned")
        client.post(f"/api/stops/{stop_id}/skip", json={"reason": "nobody home"})

        r = client.post("/api/execution/revert",
                        json={"stop_id": stop_id, "expected_status": "skipped"})

        assert r.get_json()["status"] == "arrived"
        assert execution_service.get_stop_execution(db, stop_id)["actual_arrival_at"] is not None

    def test_revert_reopens_an_auto_completed_plan(self, client, db, plan):
        """_maybe_complete_plan closed the plan on the last stop; undoing that
        stop has to bring it back into the dashboard's active view, or the
        dispatcher can no longer see the vehicle they just corrected."""
        for stop_id in plan["stop_ids"]:
            client.post(f"/api/stops/{stop_id}/skip", json={"reason": "x"})
        assert plan_service.get_plan(db, plan["plan_id"])["status"] == "completed"

        client.post("/api/execution/revert", json={"stop_id": plan["stop_ids"][2]})

        assert plan_service.get_plan(db, plan["plan_id"])["status"] == "executing"

    def test_stale_token_is_refused_as_a_conflict(self, client, db, plan):
        """Same guard as advance: a Revert button rendered before someone else
        moved the stop must not act on the status it can no longer see."""
        stop_id = plan["stop_ids"][0]
        self._advance(client, stop_id, "planned")
        _give_proof(db, stop_id)
        self._advance(client, stop_id, "arrived")

        r = client.post("/api/execution/revert",
                        json={"stop_id": stop_id, "expected_status": "arrived"})

        assert r.status_code == 409 and r.get_json()["conflict"] is True
        assert execution_service.get_stop_execution(db, stop_id)["status"] == "completed"

    def test_double_tapped_undo_does_not_step_back_twice(self, client, db, plan):
        stop_id = plan["stop_ids"][0]
        self._advance(client, stop_id, "planned")
        _give_proof(db, stop_id)
        self._advance(client, stop_id, "arrived")
        body = {"stop_id": stop_id, "expected_status": "completed"}

        assert client.post("/api/execution/revert", json=body).status_code == 200
        assert client.post("/api/execution/revert", json=body).status_code == 409
        assert execution_service.get_stop_execution(db, stop_id)["status"] == "arrived"

    def test_a_planned_stop_has_nothing_to_revert(self, client, plan):
        r = client.post("/api/execution/revert", json={"stop_id": plan["stop_ids"][0]})
        assert r.status_code == 400
        assert "Cannot revert" in r.get_json()["error"]

    def test_revert_requires_stop_id(self, client):
        assert client.post("/api/execution/revert", json={}).status_code == 400

    def test_a_closed_days_plan_is_refused(self, client, db, plan):
        """The button is gone by then, but the endpoint is open and a page
        left up overnight could still post — so the day rule is enforced
        here, not only in the markup."""
        stop_id = plan["stop_ids"][0]
        self._advance(client, stop_id, "planned")
        plan_service.update_plan(db, plan["plan_id"],
                                 plan_date=(date.today() - timedelta(days=1)).isoformat())

        r = client.post("/api/execution/revert", json={"stop_id": stop_id})

        assert r.status_code == 400
        assert "date has passed" in r.get_json()["error"]
        assert execution_service.get_stop_execution(db, stop_id)["status"] == "arrived"

    def test_an_hours_old_action_on_todays_plan_is_still_correctable(self, client, db, plan):
        """The rule that replaced the 15-minute window."""
        stop_id = plan["stop_ids"][0]
        self._advance(client, stop_id, "planned")
        _age_execution(db, stop_id, minutes=8 * 60)

        assert client.post("/api/execution/revert", json={"stop_id": stop_id}).status_code == 200

    def test_stops_response_carries_can_revert(self, client, db, plan):
        """The dashboard draws its Revert button from this flag alone."""
        stop_id = plan["stop_ids"][0]
        self._advance(client, stop_id, "planned")

        stops = client.get(f"/api/stops?assignment_id={plan['assignment_id']}").get_json()
        by_id = {s["id"]: s for s in stops}

        assert by_id[stop_id]["can_revert"] is True
        assert by_id[plan["stop_ids"][1]]["can_revert"] is False, \
            "an untouched stop offered an undo for something that never happened"

    def test_can_revert_closes_with_the_plan_day(self, client, db, plan):
        stop_id = plan["stop_ids"][0]
        self._advance(client, stop_id, "planned")
        plan_service.update_plan(db, plan["plan_id"],
                                 plan_date=(date.today() - timedelta(days=1)).isoformat())

        stops = client.get(f"/api/stops?assignment_id={plan['assignment_id']}").get_json()

        assert next(s for s in stops if s["id"] == stop_id)["can_revert"] is False


class TestProofGateEndpoint:
    """The completion gate as the dashboard meets it. The distinct 422 and
    `proof_required` flag are what let the UI offer an override instead of
    pattern-matching the message text."""

    def _arrived(self, client, plan):
        stop_id = plan["stop_ids"][0]
        client.post("/api/execution/advance", json={"stop_id": stop_id})
        return stop_id

    def test_completion_without_proof_is_422_not_400(self, client, db, plan):
        stop_id = self._arrived(client, plan)

        r = client.post("/api/execution/advance",
                        json={"stop_id": stop_id, "expected_status": "arrived"})
        body = r.get_json()

        assert r.status_code == 422, "400 would read as a malformed request"
        assert body["proof_required"] is True
        assert body["missing"] == ["unload", "door"]

    def test_the_message_names_the_missing_photo(self, client, db, plan):
        stop_id = self._arrived(client, plan)
        _give_proof(db, stop_id)
        conn = sqlite3.connect(db)
        conn.execute("DELETE FROM delivery_stop_images WHERE stop_id = ? AND category = 'door'",
                     (stop_id,))
        conn.commit()
        conn.close()

        body = client.post("/api/execution/advance", json={"stop_id": stop_id}).get_json()

        assert body["missing"] == ["door"]
        assert "locked door" in body["error"]

    def test_the_stop_does_not_move(self, client, db, plan):
        stop_id = self._arrived(client, plan)
        client.post("/api/execution/advance", json={"stop_id": stop_id})

        assert execution_service.get_stop_execution(db, stop_id)["status"] == "arrived"
        assert execution_service.get_stop_execution(db, stop_id)["completed_at"] is None

    def test_an_override_in_the_body_completes_it(self, client, db, plan):
        stop_id = self._arrived(client, plan)

        r = client.post("/api/execution/advance", json={
            "stop_id": stop_id,
            "expected_status": "arrived",
            "override_reason": "phone battery died",
        })

        assert r.status_code == 200 and r.get_json()["status"] == "completed"

    def test_the_override_reason_reaches_the_history_endpoint(self, client, db, plan):
        stop_id = self._arrived(client, plan)
        client.post("/api/execution/advance",
                    json={"stop_id": stop_id, "override_reason": "phone battery died"})

        events = client.get(f"/api/stops/{stop_id}/history").get_json()

        assert events[-1]["reason"] == "phone battery died"

    def test_uploading_both_photos_unblocks_the_normal_path(self, client, db, plan):
        """End to end through the real upload endpoint, not injected rows."""
        stop_id = self._arrived(client, plan)
        assert _upload(client, stop_id, "goods.jpg", category="unload").status_code == 201
        assert _upload(client, stop_id, "door.jpg", category="door").status_code == 201

        r = client.post("/api/execution/advance", json={"stop_id": stop_id})

        assert r.status_code == 200 and r.get_json()["status"] == "completed"


class TestDayExport:
    """The end-of-day handover.

    The photos are already on disk, organised the way they were *written*
    (year/month/day/plate/station/category). The operator hands over a
    different shape entirely, so these assert the ZIP's structure rather
    than merely that a ZIP came back.
    """

    def _zip(self, client, date_str, name="2_8_BacLieuGiaRai", loading_date=None):
        params = f"date={date_str}&name={name}"
        if loading_date:
            params += f"&loading_date={loading_date}"
        resp = client.get(f"/api/export/day.zip?{params}")
        assert resp.status_code == 200
        assert resp.mimetype == "application/zip"
        return zipfile.ZipFile(io.BytesIO(resp.data))

    def _day_upload(self, client, date_str, category, filename="x.jpg", label=""):
        return client.post("/api/export/day-images", data={
            "file": (io.BytesIO(b"bytes"), filename),
            "date": date_str,
            "category": category,
            "label": label,
        }, content_type="multipart/form-data")

    def test_summary_lists_drivers_and_missing_proof(self, client, db, plan):
        today = date.today().isoformat()
        _upload(client, plan["stop_ids"][0], "a.jpg", category="unload")

        body = client.get(f"/api/export/summary?date={today}").get_json()

        assert body["stop_count"] == 3
        assert body["incomplete_count"] == 3, "all three still lack at least one photo"
        stop = body["drivers"][0]["stops"][0]
        assert stop["missing"] == ["door"]

    def test_summary_reports_a_waived_completion(self, client, db, plan):
        stop_id = plan["stop_ids"][0]
        client.post("/api/execution/advance", json={"stop_id": stop_id})
        client.post("/api/execution/advance",
                    json={"stop_id": stop_id, "override_reason": "phone battery died"})

        body = client.get(f"/api/export/summary?date={date.today().isoformat()}").get_json()

        stop = next(s for d in body["drivers"] for s in d["stops"] if s["stop_id"] == stop_id)
        assert stop["override_reason"] == "phone battery died"

    def test_summary_requires_a_date(self, client):
        assert client.get("/api/export/summary").status_code == 400

    def test_stop_photos_are_filed_by_driver_then_station(self, client, db, plan):
        today = date.today().isoformat()
        _upload(client, plan["stop_ids"][0], "goods.jpg", category="unload")
        _upload(client, plan["stop_ids"][0], "door.jpg", category="door")

        names = self._zip(client, today).namelist()

        # Driver folder is "<name>_<5-digit plate serial>"; the fixture
        # vehicle is 50E-18463 with driver "Original Driver".
        expected_dir = f"2_8_BacLieuGiaRai/OriginalDriver_18463/HinhGiaoHang_{_ddmm(today)}/S1/"
        assert any(n.startswith(expected_dir) for n in names), names
        assert sum(1 for n in names if n.startswith(expected_dir)) == 2

    def test_a_photo_that_is_not_proof_is_left_out(self, client, db, plan):
        """An 'extra' shot is not evidence of anything and must not be filed
        alongside the two categories that are."""
        today = date.today().isoformat()
        _upload(client, plan["stop_ids"][0], "random.jpg", category="extra")

        names = self._zip(client, today).namelist()

        assert not any("HinhGiaoHang" in n for n in names), names

    def test_loading_photos_land_in_one_flat_folder(self, client, db, plan):
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        assert self._day_upload(client, today, "loading", "load1.jpg").status_code == 201
        assert self._day_upload(client, today, "loading", "load2.jpg").status_code == 201

        names = self._zip(client, today).namelist()

        folder = f"2_8_BacLieuGiaRai/HinhNhanHang_{_ddmm(yesterday)}/"
        assert sum(1 for n in names if n.startswith(folder)) == 2
        # Flat, as asked — no driver or station level beneath it.
        assert not any(n.startswith(folder) and "/" in n[len(folder):] for n in names)

    def test_the_loading_folder_defaults_to_the_day_before(self, client, db, plan):
        today = date.today().isoformat()
        self._day_upload(client, today, "loading", "load.jpg")

        names = self._zip(client, today).namelist()

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        assert any(f"HinhNhanHang_{_ddmm(yesterday)}/" in n for n in names), names

    def test_the_loading_date_can_be_overridden(self, client, db, plan):
        today = date.today().isoformat()
        self._day_upload(client, today, "loading", "load.jpg")

        names = self._zip(client, today, loading_date="2026-07-20").namelist()

        assert any("HinhNhanHang_20_07/" in n for n in names), names

    def test_empty_container_photos_carry_the_driver_name(self, client, db, plan):
        today = date.today().isoformat()
        self._day_upload(client, today, "empty_container", "truck.jpg",
                         label="Huỳnh Quốc Trọng")

        names = self._zip(client, today).namelist()

        container = [n for n in names if "HinhThungTrong/" in n]
        assert len(container) == 1
        # Accents stripped and words run together, matching the operator's
        # existing folders — and đ/Đ handled, which NFD alone does not.
        assert "HuynhQuocTrong_" in container[0], container[0]

    def test_every_zip_carries_a_manifest(self, client, db, plan):
        today = date.today().isoformat()
        _upload(client, plan["stop_ids"][0], "goods.jpg", category="unload")

        zf = self._zip(client, today)
        manifest = zf.read("2_8_BacLieuGiaRai/manifest.csv").decode()

        assert "station_code" in manifest.splitlines()[0]
        assert "S1" in manifest
        assert "door" in manifest, "the missing photo must be recorded, not just absent"

    def test_the_typed_folder_name_cannot_escape_the_zip(self, client, db, plan):
        """It is free text from a form and becomes a path. S-04 all over
        again if it were trusted."""
        today = date.today().isoformat()
        names = self._zip(client, today, name="../../etc").namelist()

        assert not any(n.startswith("..") or n.startswith("/") for n in names), names

    def test_day_image_upload_rejects_an_unknown_category(self, client, plan):
        r = self._day_upload(client, date.today().isoformat(), "not_a_category")
        assert r.status_code == 400
        assert "Unknown category" in r.get_json()["error"]

    def test_day_image_upload_rejects_a_bad_date(self, client, plan):
        assert self._day_upload(client, "not-a-date", "loading").status_code == 400

    def test_day_images_can_be_listed_and_removed(self, client, db, plan):
        today = date.today().isoformat()
        image_id = self._day_upload(client, today, "loading", "l.jpg").get_json()["id"]

        listed = client.get(f"/api/export/day-images?date={today}&category=loading").get_json()
        assert [i["id"] for i in listed] == [image_id]

        assert client.delete(f"/api/export/day-images/{image_id}").status_code == 200
        assert client.get(f"/api/export/day-images?date={today}").get_json() == []

    def test_removing_a_missing_day_image_404s(self, client, plan):
        assert client.delete("/api/export/day-images/99999").status_code == 404

    def test_a_day_with_nothing_planned_still_exports(self, client, db, plan):
        """An empty ZIP with a manifest beats an error at 6pm."""
        names = self._zip(client, "2026-01-01").namelist()
        assert names == ["2_8_BacLieuGiaRai/manifest.csv"]


class TestStopHistoryEndpoint:
    """The stored phase log, as the dashboard panel reads it."""

    def test_history_reads_oldest_first(self, client, db, plan):
        stop_id = plan["stop_ids"][0]
        client.post("/api/execution/advance", json={"stop_id": stop_id})
        _give_proof(db, stop_id)
        client.post("/api/execution/advance", json={"stop_id": stop_id})
        client.post("/api/execution/revert", json={"stop_id": stop_id})

        events = client.get(f"/api/stops/{stop_id}/history").get_json()

        assert [(e["from_status"], e["to_status"], e["action"]) for e in events] == [
            ("planned", "arrived", "advance"),
            ("arrived", "completed", "advance"),
            ("completed", "arrived", "revert"),
        ]

    def test_a_cancel_reason_survives_into_the_log(self, client, db, plan):
        """The reason is cleared off the execution row by a revert, so the
        log is the only place it continues to exist."""
        stop_id = plan["stop_ids"][0]
        client.post(f"/api/stops/{stop_id}/cancel", json={"reason": "customer closed"})
        client.post("/api/execution/revert", json={"stop_id": stop_id})

        events = client.get(f"/api/stops/{stop_id}/history").get_json()

        assert execution_service.get_stop_execution(db, stop_id)["cancel_reason"] == ""
        assert events[0]["reason"] == "customer closed"

    def test_an_untouched_stop_has_an_empty_log(self, client, plan):
        assert client.get(f"/api/stops/{plan['stop_ids'][0]}/history").get_json() == []

    def test_a_missing_stop_returns_an_empty_log_not_a_500(self, client):
        r = client.get("/api/stops/99999/history")
        assert r.status_code == 200 and r.get_json() == []


class TestReorderValidation:
    """C-06b: any list was accepted and applied stop-by-stop."""

    def test_full_reorder_succeeds(self, client, db, plan):
        a, b, c = plan["stop_ids"]
        r = client.post("/api/stops/reorder",
                             json={"assignment_id": plan["assignment_id"], "stop_ids": [c, a, b]})
        assert r.status_code == 200
        assert [s["id"] for s in plan_service.list_stops(db, plan["assignment_id"])] == [c, a, b]

    def test_partial_list_is_rejected(self, client, db, plan):
        a, b, _ = plan["stop_ids"]
        r = client.post("/api/stops/reorder",
                             json={"assignment_id": plan["assignment_id"], "stop_ids": [b, a]})
        assert r.status_code == 400
        assert "missing" in r.get_json()["error"]

        seqs = [s["execution_sequence"] for s in plan_service.list_stops(db, plan["assignment_id"])]
        assert len(seqs) == len(set(seqs)), f"duplicate execution_sequence: {seqs}"

    def test_foreign_stop_ids_are_rejected(self, client, db, plan):
        other = plan_service.create_assignment(db, plan["plan_id"], 1, sequence=9)
        foreign = plan_service.create_stop(db, other, 1, station_code="X", lat=10.8, lng=106.6)
        r = client.post("/api/stops/reorder",
                             json={"assignment_id": plan["assignment_id"], "stop_ids": [foreign]})
        assert r.status_code == 400
        assert "not in this assignment" in r.get_json()["error"]


# ===========================================================================
# Excel import (audit C-05, L-03, L-06)
# ===========================================================================

class TestImportRoute:
    def _rows(self, *plates):
        return [
            {"vehicle": p, "sequence": i + 1, "station_code": f"S{i+1}",
             "station_name": f"Stop {i+1}", "lat": 10.8, "lng": 106.6}
            for i, p in enumerate(plates)
        ]

    def _vehicle_count(self, db):
        conn = sqlite3.connect(db)
        try:
            return conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
        finally:
            conn.close()

    def test_plate_variants_collapse_to_one_assignment(self, client, db):
        """C-05 + L-03."""
        before = self._vehicle_count(db)
        plan_id = plan_service.create_plan(db, "Import", "2026-07-31")

        r = client.post("/api/plans/import/save", json={
            "plan_id": plan_id,
            "rows": self._rows("50E-18463", "50E18463", "50E 18463", "18463"),
        })

        assert r.status_code == 201
        assert r.get_json()["assignments_created"] == 1
        assert self._vehicle_count(db) == before, "import created duplicate vehicles"

    def test_unknown_vehicle_is_rejected_and_writes_nothing(self, client, db):
        before = self._vehicle_count(db)
        plan_id = plan_service.create_plan(db, "Import", "2026-07-31")

        r = client.post("/api/plans/import/save",
                             json={"plan_id": plan_id, "rows": self._rows("99Z-00000")})

        assert r.status_code == 409
        assert r.get_json()["unknown_vehicles"] == ["99Z-00000"]
        assert self._vehicle_count(db) == before
        assert plan_service.get_plan(db, plan_id)["status"] == "draft"

    def test_no_flag_can_make_the_import_create_a_vehicle(self, client, db):
        before = self._vehicle_count(db)
        plan_id = plan_service.create_plan(db, "Import", "2026-07-31")
        r = client.post("/api/plans/import/save", json={
            "plan_id": plan_id,
            "rows": self._rows("99Z-00000"),
            "create_missing_vehicles": True,   # inert
        })
        assert r.status_code == 409
        assert self._vehicle_count(db) == before

    def test_plan_is_confirmed_once_on_success(self, client, db):
        """L-06: the status UPDATE sat inside the per-vehicle loop."""
        plan_id = plan_service.create_plan(db, "Import", "2026-07-31")
        r = client.post("/api/plans/import/save",
                             json={"plan_id": plan_id, "rows": self._rows("50E-18463")})
        assert r.get_json()["plan_confirmed"] is True
        assert plan_service.get_plan(db, plan_id)["status"] == "confirmed"

    def test_import_requires_plan_id_and_rows(self, client):
        assert client.post("/api/plans/import/save", json={}).status_code == 400


# ===========================================================================
# Image upload (audit S-04, S-05, C-08)
# ===========================================================================

def _upload(client, stop_id, filename, content=b"binary-image-data", category="delivery"):
    return client.post(
        f"/api/stops/{stop_id}/images",
        data={"file": (io.BytesIO(content), filename), "category": category},
        content_type="multipart/form-data",
    )


class TestImageUpload:
    @pytest.mark.parametrize("filename", ["photo.jpg", "photo.JPG", "photo.png", "photo.webp"])
    def test_image_types_are_accepted(self, client, plan, filename):
        assert _upload(client, plan["stop_ids"][0], filename).status_code == 201

    @pytest.mark.parametrize("filename", [
        "payload.html", "payload.svg", "shell.php", "notes.txt", "noext",
    ])
    def test_dangerous_types_are_rejected(self, client, plan, filename):
        """S-05: send_file infers Content-Type from the extension, so an
        uploaded .html was served as text/html from the app's own origin."""
        resp = _upload(client, plan["stop_ids"][0], filename)
        assert resp.status_code == 400
        assert "Unsupported file type" in resp.get_json()["error"]

    def test_oversized_upload_is_rejected(self, client, plan):
        big = b"x" * (11 * 1024 * 1024)
        resp = _upload(client, plan["stop_ids"][0], "huge.jpg", content=big)
        assert resp.status_code == 400
        assert "limit" in resp.get_json()["error"]

    def test_empty_upload_is_rejected(self, client, plan):
        assert _upload(client, plan["stop_ids"][0], "empty.jpg", content=b"").status_code == 400

    def test_traversal_in_category_cannot_escape(self, client, plan):
        """S-04: category and station_code were interpolated into the upload
        path, so `../../../static/js` wrote into served static files."""
        from services.delivery import image_service

        resp = _upload(client, plan["stop_ids"][0], "ok.jpg",
                       category="../../../static/js")
        assert resp.status_code == 201

        img = image_service.get_image(client.application.config["DB_PATH"],
                                      resp.get_json()["id"])
        full = (image_service.DATA_ROOT / img["relative_path"]).resolve()
        assert full.is_relative_to(image_service.UPLOAD_ROOT.resolve())
        full.unlink(missing_ok=True)

    def test_two_uploads_in_the_same_second_both_survive(self, client, plan):
        """C-08: filenames were `{unix_seconds}{ext}`, so the second photo
        silently overwrote the first and both rows pointed at one file."""
        from services.delivery import image_service

        stop_id = plan["stop_ids"][0]
        first = _upload(client, stop_id, "a.jpg", content=b"first")
        second = _upload(client, stop_id, "b.jpg", content=b"second")
        assert first.status_code == second.status_code == 201

        db_path = client.application.config["DB_PATH"]
        images = image_service.list_images(db_path, stop_id)
        paths = {i["relative_path"] for i in images}
        assert len(paths) == 2, "one upload overwrote the other"

        for i in images:
            (image_service.DATA_ROOT / i["relative_path"]).unlink(missing_ok=True)

    def test_upload_to_a_missing_stop_404s(self, client, db):
        assert _upload(client, 999999, "x.jpg").status_code == 404

    def test_upload_requires_a_file(self, client, plan):
        resp = client.post(f"/api/stops/{plan['stop_ids'][0]}/images",
                                data={}, content_type="multipart/form-data")
        assert resp.status_code == 400


class TestImageServing:
    def test_uploaded_image_can_be_fetched_back(self, client, plan):
        from services.delivery import image_service

        resp = _upload(client, plan["stop_ids"][0], "p.jpg", content=b"the-bytes")
        image_id = resp.get_json()["id"]

        served = client.get(f"/api/images/{image_id}/file")
        assert served.status_code == 200
        assert served.data == b"the-bytes"

        img = image_service.get_image(client.application.config["DB_PATH"], image_id)
        (image_service.DATA_ROOT / img["relative_path"]).unlink(missing_ok=True)

    def test_missing_image_404s(self, client):
        assert client.get("/api/images/999999/file").status_code == 404


# ===========================================================================
# CRUD + validation surface
# ===========================================================================

class TestPlanCrud:
    def test_create_requires_name_and_date(self, client):
        assert client.post("/api/plans", json={"plan_date": "2026-07-31"}).status_code == 400
        assert client.post("/api/plans", json={"plan_name": "x"}).status_code == 400

    def test_create_then_fetch(self, client, db):
        plan_id = client.post(
            "/api/plans", json={"plan_name": "P", "plan_date": "2026-07-31"}
        ).get_json()["id"]
        assert client.get(f"/api/plans/{plan_id}").get_json()["plan_name"] == "P"

    def test_missing_plan_404s(self, client):
        assert client.get("/api/plans/999999").status_code == 404

    def test_delete_cascades_to_stops(self, client, db, plan):
        assert client.delete(f"/api/plans/{plan['plan_id']}").status_code == 200
        assert plan_service.list_stops(db, plan["assignment_id"]) == []

    def test_batch_delete_requires_ids(self, client):
        assert client.post("/api/plans/batch-delete", json={"plan_ids": []}).status_code == 400


class TestStopCrud:
    def test_list_requires_assignment_id(self, client):
        assert client.get("/api/stops").status_code == 400

    def test_get_stop_includes_images(self, client, plan):
        body = client.get(f"/api/stops/{plan['stop_ids'][0]}").get_json()
        assert body["images"] == []

    def test_missing_stop_404s(self, client):
        assert client.get("/api/stops/999999").status_code == 404

    def test_create_requires_assignment_id(self, client):
        assert client.post("/api/stops", json={"station_name": "x"}).status_code == 400

    def test_insert_temp_stop_reopens_a_completed_plan(self, client, db, plan):
        for stop_id in plan["stop_ids"]:
            client.post(f"/api/stops/{stop_id}/skip", json={"reason": "x"})
        assert plan_service.get_plan(db, plan["plan_id"])["status"] == "completed"

        r = client.post("/api/stops/insert", json={
            "assignment_id": plan["assignment_id"], "after_sequence": 1,
            "station_name": "Urgent", "lat": 10.9, "lng": 106.7,
        })
        assert r.status_code == 201
        assert plan_service.get_plan(db, plan["plan_id"])["status"] == "executing"
