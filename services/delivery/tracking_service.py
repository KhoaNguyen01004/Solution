"""GPS telemetry normalization for the delivery dashboard.

Input contract
--------------
``normalize_gps_position()`` takes a **raw TTAS DevList item** — the dicts
returned by ``app.services.ttas_client.fetch_vehicle_data()``, whose keys are
TTAS's own (``biensoxe``, ``speed``, ``ad3``, ``trktime``, ``driver``,
``latitude``, ``longitude``).

Before 2026-07-31 this module read ``speed_status`` / ``vehicle_status`` /
``engine_status`` / ``last_update`` / ``driver_name`` off that raw dict. Those
are the *output* key names of ``normalize_vehicle()``, not TTAS's input names,
so every one of them silently resolved to its default and no ``device_name``
was emitted at all — which meant the dashboard could never match a GPS
position to a vehicle (audit C-02). Raw-key parsing is therefore delegated to
``normalize_vehicle()`` rather than reimplemented here: it already owns the
six-key license-plate fallback chain, the Vietnamese speed-phrase → status
derivation, and ``safe_float``/``clean_text`` coercion. Duplicating that would
create a second source of truth for TTAS's field names.
"""
import logging
import re
from typing import Optional

from services.plate_utils import normalize_plate

logger = logging.getLogger(__name__)


def normalize_gps_position(raw_vehicle: dict) -> dict:
    """Flat dict of normalized telemetry for one vehicle.

    New fields can be added here without breaking existing consumers, since
    callers read named keys off this dict rather than assuming a fixed set.

    ``device_name`` is the license plate as TTAS reports it; ``plate_key`` is
    that plate reduced to its 5-digit serial via ``normalize_plate``, and is
    the field callers should join on — it is stable across the ``50E-18463`` /
    ``50E18463`` / ``50E 18463`` / ``18463`` formatting variants that TTAS and
    the ``vehicles`` table disagree about.
    """
    # Deferred import: app.services.ttas_client pulls in app.config, which
    # raises at import time when .env is absent. Keeping it out of module
    # scope lets this module (and its pure-function tests) be imported
    # without a configured environment. Deliberately not wrapped in
    # try/except — a genuine import failure must surface, not degrade.
    from app.services.ttas_client import normalize_vehicle

    vehicle = normalize_vehicle(raw_vehicle)

    device_name = vehicle.get("device_name", "")
    speed_status = vehicle.get("speed_status", "")

    # safe_float() coerces missing/garbage coordinates to 0.0 rather than
    # None, so an exact 0,0 reading is TTAS saying "no fix" — not a vehicle
    # in the Gulf of Guinea. Surface that as None so the frontend's existing
    # `if (!gps || gps.lat == null)` guard skips the marker.
    lat = vehicle.get("latitude")
    lng = vehicle.get("longitude")
    if not lat and not lng:
        lat = lng = None

    return {
        "device_name": device_name,
        "plate_key": normalize_plate(device_name),
        "lat": lat,
        "lng": lng,
        "speed": speed_status,
        "speed_kmh": _parse_speed_kmh(speed_status),
        "vehicle_status": vehicle.get("vehicle_status", "unknown"),
        "engine_status": vehicle.get("engine_status", ""),
        # Raw TTAS text for display; the ISO twin for anything computing an
        # age. None means "position is real, its age is unknown" — a third
        # state the dashboard must show rather than guess at.
        "last_update": vehicle.get("last_update", ""),
        "last_update_iso": vehicle.get("last_update_iso"),
        "driver_name": vehicle.get("driver_name", "Unknown"),
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
