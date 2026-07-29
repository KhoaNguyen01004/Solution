import logging
from datetime import date, datetime
from typing import Optional

from app.db import DatabaseManager

logger = logging.getLogger(__name__)


# ---- Drivers ----

def list_drivers(db_path: str):
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM drivers ORDER BY name")
        result = [dict(r) for r in c.fetchall()]
        seen = set(r["name"] for r in result if r.get("name"))
        c.execute("SELECT DISTINCT current_driver FROM vehicles WHERE current_driver IS NOT NULL AND current_driver != ''")
        for row in c.fetchall():
            name = row["current_driver"].strip()
            if name and name not in seen:
                result.append({"id": None, "name": name, "phone": "", "license_number": ""})
                seen.add(name)
        return result


def create_driver(db_path: str, name: str, phone: str = "", license_number: str = ""):
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO drivers (name, phone, license_number) VALUES (?, ?, ?)",
                  (name, phone, license_number))
        return c.lastrowid


# ---- Delivery Plans ----

def list_plans(db_path: str, status: Optional[str] = None):
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        if status:
            c.execute("SELECT * FROM delivery_plans WHERE status = ? ORDER BY plan_date DESC, created_at DESC", (status,))
        else:
            c.execute("SELECT * FROM delivery_plans ORDER BY plan_date DESC, created_at DESC")
        return [dict(r) for r in c.fetchall()]


def get_plan(db_path: str, plan_id: int):
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM delivery_plans WHERE id = ?", (plan_id,))
        row = c.fetchone()
        if not row:
            return None
        plan = dict(row)

        c.execute("""
            SELECT va.*, v.plate_number, d.name as driver_name
            FROM vehicle_assignments va
            LEFT JOIN vehicles v ON v.id = va.vehicle_id
            LEFT JOIN drivers d ON d.id = va.driver_id
            WHERE va.plan_id = ?
            ORDER BY va.sequence
        """, (plan_id,))
        assignments = [dict(r) for r in c.fetchall()]

        for assignment in assignments:
            c.execute("""
                SELECT s.*, e.id as execution_id, e.execution_sequence, e.status as execution_status,
                       e.skip_reason, e.cancel_reason, e.actual_arrival_at, e.actual_departure_at, e.completed_at
                FROM delivery_plan_stops s
                LEFT JOIN stop_executions e ON e.stop_id = s.id
                WHERE s.vehicle_assignment_id = ?
                ORDER BY COALESCE(e.execution_sequence, s.planned_sequence)
            """, (assignment["id"],))
            assignment["stops"] = [dict(r) for r in c.fetchall()]

        plan["assignments"] = assignments
        return plan


def create_plan(db_path: str, plan_name: str, plan_date: str, description: str = "", created_by: str = ""):
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO delivery_plans (plan_name, plan_date, description, status, created_by) VALUES (?, ?, ?, 'draft', ?)",
            (plan_name, plan_date, description, created_by)
        )
        return c.lastrowid


def update_plan(db_path: str, plan_id: int, **kwargs):
    allowed = {"plan_name", "plan_date", "description", "status", "created_by"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False
    updates["updated_at"] = datetime.now().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [plan_id]
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute(f"UPDATE delivery_plans SET {set_clause} WHERE id = ?", vals)
        return c.rowcount > 0


def delete_plan(db_path: str, plan_id: int):
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM delivery_plans WHERE id = ?", (plan_id,))
        return c.rowcount > 0


# ---- Vehicle Assignments ----

def list_assignments(db_path: str, plan_id: Optional[int] = None):
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        if plan_id:
            c.execute("""
                SELECT va.*, v.plate_number, d.name as driver_name
                FROM vehicle_assignments va
                LEFT JOIN vehicles v ON v.id = va.vehicle_id
                LEFT JOIN drivers d ON d.id = va.driver_id
                WHERE va.plan_id = ?
                ORDER BY va.sequence
            """, (plan_id,))
        else:
            c.execute("""
                SELECT va.*, v.plate_number, d.name as driver_name
                FROM vehicle_assignments va
                LEFT JOIN vehicles v ON v.id = va.vehicle_id
                LEFT JOIN drivers d ON d.id = va.driver_id
                ORDER BY va.plan_id, va.sequence
            """)
        return [dict(r) for r in c.fetchall()]


def get_assignment(db_path: str, assignment_id: int):
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT va.*, v.plate_number, d.name as driver_name
            FROM vehicle_assignments va
            LEFT JOIN vehicles v ON v.id = va.vehicle_id
            LEFT JOIN drivers d ON d.id = va.driver_id
            WHERE va.id = ?
        """, (assignment_id,))
        row = c.fetchone()
        if not row:
            return None
        return dict(row)


def create_assignment(db_path: str, plan_id: int, vehicle_id: int,
                      driver_id: Optional[int] = None, sequence: int = 0, notes: str = ""):
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO vehicle_assignments (plan_id, vehicle_id, driver_id, sequence, notes) VALUES (?, ?, ?, ?, ?)",
            (plan_id, vehicle_id, driver_id, sequence, notes)
        )
        return c.lastrowid


def update_assignment(db_path: str, assignment_id: int, **kwargs):
    allowed = {"vehicle_id", "driver_id", "sequence", "notes"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False
    vals = list(updates.values()) + [assignment_id]
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute(f"UPDATE vehicle_assignments SET {set_clause} WHERE id = ?", vals)
        return c.rowcount > 0


def delete_assignment(db_path: str, assignment_id: int):
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM vehicle_assignments WHERE id = ?", (assignment_id,))
        return c.rowcount > 0


# ---- Delivery Plan Stops ----

def list_stops(db_path: str, assignment_id: int):
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT s.*, e.id as execution_id, e.execution_sequence, e.status as execution_status,
                   e.skip_reason, e.cancel_reason, e.actual_arrival_at, e.actual_departure_at, e.completed_at
            FROM delivery_plan_stops s
            LEFT JOIN stop_executions e ON e.stop_id = s.id
            WHERE s.vehicle_assignment_id = ?
            ORDER BY COALESCE(e.execution_sequence, s.planned_sequence)
        """, (assignment_id,))
        return [dict(r) for r in c.fetchall()]


def get_stop(db_path: str, stop_id: int):
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT s.*, e.id as execution_id, e.execution_sequence, e.status as execution_status,
                   e.skip_reason, e.cancel_reason, e.actual_arrival_at, e.actual_departure_at, e.completed_at
            FROM delivery_plan_stops s
            LEFT JOIN stop_executions e ON e.stop_id = s.id
            WHERE s.id = ?
        """, (stop_id,))
        row = c.fetchone()
        if not row:
            return None
        return dict(row)


def create_stop(db_path: str, assignment_id: int, planned_sequence: int,
                station_code: str = "", station_name: str = "", address: str = "",
                lat: Optional[float] = None, lng: Optional[float] = None,
                manager_name: str = "", manager_phone: str = "",
                product_description: str = "", note: str = ""):
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO delivery_plan_stops
                (vehicle_assignment_id, planned_sequence, station_code, station_name,
                 address, lat, lng, manager_name, manager_phone, product_description, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (assignment_id, planned_sequence, station_code, station_name,
              address, lat, lng, manager_name, manager_phone, product_description, note))
        stop_id = c.lastrowid

        c.execute("""
            INSERT INTO stop_executions (stop_id, execution_sequence, status)
            VALUES (?, ?, 'planned')
        """, (stop_id, planned_sequence))
        return stop_id


def update_stop(db_path: str, stop_id: int, **kwargs):
    allowed = {"station_code", "station_name", "address", "lat", "lng",
               "manager_name", "manager_phone", "product_description", "note"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False
    vals = list(updates.values()) + [stop_id]
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute(f"UPDATE delivery_plan_stops SET {set_clause} WHERE id = ?", vals)
        return c.rowcount > 0


def delete_stop(db_path: str, stop_id: int):
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM stop_executions WHERE stop_id = ?", (stop_id,))
        c.execute("DELETE FROM delivery_plan_stops WHERE id = ?", (stop_id,))
        return c.rowcount > 0


def bulk_create_stops(db_path: str, assignment_id: int, stops: list[dict]):
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        for s in stops:
            c.execute("""
                INSERT INTO delivery_plan_stops
                    (vehicle_assignment_id, planned_sequence, station_code, station_name,
                     address, lat, lng, manager_name, manager_phone, product_description, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                assignment_id,
                s.get("planned_sequence", 0),
                s.get("station_code", ""),
                s.get("station_name", ""),
                s.get("address", ""),
                s.get("lat"),
                s.get("lng"),
                s.get("manager_name", ""),
                s.get("manager_phone", ""),
                s.get("product_description", ""),
                s.get("note", ""),
            ))
            stop_id = c.lastrowid
            c.execute("""
                INSERT INTO stop_executions (stop_id, execution_sequence, status)
                VALUES (?, ?, 'planned')
            """, (stop_id, s.get("planned_sequence", 0)))
        return True


# ---- Excel Import Pipeline ----

def parse_excel_rows(file_path: str):
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError("openpyxl is required for Excel import. Install with: pip install openpyxl")

    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    headers = [str(h).strip().lower() if h else "" for h in rows[0]]
    data_rows = rows[1:]

    col_map = {}
    for i, h in enumerate(headers):
        if "xe" in h or "vehicle" in h or "plate" in h or "biển" in h or "bsx" in h:
            col_map["vehicle"] = i
        elif "sequence" in h or "thứ tự" in h or "stt" in h or "order" in h:
            col_map["sequence"] = i
        elif "station_code" in h or "mã trạm" in h or "mã" in h:
            col_map["station_code"] = i
        elif "station" in h or "trạm" in h or "name" in h or "tên" in h:
            col_map["station_name"] = i
        elif "address" in h or "địa chỉ" in h or "dia chi" in h:
            col_map["address"] = i
        elif "lat" in h or "latitude" in h or "vĩ độ" in h:
            col_map["lat"] = i
        elif "lng" in h or "longitude" in h or "kinh độ" in h or "long" in h:
            col_map["lng"] = i
        elif "manager" in h or "quản lý" in h or "ql" in h or "người" in h:
            col_map["manager_name"] = i
        elif "phone" in h or "điện thoại" in h or "sdt" in h or "mobile" in h:
            col_map["manager_phone"] = i
        elif "product" in h or "hàng" in h or "sản phẩm" in h or "sp" in h:
            col_map["product_description"] = i
        elif "note" in h or "ghi chú" in h or "note" in h:
            col_map["note"] = i

    parsed = []
    for row in data_rows:
        if not any(v is not None for v in row):
            continue
        entry = {}
        for key, idx in col_map.items():
            if idx < len(row):
                entry[key] = row[idx]
        parsed.append(entry)
    return parsed


def validate_import_rows(rows: list[dict]) -> list[dict]:
    errors = []
    for i, row in enumerate(rows):
        row_errors = []
        if not row.get("vehicle"):
            row_errors.append(f"Row {i+2}: missing vehicle identifier")
        if not row.get("station_code") and not row.get("station_name"):
            row_errors.append(f"Row {i+2}: missing station code or name")
        lat = row.get("lat")
        lng = row.get("lng")
        if lat is not None:
            try:
                lat = float(lat)
                if not (-90 <= lat <= 90):
                    row_errors.append(f"Row {i+2}: invalid latitude")
            except (TypeError, ValueError):
                row_errors.append(f"Row {i+2}: latitude is not a number")
        if lng is not None:
            try:
                lng = float(lng)
                if not (-180 <= lng <= 180):
                    row_errors.append(f"Row {i+2}: invalid longitude")
            except (TypeError, ValueError):
                row_errors.append(f"Row {i+2}: longitude is not a number")
        errors.append({"row": i + 2, "errors": row_errors})
    return errors


def preview_import(rows: list[dict]) -> dict:
    errors = validate_import_rows(rows)
    has_errors = any(e["errors"] for e in errors)

    vehicle_groups = {}
    for row in rows:
        key = str(row.get("vehicle", "")).strip()
        if key not in vehicle_groups:
            vehicle_groups[key] = []
        vehicle_groups[key].append(row)

    assignments_preview = []
    for vehicle_key, stops in vehicle_groups.items():
        stops = sorted(stops, key=lambda s: int(s.get("sequence", 0) or 0))
        assignments_preview.append({
            "vehicle_identifier": vehicle_key,
            "stop_count": len(stops),
            "stops": [
                {
                    "sequence": s.get("sequence"),
                    "station_code": str(s.get("station_code", "") or ""),
                    "station_name": str(s.get("station_name", "") or ""),
                    "address": str(s.get("address", "") or ""),
                    "lat": s.get("lat"),
                    "lng": s.get("lng"),
                    "product": str(s.get("product_description", "") or ""),
                }
                for s in stops
            ]
        })

    return {
        "total_rows": len(rows),
        "total_assignments": len(assignments_preview),
        "has_errors": has_errors,
        "errors": errors,
        "assignments": assignments_preview,
    }


def confirm_import(db_path: str, plan_id: int, import_data: list[dict]):
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()

        c.execute("SELECT id, plate_number FROM vehicles")
        vehicles_map = {}
        for r in c.fetchall():
            vehicles_map[r["plate_number"]] = r["id"]

        vehicle_groups = {}
        for row in import_data:
            key = str(row.get("vehicle", "")).strip()
            if key not in vehicle_groups:
                vehicle_groups[key] = []
            vehicle_groups[key].append(row)

        seq = 0
        for vehicle_key, stops in vehicle_groups.items():
            seq += 1
            vehicle_id = vehicles_map.get(vehicle_key)
            if not vehicle_id:
                c.execute("INSERT INTO vehicles (plate_number) VALUES (?)", (vehicle_key,))
                vehicle_id = c.lastrowid
                vehicles_map[vehicle_key] = vehicle_id

            c.execute(
                "INSERT INTO vehicle_assignments (plan_id, vehicle_id, sequence) VALUES (?, ?, ?)",
                (plan_id, vehicle_id, seq)
            )
            assignment_id = c.lastrowid

            stops = sorted(stops, key=lambda s: int(s.get("sequence", 0) or 0))
            for s in stops:
                planned_seq = int(s.get("sequence", 0) or 0)
                c.execute("""
                    INSERT INTO delivery_plan_stops
                        (vehicle_assignment_id, planned_sequence, station_code, station_name,
                         address, lat, lng, manager_name, manager_phone, product_description, note)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    assignment_id,
                    planned_seq,
                    str(s.get("station_code", "") or ""),
                    str(s.get("station_name", "") or ""),
                    str(s.get("address", "") or ""),
                    s.get("lat"),
                    s.get("lng"),
                    str(s.get("manager_name", "") or ""),
                    str(s.get("manager_phone", "") or ""),
                    str(s.get("product_description", "") or ""),
                    str(s.get("note", "") or ""),
                ))
                stop_id = c.lastrowid
                c.execute("""
                    INSERT INTO stop_executions (stop_id, execution_sequence, status)
                    VALUES (?, ?, 'planned')
                """, (stop_id, planned_seq))

            c.execute(
                "UPDATE delivery_plans SET status = 'confirmed', imported_at = ? WHERE id = ?",
                (datetime.now().isoformat(), plan_id)
            )

        return True
