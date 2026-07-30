import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


def normalize_gps_position(raw_vehicle: dict) -> dict:
    """Flat dict of normalized telemetry — new fields (e.g. heading) can be
    added here later without breaking existing consumers, since callers
    already read named keys off this dict rather than assuming a fixed set.
    """
    speed_status = raw_vehicle.get("speed_status", "")
    return {
        "lat": float(raw_vehicle.get("latitude", 0)),
        "lng": float(raw_vehicle.get("longitude", 0)),
        "speed": speed_status,
        "speed_kmh": _parse_speed_kmh(speed_status),
        "vehicle_status": raw_vehicle.get("vehicle_status", "unknown"),
        "engine_status": raw_vehicle.get("engine_status", ""),
        "last_update": raw_vehicle.get("last_update", ""),
        "driver_name": raw_vehicle.get("driver_name", "Unknown"),
    }


def _parse_speed_kmh(speed_status: str) -> Optional[float]:
    """Defensively extracts a numeric km/h reading from TTAS's raw speed
    text — a Vietnamese status phrase (e.g. "Chạy 42km/h"), not a clean
    number. Mirrors the extraction already used in app/routes/trips.py,
    except this returns None (rather than defaulting to 0) when nothing
    numeric is found, since 0 and "unknown" are different facts and this
    value is a supplementary operational signal only — never used for ETA
    or routing calculations.
    """
    if not speed_status:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", speed_status)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None
