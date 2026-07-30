import logging
from datetime import datetime
from typing import Optional

from app.db import DatabaseManager

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = ("completed", "skipped", "cancelled")


def _get_plan_id_for_stop(conn, stop_id: int) -> Optional[int]:
    c = conn.cursor()
    c.execute("""
        SELECT va.plan_id FROM delivery_plan_stops s
        JOIN vehicle_assignments va ON va.id = s.vehicle_assignment_id
        WHERE s.id = ?
    """, (stop_id,))
    row = c.fetchone()
    return row["plan_id"] if row else None


def _maybe_complete_plan(conn, plan_id: Optional[int]):
    """Auto-completes a plan once every stop across every vehicle
    assignment under it has reached a terminal state — otherwise a plan
    never leaves the dashboard's active (confirmed/executing) view.
    """
    if plan_id is None:
        return
    c = conn.cursor()
    placeholders = ",".join("?" for _ in TERMINAL_STATUSES)
    c.execute(f"""
        SELECT COUNT(*) as remaining
        FROM stop_executions e
        JOIN delivery_plan_stops s ON s.id = e.stop_id
        JOIN vehicle_assignments va ON va.id = s.vehicle_assignment_id
        WHERE va.plan_id = ? AND e.status NOT IN ({placeholders})
    """, (plan_id, *TERMINAL_STATUSES))
    remaining = c.fetchone()["remaining"]
    if remaining == 0:
        c.execute(
            "UPDATE delivery_plans SET status = 'completed', updated_at = ? WHERE id = ? AND status != 'completed'",
            (datetime.now().isoformat(), plan_id),
        )


def get_current_stop(db_path: str, assignment_id: int) -> Optional[dict]:
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT s.*, e.id as execution_id, e.execution_sequence, e.status as execution_status,
                   e.skip_reason, e.cancel_reason, e.actual_arrival_at, e.actual_departure_at, e.completed_at
            FROM delivery_plan_stops s
            JOIN stop_executions e ON e.stop_id = s.id
            WHERE s.vehicle_assignment_id = ?
              AND e.status IN ('planned', 'enroute', 'arrived')
            ORDER BY e.execution_sequence
            LIMIT 1
        """, (assignment_id,))
        row = c.fetchone()
        return dict(row) if row else None


def get_stop_execution(db_path: str, stop_id: int) -> Optional[dict]:
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM stop_executions WHERE stop_id = ?", (stop_id,))
        row = c.fetchone()
        return dict(row) if row else None


def _update_execution(db_path: str, stop_id: int, **kwargs):
    allowed = {"status", "execution_sequence", "skip_reason", "cancel_reason",
               "actual_arrival_at", "actual_departure_at", "completed_at"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False
    updates["updated_at"] = datetime.now().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [stop_id]
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute(f"UPDATE stop_executions SET {set_clause} WHERE stop_id = ?", vals)
        ok = c.rowcount > 0
        if ok and updates.get("status") in TERMINAL_STATUSES:
            _maybe_complete_plan(conn, _get_plan_id_for_stop(conn, stop_id))
        return ok


def advance_stop(db_path: str, stop_id: int):
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM stop_executions WHERE stop_id = ?", (stop_id,))
        execution = c.fetchone()
        if not execution:
            return False, "Stop execution not found"

        status = execution["status"]
        now = datetime.now().isoformat()

        if status == "planned":
            c.execute("""
                UPDATE stop_executions SET status = 'arrived', actual_arrival_at = ?,
                    updated_at = ? WHERE stop_id = ?
            """, (now, now, stop_id))
        elif status == "arrived":
            c.execute("""
                UPDATE stop_executions SET status = 'completed', actual_departure_at = ?,
                    completed_at = ?, updated_at = ? WHERE stop_id = ?
            """, (now, now, now, stop_id))
            _maybe_complete_plan(conn, _get_plan_id_for_stop(conn, stop_id))
            return True, "completed"
        else:
            return False, f"Cannot advance stop in status '{status}'"

        return True, "advanced"


def skip_stop(db_path: str, stop_id: int, reason: str = ""):
    now = datetime.now().isoformat()
    return _update_execution(db_path, stop_id,
                             status="skipped", skip_reason=reason,
                             completed_at=now)


def cancel_stop(db_path: str, stop_id: int, reason: str = ""):
    now = datetime.now().isoformat()
    return _update_execution(db_path, stop_id,
                             status="cancelled", cancel_reason=reason,
                             completed_at=now)


def reorder_stops(db_path: str, assignment_id: int, stop_ids_in_order: list[int]):
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        now = datetime.now().isoformat()
        for idx, stop_id in enumerate(stop_ids_in_order):
            new_seq = idx + 1
            c.execute("""
                UPDATE stop_executions SET execution_sequence = ?, updated_at = ?
                WHERE stop_id = ? AND stop_id IN (
                    SELECT id FROM delivery_plan_stops WHERE vehicle_assignment_id = ?
                )
            """, (new_seq, now, stop_id, assignment_id))
        return True


def insert_temp_stop(db_path: str, assignment_id: int, after_sequence: int,
                     station_code: str = "", station_name: str = "",
                     address: str = "", lat: Optional[float] = None, lng: Optional[float] = None,
                     manager_name: str = "", manager_phone: str = "",
                     product_description: str = "", note: str = ""):
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()

        c.execute("""
            SELECT MAX(planned_sequence) as max_seq FROM delivery_plan_stops
            WHERE vehicle_assignment_id = ?
        """, (assignment_id,))
        max_seq = c.fetchone()["max_seq"] or 0
        new_seq = max_seq + 1

        c.execute("""
            INSERT INTO delivery_plan_stops
                (vehicle_assignment_id, planned_sequence, station_code, station_name,
                 address, lat, lng, manager_name, manager_phone, product_description, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (assignment_id, new_seq, station_code, station_name,
              address, lat, lng, manager_name, manager_phone, product_description, note))
        stop_id = c.lastrowid

        insert_seq = after_sequence + 1
        c.execute("""
            UPDATE stop_executions SET execution_sequence = execution_sequence + 1
            WHERE stop_id IN (
                SELECT id FROM delivery_plan_stops WHERE vehicle_assignment_id = ?
            ) AND stop_id != ? AND execution_sequence > ?
        """, (assignment_id, stop_id, after_sequence))

        c.execute("""
            INSERT INTO stop_executions (stop_id, execution_sequence, status)
            VALUES (?, ?, 'planned')
        """, (stop_id, insert_seq))

        # If the plan had already auto-completed, this new pending stop
        # must not stay silently hidden from the dashboard's active view.
        plan_id = _get_plan_id_for_stop(conn, stop_id)
        if plan_id is not None:
            c.execute(
                "UPDATE delivery_plans SET status = 'executing', updated_at = ? WHERE id = ? AND status = 'completed'",
                (datetime.now().isoformat(), plan_id),
            )

        return stop_id


def get_assignment_progress(db_path: str, assignment_id: int) -> dict:
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT e.status, COUNT(*) as count
            FROM delivery_plan_stops s
            JOIN stop_executions e ON e.stop_id = s.id
            WHERE s.vehicle_assignment_id = ?
            GROUP BY e.status
        """, (assignment_id,))
        counts = {r["status"]: r["count"] for r in c.fetchall()}

        total = sum(counts.values()) or 1
        completed = counts.get("completed", 0) + counts.get("skipped", 0) + counts.get("cancelled", 0)
        remaining = total - completed

        return {
            "total": total,
            "completed": completed,
            "remaining": remaining,
            "progress_pct": round(completed / total * 100, 1),
            "breakdown": counts,
        }


def get_dashboard_data(db_path: str):
    """Return all active (confirmed/executing) assignments with their
    current stop and progress breakdown.

    Fixed N+1: previously issued 1 query for assignments plus 2 more
    per assignment (current-stop + status-counts) — 101 queries for 50
    assignments. Now issues exactly 3 queries total regardless of N:
    assignments, current-stop-per-assignment (via a window function to
    pick the earliest active stop per assignment in one pass), and
    status-counts-per-assignment (via GROUP BY on both columns).
    """
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT
                va.id as assignment_id,
                va.plan_id,
                va.vehicle_id,
                va.driver_id,
                v.plate_number,
                COALESCE(NULLIF(d.name, ''), v.current_driver) as current_driver,
                dp.plan_name,
                dp.plan_date,
                dp.status as plan_status
            FROM vehicle_assignments va
            JOIN delivery_plans dp ON dp.id = va.plan_id
            LEFT JOIN vehicles v ON v.id = va.vehicle_id
            LEFT JOIN drivers d ON d.id = va.driver_id
            WHERE dp.status IN ('confirmed', 'executing')
            ORDER BY dp.plan_date DESC, va.sequence
        """)
        assignments = [dict(r) for r in c.fetchall()]

        if not assignments:
            return []

        assignment_ids = [a["assignment_id"] for a in assignments]
        placeholders = ",".join("?" for _ in assignment_ids)

        # One query for the current (earliest active) stop of every assignment.
        c.execute(f"""
            SELECT * FROM (
                SELECT s.*, e.id as execution_id, e.execution_sequence, e.status as execution_status,
                       e.skip_reason, e.cancel_reason, e.actual_arrival_at, e.actual_departure_at, e.completed_at,
                       ROW_NUMBER() OVER (
                           PARTITION BY s.vehicle_assignment_id ORDER BY e.execution_sequence
                       ) AS rn
                FROM delivery_plan_stops s
                JOIN stop_executions e ON e.stop_id = s.id
                WHERE s.vehicle_assignment_id IN ({placeholders})
                  AND e.status IN ('planned', 'enroute', 'arrived')
            ) WHERE rn = 1
        """, assignment_ids)
        current_stop_by_aid = {}
        for r in c.fetchall():
            d = dict(r)
            d.pop("rn", None)
            current_stop_by_aid[d["vehicle_assignment_id"]] = d

        # One query for status counts of every assignment.
        c.execute(f"""
            SELECT s.vehicle_assignment_id AS aid, e.status, COUNT(*) as count
            FROM delivery_plan_stops s
            JOIN stop_executions e ON e.stop_id = s.id
            WHERE s.vehicle_assignment_id IN ({placeholders})
            GROUP BY s.vehicle_assignment_id, e.status
        """, assignment_ids)
        counts_by_aid = {}
        for r in c.fetchall():
            counts_by_aid.setdefault(r["aid"], {})[r["status"]] = r["count"]

        result = []
        for a in assignments:
            aid = a["assignment_id"]
            a["current_stop"] = current_stop_by_aid.get(aid)

            counts = counts_by_aid.get(aid, {})
            total = sum(counts.values()) or 1
            completed = counts.get("completed", 0) + counts.get("skipped", 0) + counts.get("cancelled", 0)
            a["progress"] = {
                "total": total,
                "completed": completed,
                "remaining": total - completed,
                "progress_pct": round(completed / total * 100, 1),
                "breakdown": counts,
            }
            result.append(a)

        return result
