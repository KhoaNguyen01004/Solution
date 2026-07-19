"""
Flask Blueprint for Truck Load Planner API endpoints.
All routes are prefixed with /api/tlp.
"""

import json
import sqlite3
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
    rows = conn.execute("SELECT * FROM tlp_packages ORDER BY name").fetchall()
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
          allow_stacking, allow_rotation, fragile, color, default_qty)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["name"], data["length"], data["width"], data["height"],
        data["weight_kg"],
        1 if data.get("allow_stacking") else 0,
        1 if data.get("allow_rotation") else 0,
        1 if data.get("fragile") else 0,
        data.get("color", "#3b82f6"),
        data.get("default_qty", 1),
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
          color=?, default_qty=?, updated_at=CURRENT_TIMESTAMP
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
        SELECT pl.*, p.name AS package_name, p.length, p.width, p.height, p.weight_kg, p.allow_stacking, p.color
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

def _expand_candidates(base_candidates, allow_rotation):
    """Expand (x,y,z) tuples with rotation variants."""
    expanded = []
    seen = set()
    for pos in base_candidates:
        if isinstance(pos, dict):
            x, y, z = pos.get("x", 0), pos.get("y", 0), pos.get("z", 0)
        else:
            x, y, z = pos[0], pos[1], pos[2]
        key0 = (x, y, z, 0)
        if key0 not in seen:
            seen.add(key0)
            expanded.append({"x": x, "y": y, "z": z, "rotation": 0})
        if allow_rotation:
            key90 = (x, y, z, 90)
            if key90 not in seen:
                seen.add(key90)
                expanded.append({"x": x, "y": y, "z": z, "rotation": 90})
    return expanded


def _candidate_priority(pkg, pos, container):
    """Lightweight priority score for a candidate placement position.

    Higher = more promising. Used to rank candidates before expensive
    validation so that good placements are found and accepted earlier.

    Factors (most to least important):
      1. Container surfaces touched (corner placements score highest)
      2. Lower Z — prefer floor placements
      3. Greater wall-contact area
      4. Back-to-front — prefer positions closer to the back wall (x=0),
         so loading fills from the far end toward the door
      5. Proximity to the front-left-bottom origin
    """
    x, y, z = pos["x"], pos["y"], pos["z"]
    rot = pos["rotation"]

    if rot == 0:
        dx, dy, dz = pkg.length_mm, pkg.width_mm, pkg.height_mm
    else:
        dx, dy, dz = pkg.width_mm, pkg.length_mm, pkg.height_mm

    # 1. Touching surfaces (0-6 → score 0-60)
    touches = 0
    if x == 0:               touches += 1
    if x + dx == container.length: touches += 1
    if y == 0:               touches += 1
    if y + dy == container.width:  touches += 1
    if z == 0:               touches += 1
    if z + dz == container.height: touches += 1
    touch_score = touches * 10.0

    # 2. Z-height (lower → better, score 0-15)
    z_score = (1.0 - z / container.height) * 15.0 if container.height > 0 else 0.0

    # 3. Wall-contact area (score 0-15)
    contact = 0.0
    if x == 0:               contact += dy * dz
    if x + dx == container.length: contact += dy * dz
    if y == 0:               contact += dx * dz
    if y + dy == container.width:  contact += dx * dz
    if z == 0:               contact += dx * dy
    if z + dz == container.height: contact += dx * dy
    max_contact = 2 * (dx * dy + dy * dz + dx * dz)
    wall_score = (contact / max_contact * 15.0) if max_contact > 0 else 0.0

    # 4. Back-to-front loading direction (score 0-20)
    # Lower x = closer to back wall (far from rear door), loaded first
    back_score = (1.0 - x / container.length) * 20.0 if container.length > 0 else 0.0

    # 5. Proximity to front-center (score 0-10)
    # Prefers innermost (low x) without Y bias toward either wall.
    # This replaces the old origin-proximity which pulled everything to y=0.
    fc_dist = (x**2 + (y - container.width / 2)**2 + z**2) ** 0.5
    max_fc = (container.length**2 + (container.width / 2)**2 + container.height**2) ** 0.5
    front_center_score = (1.0 - fc_dist / max_fc) * 10.0 if max_fc > 0 else 0.0

    return touch_score + z_score + wall_score + back_score + front_center_score


def _build_placement_dict(pl, vehicle_id=None):
    """Convert an engine Placement to a frontend-compatible dict."""
    pkg = pl.package
    d = {
        "package_id": pl.package_id,
        "x": pl.x, "y": pl.y, "z": pl.z,
        "rotation": pl.rotation,
        "load_sequence": pl.load_sequence,
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
            "p.weight_kg, p.allow_stacking, p.allow_rotation, p.fragile, p.color "
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
            ep = EnginePackage(
                id=lpkg.id, name=lpkg.name,
                length_mm=lpkg.length, width_mm=lpkg.width,
                height_mm=lpkg.height, weight_kg=lpkg.weight_kg,
                stackable=bool(lpkg.allow_stacking),
                allow_rotation=bool(lpkg.allow_rotation),
                fragile=bool(lpkg.fragile),
                color=lpkg.color,
                clearance_mm=float(getattr(lpkg, 'clearance_mm', 10.0)),
            )
            for _ in range(qty):
                pkgs.append(ep)
        return pkgs

    if data.get("packages"):
        pkgs = []
        for pd in data["packages"]:
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
                clearance_mm=float(pd.get("clearance_mm", pd.get("clearance", 10.0))),
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


def _distribute_across_vehicles(packages, vehicle_sessions, debug=False):
    """Distribute packages across multiple vehicles using best-fit-decreasing.

    Minimises the number of vehicles used by filling each vehicle to capacity
    before opening the next one. For each package, active (already-used)
    vehicles are tried first; only when none can accommodate the package is
    a new vehicle opened.

    Uses Best-Fit Decreasing: among vehicles where the package fits, pick the
    one where the package consumes the largest fraction of remaining capacity
    (least waste), weighted together with placement quality.
    """
    sorted_pkgs = sorted(
        packages,
        key=lambda p: (
            p.stackable,
            -(p.length_mm * p.width_mm * p.height_mm),
            -(p.length_mm * p.width_mm),
            -p.weight_kg,
        ),
    )

    placed = 0
    failed = 0
    unplaced = []
    placed_vehicle_map = {vinfo["vehicle_id"]: [] for vinfo, _ in vehicle_sessions}
    active_indices: list[int] = []  # indices of vehicle_sessions that already have packages

    def _find_best_for_pkg(pkg, vinfo, session):
        """Return (best_score, best_pos) or (None, None) if no valid position."""
        best_score = -1.0
        best_pos = None
        planner = session._planner
        container = planner.state.container
        candidates = list(planner.get_candidate_points())

        # Add right-wall candidate for better left-right balance
        clearance = getattr(pkg, 'clearance_mm', 10)
        right_y = container.width - pkg.width_mm - clearance
        if right_y > clearance:
            right_candidate = (0, right_y, 0)
            if right_candidate not in candidates:
                candidates.insert(0, right_candidate)

        expanded = _expand_candidates(candidates, pkg.allow_rotation)
        # Rank by priority — more promising candidates validated first
        # so that excellent placements are found earlier (fewer iterations)
        prioritized = sorted(
            expanded,
            key=lambda pos: _candidate_priority(pkg, pos, container),
            reverse=True,
        )
        for pos in prioritized:
            vresult = planner.validate_position(
                pkg, pos["x"], pos["y"], pos["z"], pos["rotation"],
            )
            if not vresult.valid:
                continue
            score = planner.evaluate_position(
                pkg, pos["x"], pos["y"], pos["z"], pos["rotation"],
            )
            if score.total > best_score:
                best_score = score.total
                best_pos = pos
                if best_score >= 99.99:
                    break

        # ── Y-slide pass: if no position found, try sliding candidates left/right ──
        if best_pos is None:
            from truck_load_planner.engine.candidate_points import generate_slide_candidates
            slide_cands = generate_slide_candidates(candidates, pkg, container)
            for pos in slide_cands:
                vresult = planner.validate_position(
                    pkg, pos["x"], pos["y"], pos["z"], pos["rotation"],
                )
                if not vresult.valid:
                    continue
                score = planner.evaluate_position(
                    pkg, pos["x"], pos["y"], pos["z"], pos["rotation"],
                )
                if score.total > best_score:
                    best_score = score.total
                    best_pos = pos
                    if best_score >= 99.99:
                        break

        return best_score, best_pos

    def _estimate_remaining_after(pkg, pos, session):
        """Estimate remaining capacity % after placing pkg at pos.

        Returns (vol_pct, floor_pct, payload_pct). Lower = tighter fit
        = less waste. The *pos* is needed to determine floor consumption
        (packages at z>0 don't consume floor footprint).
        """
        planner = session._planner
        container = planner.state.container
        stats = planner.get_statistics()

        total_vol_mm3 = container.length * container.width * container.height
        used_vol_mm3 = stats.get("volume_used_m3", 0) * 1_000_000_000
        rem_vol = max(0.0, total_vol_mm3 - used_vol_mm3
                      - pkg.length_mm * pkg.width_mm * pkg.height_mm)

        total_floor_mm2 = container.length * container.width
        used_floor_pct = stats.get("floor_used_pct", 0) / 100.0
        used_floor_mm2 = used_floor_pct * total_floor_mm2
        floor_footprint = pkg.length_mm * pkg.width_mm if pos["z"] == 0 else 0
        rem_floor = max(0.0, total_floor_mm2 - used_floor_mm2 - floor_footprint)

        rem_payload = max(0.0, stats.get("weight_remaining_kg",
                          container.payload_kg) - pkg.weight_kg)

        vol_pct = rem_vol / total_vol_mm3 * 100 if total_vol_mm3 > 0 else 0.0
        floor_pct = (rem_floor / total_floor_mm2 * 100
                     if total_floor_mm2 > 0 else 0.0)
        payload_pct = (rem_payload / container.payload_kg * 100
                       if container.payload_kg > 0 else 0.0)
        return vol_pct, floor_pct, payload_pct

    for pkg in sorted_pkgs:
        best_waste = float("inf")
        best_score = -1.0
        best_session = None
        best_pos = None
        best_vinfo = None

        def _is_better(waste, score):
            """Primary: less remaining capacity (tighter fit).
            Secondary: higher placement score (tiebreaker)."""
            nonlocal best_waste, best_score
            return (waste < best_waste - 1e-9
                    or (abs(waste - best_waste) < 1e-9 and score > best_score))

        # Phase 1: try active (already-used) vehicles first
        for idx in active_indices:
            vinfo, session = vehicle_sessions[idx]
            score, pos = _find_best_for_pkg(pkg, vinfo, session)
            if pos is not None:
                rv, rf, rp = _estimate_remaining_after(pkg, pos, session)
                waste = rv + rf + rp
                if _is_better(waste, score):
                    best_waste = waste
                    best_score = score
                    best_session = session
                    best_pos = pos
                    best_vinfo = vinfo
                    if score >= 99.99:
                        break

        # Phase 2: if no active vehicle works, try the next unused vehicle
        if best_pos is None:
            new_active = None
            for idx, (vinfo, session) in enumerate(vehicle_sessions):
                if idx in active_indices:
                    continue
                score, pos = _find_best_for_pkg(pkg, vinfo, session)
                if pos is not None:
                    rv, rf, rp = _estimate_remaining_after(pkg, pos, session)
                    waste = rv + rf + rp
                    if _is_better(waste, score):
                        best_waste = waste
                        best_score = score
                        best_session = session
                        best_pos = pos
                        best_vinfo = vinfo
                        new_active = idx
                        if score >= 99.99:
                            break
            if new_active is not None:
                active_indices.append(new_active)

        # Phase 3: if the package literally touches the rear wall, redirect to
        # the last vehicle unconditionally (if it can accommodate). The last
        # vehicle has the most unused space, and rear-wall packages unload first.
        if best_pos is not None and len(vehicle_sessions) > 1:
            last_idx = len(vehicle_sessions) - 1
            last_vinfo, last_session = vehicle_sessions[last_idx]
            if last_vinfo["vehicle_id"] != best_vinfo["vehicle_id"]:
                container = best_session._planner.state.container
                dx = pkg.length_mm if best_pos["rotation"] == 0 else pkg.width_mm
                gap = container.length - (best_pos["x"] + dx)
                if gap <= 0:  # touches rear wall
                    last_score, last_pos = _find_best_for_pkg(pkg, last_vinfo, last_session)
                    if last_pos is not None:
                        rv, rf, rp = _estimate_remaining_after(pkg, last_pos, last_session)
                        last_waste = rv + rf + rp
                        best_waste, best_score = last_waste, last_score
                        best_session, best_pos = last_session, last_pos
                        best_vinfo = last_vinfo
                        if last_idx not in active_indices:
                            active_indices.append(last_idx)

        if best_session and best_pos:
            p_result = best_session._planner.place_package(
                pkg, best_pos["x"], best_pos["y"], best_pos["z"], best_pos["rotation"],
            )
            if p_result.valid:
                placed += 1
                placed_vehicle_map[best_vinfo["vehicle_id"]].append(pkg.name)
            else:
                failed += 1
                unplaced.append(pkg.name)
        else:
            failed += 1
            unplaced.append(pkg.name)

    return placed, failed, unplaced, placed_vehicle_map


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
    strategy = data.get("strategy", "largest_first")
    debug = bool(data.get("debug", False))

    conn = _get_db()

    if vehicle_id:
        # ── Single-vehicle path ──
        session, vdata = _load_vehicle_session(conn, vehicle_id)
        if not session:
            conn.close()
            return jsonify({"error": "Vehicle not found or has no container config"}), 404

        packages = _get_packages_from_request(data, conn)
        conn.close()

        if not packages:
            return jsonify({"error": "No packages to arrange"}), 400

        result = session.auto_arrange(
            packages=packages,
            strategy=strategy,
            debug=debug,
        )

        placements_out = [_build_placement_dict(pl) for pl in session._planner.placements]

        return jsonify({
            "multi_vehicle": False,
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
        })

    # ── Multi-vehicle path ──
    # Load all vehicles that have container configs
    vrows = conn.execute("""
        SELECT v.id AS vehicle_id, v.plate_number, v.vehicle_type, v.current_driver,
               cc.id AS cc_id, cc.name AS container_name,
               cc.cargo_length_mm, cc.cargo_width_mm, cc.cargo_height_mm, cc.payload_kg
        FROM vehicles v
        INNER JOIN container_configs cc ON cc.id = v.container_config_id
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
            vehicle_sessions.append((vinfo, session))

    packages = _get_packages_from_request(data, conn)
    conn.close()

    if not packages:
        return jsonify({"error": "No packages to arrange"}), 400
    if not vehicle_sessions:
        return jsonify({"error": "No vehicles with valid container configs"}), 404

    placed, failed, unplaced, vehicle_map = _distribute_across_vehicles(
        packages, vehicle_sessions, debug=debug,
    )

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
                "packages": vehicle_map.get(vinfo["vehicle_id"], []),
                "statistics": session.get_status(),
            })
        all_placements.extend(v_placements)

    total_util = 0.0
    for pv in per_vehicle:
        stats = pv.get("statistics", {})
        total_util += stats.get("volume_used_pct", 0) if stats.get("volume_used_pct", 0) != 0 else 0
    avg_util = round(total_util / len(per_vehicle), 1) if per_vehicle else 0.0

    return jsonify({
        "multi_vehicle": True,
        "success": placed > 0,
        "summary": {
            "placed_packages": placed,
            "failed_packages": failed,
            "utilization": avg_util,
            "warnings": [],
            "unplaced_packages": unplaced,
        },
        "per_vehicle": per_vehicle,
        "placements": all_placements,
        "debug_log": [],
    })
