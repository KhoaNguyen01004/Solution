import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.db import DatabaseManager

logger = logging.getLogger(__name__)

#: Root that uploads live under and that ``relative_path`` is stored
#: relative to. Defaults to the repository, which is right for local dev;
#: in production DATA_DIR points at Render's mounted disk, because the
#: container filesystem is wiped on every deploy and proof photos must not
#: be. Deliberately the *parent* of DeliveryPlans/ so that rows written
#: before the disk existed ("DeliveryPlans/2026/...") still resolve.
DATA_ROOT = Path(os.getenv("DATA_DIR") or Path(__file__).resolve().parent.parent.parent)
UPLOAD_ROOT = DATA_ROOT / "DeliveryPlans"

# Only image types the dashboard actually renders. The stored file is served
# back by GET /api/images/<id>/file via send_file(), which infers Content-Type
# from the extension — so an uploaded .html or .svg would be served as
# text/html or image/svg+xml from the application's own origin, i.e. stored
# XSS with full session access (audit S-05). SVG is excluded deliberately: it
# is an image format that can execute script.
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB — phone photos, not video

_UNSAFE_SEGMENT_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


class UploadRejected(ValueError):
    """Raised when an upload fails validation. Carries a user-safe message."""


def _safe_path_segment(value: Optional[str], fallback: str) -> str:
    """Reduce a user-supplied string to one safe filesystem path component.

    ``station_code`` and ``category`` are attacker-controlled (Excel import,
    POST /api/stops, and the upload form) and were previously interpolated
    straight into the upload path, so a value of ``../../../static/js`` let
    mkdir + save write anywhere inside the repository (audit S-04).

    Separators and traversal sequences are stripped rather than escaped, and
    a value that reduces to nothing (or to a bare dot sequence) falls back to
    a constant so the path always has a well-formed component.
    """
    text = (value or "").strip()
    text = text.replace("/", "_").replace("\\", "_")
    text = _UNSAFE_SEGMENT_CHARS.sub("_", text)
    text = text.strip("._")
    if not text or set(text) <= {".", "_"}:
        return fallback
    return text[:64]


def _validate_upload(file_storage) -> str:
    """Check extension and size. Returns the normalized extension."""
    original_name = file_storage.filename or ""
    ext = Path(original_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UploadRejected(
            f"Unsupported file type '{ext or original_name}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # FileStorage wraps a SpooledTemporaryFile; seek to the end to size it
    # without reading the whole payload into memory, then rewind so save()
    # still writes the complete file.
    stream = file_storage.stream
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(0)
    if size > MAX_UPLOAD_BYTES:
        raise UploadRejected(
            f"File is {size // 1024 // 1024} MB; the limit is "
            f"{MAX_UPLOAD_BYTES // 1024 // 1024} MB."
        )
    if size == 0:
        raise UploadRejected("File is empty.")

    return ext


def ensure_folder(category: str, plan_date: str, plate: str, station_code: str) -> Path:
    try:
        dt = datetime.fromisoformat(plan_date)
    except (ValueError, TypeError):
        dt = datetime.now()

    folder = (UPLOAD_ROOT / str(dt.year) / f"{dt.month:02d}" / f"{dt.day:02d}"
              / _safe_path_segment(plate, "unknown-vehicle")
              / _safe_path_segment(station_code, "unknown-station")
              / _safe_path_segment(category, "extra"))

    # Belt and braces: even with every segment sanitized, confirm the
    # resolved path is still inside UPLOAD_ROOT before creating it.
    resolved = folder.resolve()
    if not resolved.is_relative_to(UPLOAD_ROOT.resolve()):
        raise UploadRejected("Invalid upload destination.")

    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


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

        ext = _validate_upload(file_storage)

        folder = ensure_folder(category, plan_date, plate, station_code)
        original_name = file_storage.filename or f"image_{datetime.now().timestamp()}"
        # Timestamp alone is second-granularity, so two photos of the same
        # stop and category taken in the same second collided and one
        # silently overwrote the other — two DB rows pointing at one file,
        # i.e. lost proof-of-delivery evidence (audit C-08). The uuid suffix
        # keeps the sortable timestamp prefix while making collision
        # impossible.
        filename = f"{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:8]}{ext}"
        file_path = folder / filename

        file_storage.save(str(file_path))

        relative = str(file_path.relative_to(DATA_ROOT))

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
            full_path = DATA_ROOT / row["relative_path"]
            try:
                if full_path.exists():
                    full_path.unlink()
            except Exception as e:
                logger.warning("Failed to delete file %s: %s", full_path, e)

        c.execute("DELETE FROM delivery_stop_images WHERE id = ?", (image_id,))
        return c.rowcount > 0
