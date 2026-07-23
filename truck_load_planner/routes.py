"""
Flask Blueprint for Truck Load Planner API endpoints.
All routes are prefixed with /api/tlp.
"""

import json
import sqlite3
import time
import uuid
import datetime
from flask import Blueprint, jsonify, request

tlp_bp = Blueprint("tlp", __name__, url_prefix="/api/tlp")

DB_PATH = None



def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row):
    if row is None:
        return None
    return dict(row)


# ─── Container Config CRUD ─────────────────────────────────────

@tlp_bp.route("/container-configs", methods=["GET"])
def list_container_configs():
    conn = _get_db()
    rows = conn.execute("SELECT * FROM container_configs ORDER BY name").fetchall()
    result = []
    for r in rows:
        cc = _row_to_dict(r)
        feats = conn.execute(
            "SELECT * FROM container_features WHERE container_config_id = ? ORDER BY feature_type",
            (r["id"],)
        ).fetchall()
        cc["features"] = [f["feature_type"] for f in feats]
        result.append(cc)
    conn.close()
    return jsonify(result)


@tlp_bp.route("/container-configs", methods=["POST"])
def create_container_config():
    data = request.json or {}
    required = ["cargo_length_mm", "cargo_width_mm", "cargo_height_mm"]
    for f in required:
        if f not in data:
            return jsonify({"error": f"Missing required field: {f}"}), 400
    conn = _get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO container_configs (name, cargo_length_mm, cargo_width_mm, cargo_height_mm, payload_kg)
        VALUES (?, ?, ?, ?, ?)
    """, (
        data.get("name", ""),
        data["cargo_length_mm"], data["cargo_width_mm"], data["cargo_height_mm"],
        data.get("payload_kg", 0),
    ))
    cc_id = c.lastrowid
    for feat in data.get("features", []):
        geo = feat.get("geometry", {})
        c.execute("""
            INSERT INTO container_features (container_config_id, feature_type, label, geometry_json)
            VALUES (?, ?, ?, ?)
        """, (cc_id, feat["feature_type"], feat.get("label", ""), json.dumps(geo)))
    conn.commit()
    row = conn.execute("SELECT * FROM container_configs WHERE id = ?", (cc_id,)).fetchone()
    conn.close()
    return jsonify(_row_to_dict(row)), 201


@tlp_bp.route("/container-configs/<int:cc_id>", methods=["GET"])
def get_container_config(cc_id):
    conn = _get_db()
    row = conn.execute("SELECT * FROM container_configs WHERE id = ?", (cc_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Container config not found"}), 404
    cc = _row_to_dict(row)
    feats = conn.execute(
        "SELECT * FROM container_features WHERE container_config_id = ? ORDER BY id",
        (cc_id,)
    ).fetchall()
    cc["features"] = [_row_to_dict(f) for f in feats]
    conn.close()
    return jsonify(cc)


@tlp_bp.route("/container-configs/<int:cc_id>", methods=["PUT"])
def update_container_config(cc_id):
    data = request.json or {}
    conn = _get_db()
    existing = conn.execute("SELECT * FROM container_configs WHERE id = ?", (cc_id,)).fetchone()
    if not existing:
        conn.close()
        return jsonify({"error": "Container config not found"}), 404
    conn.execute("""
        UPDATE container_configs SET name=?, cargo_length_mm=?, cargo_width_mm=?,
          cargo_height_mm=?, payload_kg=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (
        data.get("name", existing["name"]),
        data.get("cargo_length_mm", existing["cargo_length_mm"]),
        data.get("cargo_width_mm", existing["cargo_width_mm"]),
        data.get("cargo_height_mm", existing["cargo_height_mm"]),
        data.get("payload_kg", existing["payload_kg"]),
        cc_id,
    ))
    if "features" in data:
        conn.execute("DELETE FROM container_features WHERE container_config_id = ?", (cc_id,))
        for feat in data["features"]:
            geo = feat.get("geometry", {})
            conn.execute("""
                INSERT INTO container_features (container_config_id, feature_type, label, geometry_json)
                VALUES (?, ?, ?, ?)
            """, (cc_id, feat["feature_type"], feat.get("label", ""), json.dumps(geo)))
    conn.commit()
    row = conn.execute("SELECT * FROM container_configs WHERE id = ?", (cc_id,)).fetchone()
    conn.close()
    return jsonify(_row_to_dict(row))


@tlp_bp.route("/container-configs/<int:cc_id>", methods=["DELETE"])
def delete_container_config(cc_id):
    conn = _get_db()
    c = conn.cursor()
    c.execute("DELETE FROM container_features WHERE container_config_id = ?", (cc_id,))
    c.execute("DELETE FROM container_configs WHERE id = ?", (cc_id,))
    conn.commit()
    conn.close()
    if c.rowcount == 0:
        return jsonify({"error": "Container config not found"}), 404
    return jsonify({"success": True})


# ─── Container Features (standalone CRUD) ──────────────────────

@tlp_bp.route("/container-configs/<int:cc_id>/features", methods=["POST"])
def add_feature(cc_id):
    data = request.json or {}
    if not data.get("feature_type"):
        return jsonify({"error": "feature_type is required"}), 400
    conn = _get_db()
    c = conn.cursor()
    geo = data.get("geometry", {})
    c.execute("""
        INSERT INTO container_features (container_config_id, feature_type, label, geometry_json)
        VALUES (?, ?, ?, ?)
    """, (cc_id, data["feature_type"], data.get("label", ""), json.dumps(geo)))
    conn.commit()
    fid = c.lastrowid
    row = conn.execute("SELECT * FROM container_features WHERE id = ?", (fid,)).fetchone()
    conn.close()
    return jsonify(_row_to_dict(row)), 201


@tlp_bp.route("/container-features/<int:feat_id>", methods=["PUT"])
def update_feature(feat_id):
    data = request.json or {}
    conn = _get_db()
    existing = conn.execute("SELECT * FROM container_features WHERE id = ?", (feat_id,)).fetchone()
    if not existing:
        conn.close()
        return jsonify({"error": "Feature not found"}), 404
    geo = data.get("geometry", {})
    if not isinstance(geo, str):
        geo = json.dumps(geo)
    conn.execute("""
        UPDATE container_features SET feature_type=?, label=?, geometry_json=?
        WHERE id=?
    """, (
        data.get("feature_type", existing["feature_type"]),
        data.get("label", existing["label"]),
        geo,
        feat_id,
    ))
    conn.commit()
    row = conn.execute("SELECT * FROM container_features WHERE id = ?", (feat_id,)).fetchone()
    conn.close()
    return jsonify(_row_to_dict(row))


@tlp_bp.route("/container-features/<int:feat_id>", methods=["DELETE"])
def delete_feature(feat_id):
    conn = _get_db()
    c = conn.cursor()
    c.execute("DELETE FROM container_features WHERE id = ?", (feat_id,))
    conn.commit()
    conn.close()
    if c.rowcount == 0:
        return jsonify({"error": "Feature not found"}), 404
    return jsonify({"success": True})


# ─── Package CRUD ──────────────────────────────────────────────

@tlp_bp.route("/packages", methods=["GET"])
def list_packages():
    conn = _get_db()
    rows = conn.execute("SELECT * FROM tlp_packages ORDER BY weight_kg DESC, (length * width * height) DESC").fetchall()
    conn.close()
    return jsonify([_row_to_dict(r) for r in rows])


@tlp_bp.route("/packages", methods=["POST"])
def create_package():
    data = request.json or {}
    required = ["name", "length", "width", "height", "weight_kg"]
    for f in required:
        if f not in data:
            return jsonify({"error": f"Missing required field: {f}"}), 400
    conn = _get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO tlp_packages (name, length, width, height, weight_kg,
          allow_stacking, allow_rotation, fragile, color, default_qty,
          max_top_weight_kg, max_stack_layers)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["name"], data["length"], data["width"], data["height"],
        data["weight_kg"],
        1 if data.get("allow_stacking") else 0,
        1 if data.get("allow_rotation") else 0,
        1 if data.get("fragile") else 0,
        data.get("color", "#3b82f6"),
        data.get("default_qty", 1),
        data.get("max_top_weight_kg", 0.0),
        data.get("max_stack_layers", 0),
    ))
    conn.commit()
    pkg_id = c.lastrowid
    row = conn.execute("SELECT * FROM tlp_packages WHERE id = ?", (pkg_id,)).fetchone()
    conn.close()
    return jsonify(_row_to_dict(row)), 201


@tlp_bp.route("/packages/<int:pkg_id>", methods=["PUT"])
def update_package(pkg_id):
    data = request.json or {}
    conn = _get_db()
    existing = conn.execute("SELECT * FROM tlp_packages WHERE id = ?", (pkg_id,)).fetchone()
    if not existing:
        conn.close()
        return jsonify({"error": "Package not found"}), 404
    conn.execute("""
        UPDATE tlp_packages SET name=?, length=?, width=?, height=?,
          weight_kg=?, allow_stacking=?, allow_rotation=?, fragile=?,
          color=?, default_qty=?, max_top_weight_kg=?, max_stack_layers=?,
          updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (
        data.get("name", existing["name"]),
        data.get("length", existing["length"]),
        data.get("width", existing["width"]),
        data.get("height", existing["height"]),
        data.get("weight_kg", existing["weight_kg"]),
        1 if data.get("allow_stacking", existing["allow_stacking"]) else 0,
        1 if data.get("allow_rotation", existing["allow_rotation"]) else 0,
        1 if data.get("fragile", existing["fragile"]) else 0,
        data.get("color", existing["color"]),
        data.get("default_qty", existing["default_qty"] if "default_qty" in existing.keys() else 1),
        data.get("max_top_weight_kg", existing.get("max_top_weight_kg", 0.0)),
        data.get("max_stack_layers", existing.get("max_stack_layers", 0)),
        pkg_id,
    ))
    conn.commit()
    row = conn.execute("SELECT * FROM tlp_packages WHERE id = ?", (pkg_id,)).fetchone()
    conn.close()
    return jsonify(_row_to_dict(row))


@tlp_bp.route("/packages/<int:pkg_id>", methods=["DELETE"])
def delete_package(pkg_id):
    conn = _get_db()
    c = conn.cursor()
    c.execute("DELETE FROM tlp_packages WHERE id = ?", (pkg_id,))
    conn.commit()
    conn.close()
    if c.rowcount == 0:
        return jsonify({"error": "Package not found"}), 404
    return jsonify({"success": True})


@tlp_bp.route("/packages/clear", methods=["DELETE"])
def clear_all_packages():
    conn = _get_db()
    c = conn.cursor()
    c.execute("DELETE FROM tlp_placements WHERE package_id IN (SELECT id FROM tlp_packages)")
    c.execute("DELETE FROM tlp_shipment_items WHERE package_id IN (SELECT id FROM tlp_packages)")
    c.execute("DELETE FROM tlp_packages")
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ─── Shipment CRUD ─────────────────────────────────────────────

@tlp_bp.route("/shipments", methods=["GET"])
def list_shipments():
    conn = _get_db()
    rows = conn.execute("SELECT * FROM tlp_shipments ORDER BY created_at DESC").fetchall()
    result = []
    for r in rows:
        s = _row_to_dict(r)
        items = conn.execute(
            "SELECT si.*, p.name AS package_name, p.length, p.width, p.height, p.weight_kg, p.color "
            "FROM tlp_shipment_items si "
            "LEFT JOIN tlp_packages p ON p.id = si.package_id "
            "WHERE si.shipment_id = ?", (r["id"],)
        ).fetchall()
        s["items"] = [_row_to_dict(i) for i in items]
        result.append(s)
    conn.close()
    return jsonify(result)


@tlp_bp.route("/shipments", methods=["POST"])
def create_shipment():
    data = request.json or {}
    if not data.get("customer_name"):
        return jsonify({"error": "customer_name is required"}), 400
    conn = _get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO tlp_shipments (customer_name, reference_number, notes)
        VALUES (?, ?, ?)
    """, (data["customer_name"], data.get("reference_number", ""),
          data.get("notes", "")))
    shipment_id = c.lastrowid
    for item in data.get("items", []):
        c.execute("""
            INSERT INTO tlp_shipment_items (shipment_id, package_id, quantity, notes)
            VALUES (?, ?, ?, ?)
        """, (shipment_id, item["package_id"], item.get("quantity", 1),
              item.get("notes", "")))
    conn.commit()
    row = conn.execute("SELECT * FROM tlp_shipments WHERE id = ?", (shipment_id,)).fetchone()
    conn.close()
    return jsonify(_row_to_dict(row)), 201


@tlp_bp.route("/shipments/<int:shipment_id>", methods=["GET"])
def get_shipment(shipment_id):
    conn = _get_db()
    row = conn.execute("SELECT * FROM tlp_shipments WHERE id = ?", (shipment_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Shipment not found"}), 404
    s = _row_to_dict(row)
    items = conn.execute(
        "SELECT si.*, p.name AS package_name, p.length, p.width, p.height, p.weight_kg, p.color "
        "FROM tlp_shipment_items si "
        "LEFT JOIN tlp_packages p ON p.id = si.package_id "
        "WHERE si.shipment_id = ?", (shipment_id,)
    ).fetchall()
    s["items"] = [_row_to_dict(i) for i in items]
    conn.close()
    return jsonify(s)


@tlp_bp.route("/shipments/<int:shipment_id>", methods=["PUT"])
def update_shipment(shipment_id):
    data = request.json or {}
    conn = _get_db()
    existing = conn.execute("SELECT * FROM tlp_shipments WHERE id = ?", (shipment_id,)).fetchone()
    if not existing:
        conn.close()
        return jsonify({"error": "Shipment not found"}), 404
    c = conn.cursor()
    c.execute("""
        UPDATE tlp_shipments SET customer_name=?, reference_number=?, notes=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (
        data.get("customer_name", existing["customer_name"]),
        data.get("reference_number", existing["reference_number"]),
        data.get("notes", existing["notes"]),
        shipment_id,
    ))
    if "items" in data:
        c.execute("DELETE FROM tlp_shipment_items WHERE shipment_id = ?", (shipment_id,))
        for item in data["items"]:
            c.execute("""
                INSERT INTO tlp_shipment_items (shipment_id, package_id, quantity, notes)
                VALUES (?, ?, ?, ?)
            """, (shipment_id, item["package_id"], item.get("quantity", 1), item.get("notes", "")))
    conn.commit()
    row = conn.execute("SELECT * FROM tlp_shipments WHERE id = ?", (shipment_id,)).fetchone()
    conn.close()
    return jsonify(_row_to_dict(row))


@tlp_bp.route("/shipment-items/<int:item_id>", methods=["PUT"])
def update_shipment_item(item_id):
    data = request.json or {}
    conn = _get_db()
    existing = conn.execute("SELECT * FROM tlp_shipment_items WHERE id = ?", (item_id,)).fetchone()
    if not existing:
        conn.close()
        return jsonify({"error": "Shipment item not found"}), 404
    conn.execute("""
        UPDATE tlp_shipment_items SET package_id=?, quantity=?, notes=?
        WHERE id=?
    """, (
        data.get("package_id", existing["package_id"]),
        data.get("quantity", existing["quantity"]),
        data.get("notes", existing["notes"]),
        item_id,
    ))
    conn.commit()
    row = conn.execute("SELECT * FROM tlp_shipment_items WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    return jsonify(_row_to_dict(row))


@tlp_bp.route("/shipment-items/<int:item_id>", methods=["DELETE"])
def delete_shipment_item(item_id):
    conn = _get_db()
    c = conn.cursor()
    c.execute("DELETE FROM tlp_shipment_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    if c.rowcount == 0:
        return jsonify({"error": "Shipment item not found"}), 404
    return jsonify({"success": True})


@tlp_bp.route("/shipments/<int:shipment_id>", methods=["DELETE"])
def delete_shipment(shipment_id):
    conn = _get_db()
    c = conn.cursor()
    c.execute("DELETE FROM tlp_shipment_items WHERE shipment_id = ?", (shipment_id,))
    c.execute("DELETE FROM tlp_shipments WHERE id = ?", (shipment_id,))
    conn.commit()
    conn.close()
    if c.rowcount == 0:
        return jsonify({"error": "Shipment not found"}), 404
    return jsonify({"success": True})


# ─── Vehicle Containers (read vehicles with their container config) ──

@tlp_bp.route("/vehicle-containers", methods=["GET"])
def list_vehicle_containers():
    """Return all vehicles that have a container_config_id set."""
    conn = _get_db()
    rows = conn.execute("""
        SELECT v.id AS vehicle_id, v.plate_number, v.vehicle_type, v.current_driver,
               v.container_config_id,
               cc.id AS cc_id, cc.name AS container_name,
               cc.cargo_length_mm, cc.cargo_width_mm, cc.cargo_height_mm, cc.payload_kg
        FROM vehicles v
        LEFT JOIN container_configs cc ON cc.id = v.container_config_id
        WHERE v.container_config_id IS NOT NULL
        ORDER BY v.plate_number
    """).fetchall()
    result = []
    for r in rows:
        item = _row_to_dict(r)
        feats = conn.execute(
            "SELECT * FROM container_features WHERE container_config_id = ?",
            (r["cc_id"],)
        ).fetchall()
        item["features"] = [_row_to_dict(f) for f in feats]
        result.append(item)
    conn.close()
    return jsonify(result)


# ─── Load Plan CRUD ────────────────────────────────────────────

@tlp_bp.route("/plans", methods=["GET"])
def list_plans():
    conn = _get_db()
    rows = conn.execute("""
        SELECT lp.*, v.plate_number, v.vehicle_type,
               cc.name AS container_name, cc.cargo_length_mm, cc.cargo_width_mm,
               cc.cargo_height_mm, cc.payload_kg
        FROM tlp_load_plans lp
        LEFT JOIN vehicles v ON v.id = lp.vehicle_id
        LEFT JOIN container_configs cc ON cc.id = v.container_config_id
        ORDER BY lp.created_at DESC
    """).fetchall()
    result = []
    for r in rows:
        plan = _row_to_dict(r)
        placements = conn.execute("""
            SELECT pl.*, p.name AS package_name, p.length, p.width, p.height, p.weight_kg, p.color
            FROM tlp_placements pl
            LEFT JOIN tlp_packages p ON p.id = pl.package_id
            WHERE pl.load_plan_id = ?
            ORDER BY pl.load_sequence
        """, (r["id"],)).fetchall()
        plan["placements"] = [_row_to_dict(pl) for pl in placements]
        result.append(plan)
    conn.close()
    return jsonify(result)


@tlp_bp.route("/plans", methods=["POST"])
def create_plan():
    data = request.json or {}
    if not data.get("vehicle_id"):
        return jsonify({"error": "vehicle_id is required"}), 400
    conn = _get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO tlp_load_plans (name, vehicle_id, shipment_id, planner, notes, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        data.get("name", ""),
        data["vehicle_id"],
        data.get("shipment_id"),
        data.get("planner", ""),
        data.get("notes", ""),
        data.get("status", "draft"),
    ))
    plan_id = c.lastrowid
    for pl in data.get("placements", []):
        c.execute("""
            INSERT INTO tlp_placements (load_plan_id, shipment_item_id, package_id,
              x, y, z, rotation, stack_level, load_sequence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            plan_id,
            pl.get("shipment_item_id"),
            pl["package_id"],
            pl["x"], pl["y"], pl.get("z", 0),
            pl.get("rotation", 0),
            pl.get("stack_level", 0),
            pl.get("load_sequence"),
        ))
    conn.commit()
    row = conn.execute("SELECT * FROM tlp_load_plans WHERE id = ?", (plan_id,)).fetchone()
    conn.close()
    return jsonify(_row_to_dict(row)), 201


@tlp_bp.route("/plans/<int:plan_id>", methods=["GET"])
def get_plan(plan_id):
    conn = _get_db()
    row = conn.execute("""
        SELECT lp.*, v.plate_number, v.vehicle_type,
               cc.id AS cc_id, cc.name AS container_name,
               cc.cargo_length_mm, cc.cargo_width_mm, cc.cargo_height_mm, cc.payload_kg
        FROM tlp_load_plans lp
        LEFT JOIN vehicles v ON v.id = lp.vehicle_id
        LEFT JOIN container_configs cc ON cc.id = v.container_config_id
        WHERE lp.id = ?
    """, (plan_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Plan not found"}), 404
    plan = _row_to_dict(row)
    if plan.get("cc_id"):
        feats = conn.execute(
            "SELECT * FROM container_features WHERE container_config_id = ?",
            (plan["cc_id"],)
        ).fetchall()
        plan["features"] = [_row_to_dict(f) for f in feats]
    placements = conn.execute("""
        SELECT pl.*, p.name AS package_name, p.length, p.width, p.height, p.weight_kg, p.allow_stacking, p.allow_rotation, p.fragile, p.color, p.max_top_weight_kg, p.max_stack_layers
        FROM tlp_placements pl
        LEFT JOIN tlp_packages p ON p.id = pl.package_id
        WHERE pl.load_plan_id = ?
        ORDER BY pl.load_sequence
    """, (plan_id,)).fetchall()
    plan["placements"] = [_row_to_dict(pl) for pl in placements]
    conn.close()
    return jsonify(plan)


@tlp_bp.route("/plans/<int:plan_id>", methods=["PUT"])
def update_plan(plan_id):
    data = request.json or {}
    conn = _get_db()
    existing = conn.execute("SELECT * FROM tlp_load_plans WHERE id = ?", (plan_id,)).fetchone()
    if not existing:
        conn.close()
        return jsonify({"error": "Plan not found"}), 404
    conn.execute("""
        UPDATE tlp_load_plans SET name=?, vehicle_id=?, shipment_id=?,
          planner=?, notes=?, status=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (
        data.get("name", existing["name"]),
        data.get("vehicle_id", existing["vehicle_id"]),
        data.get("shipment_id", existing["shipment_id"]),
        data.get("planner", existing["planner"]),
        data.get("notes", existing["notes"]),
        data.get("status", existing["status"]),
        plan_id,
    ))
    if "placements" in data:
        conn.execute("DELETE FROM tlp_placements WHERE load_plan_id = ?", (plan_id,))
        for pl in data["placements"]:
            conn.execute("""
                INSERT INTO tlp_placements (load_plan_id, shipment_item_id, package_id,
                  x, y, z, rotation, stack_level, load_sequence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan_id,
                pl.get("shipment_item_id"),
                pl["package_id"],
                pl["x"], pl["y"], pl.get("z", 0),
                pl.get("rotation", 0),
                pl.get("stack_level", 0),
                pl.get("load_sequence"),
            ))
    conn.commit()
    row = conn.execute("SELECT * FROM tlp_load_plans WHERE id = ?", (plan_id,)).fetchone()
    conn.close()
    return jsonify(_row_to_dict(row))


@tlp_bp.route("/plans/<int:plan_id>", methods=["DELETE"])
def delete_plan(plan_id):
    conn = _get_db()
    c = conn.cursor()
    c.execute("DELETE FROM tlp_placements WHERE load_plan_id = ?", (plan_id,))
    c.execute("DELETE FROM tlp_load_plans WHERE id = ?", (plan_id,))
    conn.commit()
    conn.close()
    if c.rowcount == 0:
        return jsonify({"error": "Plan not found"}), 404
    return jsonify({"success": True})


# ─── Session Validation ────────────────────────────────────────

@tlp_bp.route("/session/validate", methods=["POST"])
def validate_placement():
    """Validate a single placement without saving.
    Body: { vehicle_id, package_id, x, y, z, rotation, existing_placements }
    """
    data = request.json or {}
    from truck_load_planner.session import LoadPlanningSession
    from truck_load_planner.models import ContainerConfig, Package

    conn = _get_db()
    # Read vehicle → container_config → features
    vrow = conn.execute("""
        SELECT v.*, cc.id AS cc_id, cc.name AS container_name,
               cc.cargo_length_mm, cc.cargo_width_mm, cc.cargo_height_mm, cc.payload_kg
        FROM vehicles v
        LEFT JOIN container_configs cc ON cc.id = v.container_config_id
        WHERE v.id = ?
    """, (data.get("vehicle_id"),)).fetchone()
    pkg_row = conn.execute("SELECT * FROM tlp_packages WHERE id = ?",
                           (data.get("package_id"),)).fetchone()
    conn.close()

    if not vrow:
        return jsonify({"error": "Vehicle not found"}), 404
    vdata = dict(vrow)
    if not vdata.get("cc_id"):
        return jsonify({"error": "Vehicle has no container config"}), 404
    if not pkg_row:
        return jsonify({"error": "Package not found"}), 404

    cc = ContainerConfig(
        id=vdata["cc_id"],
        name=vdata.get("container_name", ""),
        cargo_length_mm=vdata["cargo_length_mm"],
        cargo_width_mm=vdata["cargo_width_mm"],
        cargo_height_mm=vdata["cargo_height_mm"],
        payload_kg=vdata["payload_kg"],
    )
    package = Package.from_row(_row_to_dict(pkg_row))

    # Re-read features
    conn2 = _get_db()
    feat_rows = conn2.execute(
        "SELECT * FROM container_features WHERE container_config_id = ?",
        (cc.id,)
    ).fetchall()
    conn2.close()
    features = [_row_to_dict(f) for f in feat_rows]

    session = LoadPlanningSession()
    session.select_container(cc, features)
    session.load_placements(data.get("existing_placements", []))

    result = session.try_place(
        package, data.get("x", 0), data.get("y", 0),
        data.get("z", 0), data.get("rotation", 0)
    )

    if result.get("placement"):
        result["placement"] = {k: v for k, v in result["placement"].items()
                               if not k.startswith("_")}

    return jsonify(result)


# ─── Auto Arrange ────────────────────────────────────────────────

from truck_load_planner.engine.distribution import distribute_across_vehicles, find_best_for_pkg
from truck_load_planner.optimization.vehicle_cost import compute_fleet_cost

_distribute_across_vehicles = distribute_across_vehicles


def _build_placement_dict(pl, vehicle_id=None):
    """Convert an engine Placement to a frontend-compatible dict."""
    pkg = pl.package
    d = {
        "package_id": pl.package_id,
        "x": pl.x, "y": pl.y, "z": pl.z,
        "rotation": pl.rotation,
        "load_sequence": pl.load_sequence,
        "door_used": getattr(pl, "door_used", "rear"),
        "_package": {
            "id": pkg.id if pkg else None,
            "name": pkg.name if pkg else "",
            "length": pkg.length_mm if pkg else 0,
            "width": pkg.width_mm if pkg else 0,
            "height": pkg.height_mm if pkg else 0,
            "weight_kg": pkg.weight_kg if pkg else 0,
            "color": pkg.color if pkg else "#3b82f6",
            "stackable": pkg.stackable if pkg else False,
            "allow_stacking": pkg.stackable if pkg else False,
            "max_top_weight_kg": pkg.max_top_weight_kg if pkg else 0.0,
            "max_stack_layers": pkg.max_stack_layers if pkg else 0,
        } if pkg else None,
        "_name": pkg.name if pkg else "",
        "_length": pkg.length_mm if pkg else 0,
        "_width": pkg.width_mm if pkg else 0,
        "_height": pkg.height_mm if pkg else 0,
        "_weight_kg": pkg.weight_kg if pkg else 0,
        "_color": pkg.color if pkg else "#3b82f6",
    }
    if vehicle_id is not None:
        d["vehicle_id"] = vehicle_id
    return d


def _get_packages_from_request(data, conn):
    """Extract expanded EnginePackage list from shipment_id or inline packages."""
    from truck_load_planner.models import ContainerConfig, Package as LegacyPackage
    from truck_load_planner.engine.package import Package as EnginePackage

    shipment_id = data.get("shipment_id")
    if shipment_id:
        items = conn.execute(
            "SELECT si.*, p.name AS package_name, p.length, p.width, p.height, "
            "p.weight_kg, p.allow_stacking, p.allow_rotation, p.fragile, p.color, "
            "p.max_top_weight_kg, p.max_stack_layers "
            "FROM tlp_shipment_items si "
            "LEFT JOIN tlp_packages p ON p.id = si.package_id "
            "WHERE si.shipment_id = ?",
            (shipment_id,)
        ).fetchall()
        pkgs = []
        for it in items:
            itd = dict(it)
            lpkg = LegacyPackage.from_row(itd)
            qty = itd.get("quantity", 1) or 1
            old_clr = getattr(lpkg, 'clearance_mm', getattr(lpkg, 'clearance', None))
            h_clr = float(old_clr) if old_clr is not None else 10.0
            ep = EnginePackage(
                id=lpkg.id, name=lpkg.name,
                length_mm=lpkg.length, width_mm=lpkg.width,
                height_mm=lpkg.height, weight_kg=lpkg.weight_kg,
                stackable=bool(lpkg.allow_stacking),
                allow_rotation=bool(lpkg.allow_rotation),
                fragile=bool(lpkg.fragile),
                color=lpkg.color,
                horizontal_clearance_mm=h_clr,
                max_top_weight_kg=float(getattr(lpkg, 'max_top_weight_kg', 0.0)),
                max_stack_layers=int(getattr(lpkg, 'max_stack_layers', 0)),
            )
            for _ in range(qty):
                pkgs.append(ep)
        return pkgs

    if data.get("packages"):
        pkgs = []
        for pd in data["packages"]:
            old_clr = pd.get("clearance_mm", pd.get("clearance", None))
            h_clr = float(old_clr) if old_clr is not None else 10.0
            pkgs.append(EnginePackage(
                id=pd.get("package_id", pd.get("id")),
                name=pd.get("name", ""),
                length_mm=pd.get("length", 0),
                width_mm=pd.get("width", 0),
                height_mm=pd.get("height", 0),
                weight_kg=pd.get("weight_kg", 0),
                stackable=bool(pd.get("stackable", pd.get("allow_stacking", 0))),
                allow_rotation=bool(pd.get("allow_rotation", 0)),
                fragile=bool(pd.get("fragile", 0)),
                color=pd.get("color", "#3b82f6"),
                horizontal_clearance_mm=h_clr,
                max_top_weight_kg=float(pd.get("max_top_weight_kg", 0.0)),
                max_stack_layers=int(pd.get("max_stack_layers", 0)),
            ))
        return pkgs

    return []


def _load_vehicle_session(conn, vehicle_id):
    """Load a single vehicle's container config and create a LoadPlanningSession."""
    from truck_load_planner.session import LoadPlanningSession
    from truck_load_planner.models import ContainerConfig

    vrow = conn.execute("""
        SELECT v.*, cc.id AS cc_id, cc.name AS container_name,
               cc.cargo_length_mm, cc.cargo_width_mm, cc.cargo_height_mm, cc.payload_kg
        FROM vehicles v
        LEFT JOIN container_configs cc ON cc.id = v.container_config_id
        WHERE v.id = ?
    """, (vehicle_id,)).fetchone()

    if not vrow or not vrow["cc_id"]:
        return None, None

    vdata = dict(vrow)
    cc = ContainerConfig(
        id=vdata["cc_id"],
        name=vdata.get("container_name", ""),
        cargo_length_mm=vdata["cargo_length_mm"],
        cargo_width_mm=vdata["cargo_width_mm"],
        cargo_height_mm=vdata["cargo_height_mm"],
        payload_kg=vdata["payload_kg"],
    )

    feat_rows = conn.execute(
        "SELECT * FROM container_features WHERE container_config_id = ?",
        (cc.id,)
    ).fetchall()
    features = [_row_to_dict(f) for f in feat_rows]

    session = LoadPlanningSession()
    session.select_container(cc, features)
    session.vehicle_id = vehicle_id

    return session, vdata


def _distribute_across_vehicles(packages, vehicle_sessions, debug=False, profile=None):
    """Delegate to engine.distribution.distribute_across_vehicles."""
    return distribute_across_vehicles(packages, vehicle_sessions, debug=debug, profile=profile)


@tlp_bp.route("/auto-arrange", methods=["POST"])
def auto_arrange():
    """Auto-arrange packages into one or more vehicles.

    Single-vehicle (existing behaviour):
      Body: { vehicle_id, shipment_id (or packages), strategy, debug }

    Multi-vehicle (distribute packages to best-fit containers):
      Body: { shipment_id (or packages), strategy, debug }
      (omit vehicle_id to distribute across all available vehicles)
    """
    data = request.json or {}
    vehicle_id = data.get("vehicle_id")
    strategy = data.get("strategy", "optimized")
    debug = bool(data.get("debug", False))

    from truck_load_planner.engine.profile import PROFILES
    profile_name = data.get("profile", "balanced")
    profile = PROFILES.get(profile_name, PROFILES["balanced"])

    conn = _get_db()

    if vehicle_id:
        session, vdata = _load_vehicle_session(conn, vehicle_id)
        if not session:
            conn.close()
            return jsonify({"error": "Vehicle not found or has no container config"}), 404

        packages = _get_packages_from_request(data, conn)
        conn.close()

        if not packages:
            return jsonify({"error": "No packages to arrange"}), 400

        if profile and profile.candidate_limit and session._planner:
            session._planner._candidate_limit = profile.candidate_limit
        result = session.auto_arrange(
            packages=packages,
            strategy=strategy,
            debug=debug,
        )

        placements_out = [_build_placement_dict(pl) for pl in session._planner.placements]

        response_data = {
            "multi_vehicle": False,
            "profile": profile_name,
            "vehicle_id": vehicle_id,
            "success": result.failed_packages == 0 or result.placed_packages > 0,
            "summary": {
                "placed_packages": result.placed_packages,
                "failed_packages": result.failed_packages,
                "utilization": round(result.utilization, 1),
                "total_score": result.total_score,
                "warnings": result.warnings,
                "unplaced_packages": result.unplaced_packages,
            },
            "placements": placements_out,
            "statistics": session.get_status(),
            "debug_log": result.debug_log if debug else [],
        }

        return jsonify(response_data)

    # ── Multi-vehicle path ──
    # Load all vehicles that have container configs
    vrows = conn.execute("""
        SELECT v.id AS vehicle_id, v.plate_number, v.vehicle_type, v.current_driver,
               cc.id AS cc_id, cc.name AS container_name,
               cc.cargo_length_mm, cc.cargo_width_mm, cc.cargo_height_mm, cc.payload_kg,
               fvp.normal_l_per_100km
        FROM vehicles v
        INNER JOIN container_configs cc ON cc.id = v.container_config_id
        LEFT JOIN fuel_vehicle_profile fvp ON fvp.license_plate = v.plate_number
        ORDER BY v.plate_number
    """).fetchall()

    if not vrows:
        conn.close()
        return jsonify({"error": "No vehicles with container configs found"}), 404

    vehicle_sessions = []
    for vr in vrows:
        vinfo = dict(vr)
        session, _ = _load_vehicle_session(conn, vinfo["vehicle_id"])
        if session:
            if profile and profile.candidate_limit and session._planner:
                session._planner._candidate_limit = profile.candidate_limit
            vehicle_sessions.append((vinfo, session))

    packages = _get_packages_from_request(data, conn)
    conn.close()

    if not packages:
        return jsonify({"error": "No packages to arrange"}), 400
    if not vehicle_sessions:
        return jsonify({"error": "No vehicles with valid container configs"}), 404

    dist_start = time.time()
    placed, failed, unplaced, vehicle_map, dist_stats = _distribute_across_vehicles(
        packages, vehicle_sessions, debug=debug, profile=profile,
    )
    dist_time_ms = int((time.time() - dist_start) * 1000)

    # ── Repair phase: fleet-level Destroy-and-Repair ──────────────
    # Recompute counts after distribution
    placed = sum(len(s._planner.placements) for _, s in vehicle_sessions)

    placed_vehicle_map = {vinfo["vehicle_id"]: [] for vinfo, _ in vehicle_sessions}
    for vinfo, session in vehicle_sessions:
        vid = vinfo["vehicle_id"]
        for pl in session._planner.placements:
            if pl.package:
                placed_vehicle_map[vid].append(pl.package.name)

    # Build per-vehicle placements and statistics
    per_vehicle = []
    all_placements = []
    for vinfo, session in vehicle_sessions:
        v_placements = [_build_placement_dict(pl, vehicle_id=vinfo["vehicle_id"])
                        for pl in session._planner.placements]
        if v_placements:
            per_vehicle.append({
                "vehicle_id": vinfo["vehicle_id"],
                "plate_number": vinfo["plate_number"],
                "package_count": len(v_placements),
                "packages": placed_vehicle_map.get(vinfo["vehicle_id"], []),
                "statistics": session.get_status(),
            })
        all_placements.extend(v_placements)

    total_util = 0.0
    for pv in per_vehicle:
        stats = pv.get("statistics", {})
        total_util += stats.get("volume_used_pct", 0) if stats.get("volume_used_pct", 0) != 0 else 0
    avg_util = round(total_util / len(per_vehicle), 1) if per_vehicle else 0.0
    failed = len(packages) - placed
    fleet_cost = round(compute_fleet_cost(vehicle_sessions), 1)

    response_data = {
        "multi_vehicle": True,
        "profile": profile_name,
        "success": placed > 0,
        "summary": {
            "placed_packages": placed,
            "failed_packages": failed,
            "utilization": avg_util,
            "fleet_cost": fleet_cost,
            "warnings": [],
            "unplaced_packages": unplaced,
        },
        "per_vehicle": per_vehicle,
        "placements": all_placements,
        "debug_log": [],
        "profile_stats": {
            "profile": profile_name,
            "distribution_time_ms": dist_time_ms,
            "total_time_ms": dist_time_ms,
        },
    }

    return jsonify(response_data)
