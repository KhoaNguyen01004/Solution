import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.db import DatabaseManager

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_ROOT = BASE_DIR / "DeliveryPlans"


def ensure_folder(category: str, plan_date: str, plate: str, station_code: str) -> Path:
    try:
        dt = datetime.fromisoformat(plan_date)
    except (ValueError, TypeError):
        dt = datetime.now()
    folder = UPLOAD_ROOT / str(dt.year) / f"{dt.month:02d}" / f"{dt.day:02d}" / plate / station_code / category
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def upload_image(db_path: str, stop_id: int, file_storage,
                 category: str = "extra",
                 plan_date: Optional[str] = None,
                 plate: Optional[str] = None,
                 station_code: Optional[str] = None,
                 gps_lat: Optional[float] = None,
                 gps_lng: Optional[float] = None,
                 captured_at: Optional[str] = None,
                 uploaded_by: str = "") -> Optional[int]:
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT s.id, s.station_code, va.plan_id, dp.plan_date, v.plate_number
            FROM delivery_plan_stops s
            JOIN vehicle_assignments va ON va.id = s.vehicle_assignment_id
            JOIN delivery_plans dp ON dp.id = va.plan_id
            JOIN vehicles v ON v.id = va.vehicle_id
            WHERE s.id = ?
        """, (stop_id,))
        stop_info = c.fetchone()

        if not stop_info:
            return None

        plan_date = plan_date or stop_info["plan_date"]
        plate = plate or stop_info["plate_number"]
        station_code = station_code or stop_info["station_code"]

        folder = ensure_folder(category, plan_date, plate, station_code)
        original_name = file_storage.filename or f"image_{datetime.now().timestamp()}"
        ext = Path(original_name).suffix if original_name else ""
        filename = f"{int(datetime.now().timestamp())}{ext}"
        file_path = folder / filename

        file_storage.save(str(file_path))

        relative = str(file_path.relative_to(BASE_DIR))

        try:
            c.execute("""
                INSERT INTO delivery_stop_images
                    (stop_id, category, filename, relative_path, original_filename,
                     gps_lat, gps_lng, captured_at, uploaded_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (stop_id, category, filename, relative,
                  original_name, gps_lat, gps_lng, captured_at, uploaded_by))
        except Exception:
            if file_path.exists():
                file_path.unlink()
            raise

        return c.lastrowid


def list_images(db_path: str, stop_id: int):
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT * FROM delivery_stop_images
            WHERE stop_id = ?
            ORDER BY uploaded_at DESC
        """, (stop_id,))
        return [dict(r) for r in c.fetchall()]


def get_image(db_path: str, image_id: int) -> Optional[dict]:
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM delivery_stop_images WHERE id = ?", (image_id,))
        row = c.fetchone()
        return dict(row) if row else None


def delete_image(db_path: str, image_id: int) -> bool:
    with DatabaseManager(db_path).connect() as conn:
        c = conn.cursor()
        c.execute("SELECT relative_path FROM delivery_stop_images WHERE id = ?", (image_id,))
        row = c.fetchone()
        if row:
            full_path = BASE_DIR / row["relative_path"]
            try:
                if full_path.exists():
                    full_path.unlink()
            except Exception as e:
                logger.warning("Failed to delete file %s: %s", full_path, e)

        c.execute("DELETE FROM delivery_stop_images WHERE id = ?", (image_id,))
        return c.rowcount > 0
