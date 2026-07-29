import logging

logger = logging.getLogger(__name__)


def normalize_gps_position(raw_vehicle: dict) -> dict:
    return {
        "lat": float(raw_vehicle.get("latitude", 0)),
        "lng": float(raw_vehicle.get("longitude", 0)),
        "speed": raw_vehicle.get("speed_status", ""),
        "vehicle_status": raw_vehicle.get("vehicle_status", "unknown"),
        "engine_status": raw_vehicle.get("engine_status", ""),
        "last_update": raw_vehicle.get("last_update", ""),
        "driver_name": raw_vehicle.get("driver_name", "Unknown"),
    }
