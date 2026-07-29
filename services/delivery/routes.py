import os
import json
import logging
from flask import Blueprint, jsonify, request, send_file, current_app
from datetime import datetime
from pathlib import Path

from . import plan_service
from . import execution_service
from . import eta_service
from . import image_service
from . import tracking_service

logger = logging.getLogger(__name__)

bp = Blueprint("delivery", __name__, url_prefix="/api")


def _db():
    return current_app.config.get("DB_PATH", current_app.root_path + "/routing_system.db")


def _ors_config():
    return (
        os.getenv("ORS_API_KEY", ""),
        os.getenv("ORS_BASE_URL", ""),
    )


def _ttas_vehicles():
    try:
        from app import fetch_vehicle_data
        raw, source, err = fetch_vehicle_data()
        return [tracking_service.normalize_gps_position(v) for v in raw], source, err
    except Exception as e:
        return [], "error", str(e)


# ===========================
# Drivers
# ===========================
@bp.route("/drivers", methods=["GET"])
def list_drivers():
    return jsonify(plan_service.list_drivers(_db()))


@bp.route("/drivers", methods=["POST"])
def create_driver():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Driver name is required"}), 400
    driver_id = plan_service.create_driver(_db(), name, data.get("phone", ""), data.get("license_number", ""))
    return jsonify({"id": driver_id}), 201


# ===========================
# Plans
# ===========================
@bp.route("/plans", methods=["GET"])
def list_plans():
    status = request.args.get("status")
    return jsonify(plan_service.list_plans(_db(), status))


@bp.route("/plans", methods=["POST"])
def create_plan():
    data = request.get_json(force=True)
    name = (data.get("plan_name") or "").strip()
    plan_date = (data.get("plan_date") or "").strip()
    if not name:
        return jsonify({"error": "plan_name is required"}), 400
    if not plan_date:
        return jsonify({"error": "plan_date is required"}), 400
    plan_id = plan_service.create_plan(_db(), name, plan_date, data.get("description", ""), data.get("created_by", ""))
    return jsonify({"id": plan_id}), 201


@bp.route("/plans/<int:plan_id>", methods=["GET"])
def get_plan(plan_id):
    plan = plan_service.get_plan(_db(), plan_id)
    if not plan:
        return jsonify({"error": "Plan not found"}), 404
    return jsonify(plan)


@bp.route("/plans/<int:plan_id>", methods=["PUT"])
def update_plan(plan_id):
    data = request.get_json(force=True)
    ok = plan_service.update_plan(_db(), plan_id, **data)
    if not ok:
        return jsonify({"error": "Plan not found or no changes"}), 404
    return jsonify({"ok": True})


@bp.route("/plans/<int:plan_id>", methods=["DELETE"])
def delete_plan(plan_id):
    ok = plan_service.delete_plan(_db(), plan_id)
    if not ok:
        return jsonify({"error": "Plan not found"}), 404
    return jsonify({"ok": True})


@bp.route("/plans/<int:plan_id>/confirm", methods=["POST"])
def confirm_plan(plan_id):
    ok = plan_service.update_plan(_db(), plan_id, status="confirmed")
    if not ok:
        return jsonify({"error": "Plan not found"}), 404
    return jsonify({"ok": True})


# ===========================
# Excel Import Pipeline
# ===========================
@bp.route("/plans/import/parse", methods=["POST"])
def import_parse():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["file"]
    tmp_path = Path(current_app.root_path) / "_import_temp.xlsx"
    file.save(str(tmp_path))
    try:
        rows = plan_service.parse_excel_rows(str(tmp_path))
        preview = plan_service.preview_import(rows)
        return jsonify(preview)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


@bp.route("/plans/import/save", methods=["POST"])
def import_save():
    data = request.get_json(force=True)
    plan_id = data.get("plan_id")
    rows = data.get("rows")
    if not plan_id or not rows:
        return jsonify({"error": "plan_id and rows are required"}), 400
    try:
        plan_service.confirm_import(_db(), plan_id, rows)
        return jsonify({"ok": True}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ===========================
# Vehicle Assignments
# ===========================
@bp.route("/assignments", methods=["GET"])
def list_assignments():
    plan_id = request.args.get("plan_id", type=int)
    return jsonify(plan_service.list_assignments(_db(), plan_id))


@bp.route("/assignments", methods=["POST"])
def create_assignment():
    data = request.get_json(force=True)
    plan_id = data.get("plan_id")
    vehicle_id = data.get("vehicle_id")
    if not plan_id or not vehicle_id:
        return jsonify({"error": "plan_id and vehicle_id are required"}), 400
    assignment_id = plan_service.create_assignment(
        _db(), plan_id, vehicle_id,
        driver_id=data.get("driver_id"),
        sequence=data.get("sequence", 0),
        notes=data.get("notes", ""),
    )
    return jsonify({"id": assignment_id}), 201


@bp.route("/assignments/<int:assignment_id>", methods=["GET"])
def get_assignment(assignment_id):
    a = plan_service.get_assignment(_db(), assignment_id)
    if not a:
        return jsonify({"error": "Assignment not found"}), 404
    return jsonify(a)


@bp.route("/assignments/<int:assignment_id>", methods=["PUT"])
def update_assignment(assignment_id):
    data = request.get_json(force=True)
    ok = plan_service.update_assignment(_db(), assignment_id, **data)
    if not ok:
        return jsonify({"error": "Assignment not found or no changes"}), 404
    return jsonify({"ok": True})


@bp.route("/assignments/<int:assignment_id>", methods=["DELETE"])
def delete_assignment(assignment_id):
    ok = plan_service.delete_assignment(_db(), assignment_id)
    if not ok:
        return jsonify({"error": "Assignment not found"}), 404
    return jsonify({"ok": True})


# ===========================
# Stops
# ===========================
@bp.route("/stops", methods=["GET"])
def list_stops():
    assignment_id = request.args.get("assignment_id", type=int)
    if not assignment_id:
        return jsonify({"error": "assignment_id is required"}), 400
    return jsonify(plan_service.list_stops(_db(), assignment_id))


@bp.route("/stops", methods=["POST"])
def create_stop():
    data = request.get_json(force=True)
    assignment_id = data.get("vehicle_assignment_id") or data.get("assignment_id")
    if not assignment_id:
        return jsonify({"error": "assignment_id is required"}), 400
    stop_id = plan_service.create_stop(
        _db(), assignment_id,
        data.get("planned_sequence", 0),
        station_code=data.get("station_code", ""),
        station_name=data.get("station_name", ""),
        address=data.get("address", ""),
        lat=data.get("lat"),
        lng=data.get("lng"),
        manager_name=data.get("manager_name", ""),
        manager_phone=data.get("manager_phone", ""),
        product_description=data.get("product_description", ""),
        note=data.get("note", ""),
    )
    return jsonify({"id": stop_id}), 201


@bp.route("/stops/<int:stop_id>", methods=["GET"])
def get_stop(stop_id):
    stop = plan_service.get_stop(_db(), stop_id)
    if not stop:
        return jsonify({"error": "Stop not found"}), 404
    images = image_service.list_images(_db(), stop_id)
    stop["images"] = images
    return jsonify(stop)


@bp.route("/stops/<int:stop_id>", methods=["PUT"])
def update_stop(stop_id):
    data = request.get_json(force=True)
    ok = plan_service.update_stop(_db(), stop_id, **data)
    if not ok:
        return jsonify({"error": "Stop not found or no changes"}), 404
    return jsonify({"ok": True})


@bp.route("/stops/<int:stop_id>", methods=["DELETE"])
def delete_stop(stop_id):
    ok = plan_service.delete_stop(_db(), stop_id)
    if not ok:
        return jsonify({"error": "Stop not found"}), 404
    return jsonify({"ok": True})


@bp.route("/stops/<int:stop_id>/skip", methods=["POST"])
def skip_stop(stop_id):
    data = request.get_json(force=True) or {}
    ok = execution_service.skip_stop(_db(), stop_id, data.get("reason", ""))
    if not ok:
        return jsonify({"error": "Stop not found"}), 404
    return jsonify({"ok": True})


@bp.route("/stops/<int:stop_id>/cancel", methods=["POST"])
def cancel_stop(stop_id):
    data = request.get_json(force=True) or {}
    ok = execution_service.cancel_stop(_db(), stop_id, data.get("reason", ""))
    if not ok:
        return jsonify({"error": "Stop not found"}), 404
    return jsonify({"ok": True})


@bp.route("/stops/reorder", methods=["POST"])
def reorder_stops():
    data = request.get_json(force=True)
    assignment_id = data.get("assignment_id")
    stop_ids = data.get("stop_ids")
    if not assignment_id or not stop_ids:
        return jsonify({"error": "assignment_id and stop_ids are required"}), 400
    ok = execution_service.reorder_stops(_db(), assignment_id, stop_ids)
    if not ok:
        return jsonify({"error": "Reorder failed"}), 400
    return jsonify({"ok": True})


@bp.route("/stops/insert", methods=["POST"])
def insert_temp_stop():
    data = request.get_json(force=True)
    assignment_id = data.get("assignment_id")
    after_seq = data.get("after_sequence", 0)
    if not assignment_id:
        return jsonify({"error": "assignment_id is required"}), 400
    stop_id = execution_service.insert_temp_stop(
        _db(), assignment_id, after_seq,
        station_code=data.get("station_code", ""),
        station_name=data.get("station_name", ""),
        address=data.get("address", ""),
        lat=data.get("lat"),
        lng=data.get("lng"),
        manager_name=data.get("manager_name", ""),
        manager_phone=data.get("manager_phone", ""),
        product_description=data.get("product_description", ""),
        note=data.get("note", ""),
    )
    return jsonify({"id": stop_id}), 201


# ===========================
# Execution
# ===========================
@bp.route("/execution/current", methods=["GET"])
def get_current_stop():
    assignment_id = request.args.get("assignment_id", type=int)
    if not assignment_id:
        return jsonify({"error": "assignment_id is required"}), 400
    stop = execution_service.get_current_stop(_db(), assignment_id)
    if not stop:
        return jsonify({"message": "No active stop", "stop": None})
    return jsonify(stop)


@bp.route("/execution/advance", methods=["POST"])
def advance_stop():
    data = request.get_json(force=True)
    stop_id = data.get("stop_id")
    if not stop_id:
        return jsonify({"error": "stop_id is required"}), 400
    ok, msg = execution_service.advance_stop(_db(), stop_id)
    if not ok:
        return jsonify({"error": msg}), 400
    return jsonify({"ok": True, "status": msg})


@bp.route("/execution/dashboard", methods=["GET"])
def get_dashboard():
    data = execution_service.get_dashboard_data(_db())
    vehicles, source, err = _ttas_vehicles()
    vehicle_map = {}
    for v in vehicles:
        plate = (v.get("device_name") or "").strip().lower()
        if plate:
            vehicle_map[plate] = v

    for entry in data:
        plate = (entry.get("plate_number") or "").strip().lower()
        if plate in vehicle_map:
            entry["gps"] = vehicle_map[plate]

    return jsonify({
        "assignments": data,
        "gps_source": source,
        "gps_error": err,
    })


@bp.route("/execution/progress", methods=["GET"])
def get_progress():
    assignment_id = request.args.get("assignment_id", type=int)
    if not assignment_id:
        return jsonify({"error": "assignment_id is required"}), 400
    return jsonify(execution_service.get_assignment_progress(_db(), assignment_id))


# ===========================
# ETA
# ===========================
@bp.route("/eta", methods=["GET"])
def get_eta():
    assignment_id = request.args.get("assignment_id", type=int)
    if not assignment_id:
        return jsonify({"error": "assignment_id is required"}), 400

    stops = plan_service.list_stops(_db(), assignment_id)
    remaining = [s for s in stops if s.get("execution_status") in ("planned", "enroute")]

    vehicles, _, _ = _ttas_vehicles()
    assignment = plan_service.get_assignment(_db(), assignment_id)
    plate = (assignment.get("plate_number") or "").strip().lower() if assignment else ""

    current_gps = None
    for v in vehicles:
        if (v.get("device_name") or "").strip().lower() == plate:
            current_gps = tracking_service.normalize_gps_position(v)
            break

    if not current_gps:
        return jsonify({"error": "Vehicle GPS not available", "etas": []})

    ors_key, ors_base = _ors_config()
    etas = eta_service.calculate_etas_for_stops(
        ors_key, ors_base,
        current_gps["lat"], current_gps["lng"],
        remaining,
    )
    return jsonify({"etas": etas, "gps": current_gps})


# ===========================
# Images per Stop
# ===========================
@bp.route("/stops/<int:stop_id>/images", methods=["GET"])
def list_stop_images(stop_id):
    return jsonify(image_service.list_images(_db(), stop_id))


@bp.route("/stops/<int:stop_id>/images", methods=["POST"])
def upload_stop_image(stop_id):
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["file"]
    category = request.form.get("category", "extra")
    gps_lat = request.form.get("gps_lat", type=float)
    gps_lng = request.form.get("gps_lng", type=float)
    captured_at = request.form.get("captured_at")
    uploaded_by = request.form.get("uploaded_by", "")

    img_id = image_service.upload_image(
        _db(), stop_id, file, category=category,
        gps_lat=gps_lat, gps_lng=gps_lng,
        captured_at=captured_at, uploaded_by=uploaded_by,
    )
    if not img_id:
        return jsonify({"error": "Stop not found"}), 404
    return jsonify({"id": img_id}), 201


# ===========================
# Images (generic)
# ===========================
@bp.route("/images/<int:image_id>/file", methods=["GET"])
def serve_image(image_id):
    img = image_service.get_image(_db(), image_id)
    if not img:
        return jsonify({"error": "Image not found"}), 404
    full_path = image_service.BASE_DIR / img["relative_path"]
    if not full_path.exists():
        return jsonify({"error": "File not found on disk"}), 404
    return send_file(str(full_path))


@bp.route("/images/<int:image_id>", methods=["DELETE"])
def delete_image(image_id):
    ok = image_service.delete_image(_db(), image_id)
    if not ok:
        return jsonify({"error": "Image not found"}), 404
    return jsonify({"ok": True})
