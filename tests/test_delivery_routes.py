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
from services.delivery import plan_service, execution_service  # noqa: E402
from services.delivery.database import init_delivery_tables    # noqa: E402

# A raw TTAS DevList item. Note the plate has no hyphen while the fleet
# stores "50E-18463" — the mismatch that produced audit C-03.
TTAS_PAYLOAD = [{
    "biensoxe": "50E18463",
    "latitude": "10.8500",
    "longitude": "106.6500",
    "speed": "Chạy 42km/h",
    "ad3": "Nổ",
    "trktime": "2026-07-31 09:00:00",
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
    monkeypatch.setattr(image_service, "BASE_DIR", tmp_path)
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
    """A confirmed plan with one assignment and three stops."""
    plan_id = plan_service.create_plan(db, "Route Plan", "2026-07-31")
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


# ===========================================================================
# GPS pipeline (audit C-01, C-02, C-03)
# ===========================================================================

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
        assert gps["last_update"] == "2026-07-31 09:00:00"  # from "trktime"
        assert gps["driver_name"] == "Driver A"   # from "driver"

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
        full = (image_service.BASE_DIR / img["relative_path"]).resolve()
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
            (image_service.BASE_DIR / i["relative_path"]).unlink(missing_ok=True)

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
        (image_service.BASE_DIR / img["relative_path"]).unlink(missing_ok=True)

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
