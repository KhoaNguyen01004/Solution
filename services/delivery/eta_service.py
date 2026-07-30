import logging
import math
import threading
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# Route/ETA cache — avoids re-hitting ORS every poll for an assignment whose
# remaining stops and GPS position haven't meaningfully changed. Scoped to
# this module (not app/state.py, which is documented as being for the
# fleet/fuel/oil/trips blueprints + TTAS session, a different concern).
_route_cache = {}  # assignment_id -> {"key": stops_key, "gps": (lat, lng), "result": [...]}
_route_cache_lock = threading.Lock()
ROUTE_CACHE_GPS_THRESHOLD_M = 50  # below this, treat GPS position as "unchanged"


def get_distance_meters(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (math.sin(delta_phi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def calculate_eta(ors_api_key: str, ors_base_url: str,
                  from_lat: float, from_lng: float,
                  to_lat: float, to_lng: float) -> dict:
    try:
        if not ors_api_key:
            dist_km = get_distance_meters(from_lat, from_lng, to_lat, to_lng) / 1000
            return {
                "distance_km": round(dist_km, 2),
                "duration_sec": None,
                "eta": None,
                "source": "haversine",
                "geometry": None,
            }

        url = f"{ors_base_url}/driving-hgv"
        params = {
            "api_key": ors_api_key,
            "start": f"{from_lng},{from_lat}",
            "end": f"{to_lng},{to_lat}",
        }
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if "features" in data and len(data["features"]) > 0:
            feature = data["features"][0]
            dist_km = feature["properties"]["segments"][0]["distance"] / 1000
            duration_sec = feature["properties"]["segments"][0]["duration"]
            coords = (feature.get("geometry") or {}).get("coordinates") or []
            # ORS/GeoJSON coordinates are [lng, lat]; Leaflet wants [lat, lng].
            geometry = [[c[1], c[0]] for c in coords] or None
            return {
                "distance_km": round(dist_km, 2),
                "duration_sec": duration_sec,
                "eta": duration_sec,
                "source": "ors",
                "geometry": geometry,
            }

        dist_km = get_distance_meters(from_lat, from_lng, to_lat, to_lng) / 1000
        return {
            "distance_km": round(dist_km, 2),
            "duration_sec": None,
            "eta": None,
            "source": "haversine",
            "geometry": None,
        }
    except Exception as e:
        logger.warning("ORS ETA calculation failed: %s", e)
        dist_km = get_distance_meters(from_lat, from_lng, to_lat, to_lng) / 1000
        return {
            "distance_km": round(dist_km, 2),
            "duration_sec": None,
            "eta": None,
            "source": "haversine_fallback",
            "geometry": None,
        }


def _compute_etas_for_stops(ors_api_key: str, ors_base_url: str,
                             current_lat: float, current_lng: float,
                             stops: list[dict]) -> list[dict]:
    cumulative_duration = 0.0
    cumulative_distance = 0.0
    results = []
    prev_lat, prev_lng = current_lat, current_lng

    for stop in stops:
        stop_lat = stop.get("lat")
        stop_lng = stop.get("lng")
        if stop_lat is None or stop_lng is None:
            results.append({**stop, "stop_id": stop.get("id"), "distance_km": None,
                            "duration_sec": None, "cumulative_sec": None, "cumulative_km": None,
                            "eta_seconds": None, "geometry": None})
            continue

        leg = calculate_eta(ors_api_key, ors_base_url,
                            prev_lat, prev_lng, stop_lat, stop_lng)
        if leg.get("duration_sec"):
            cumulative_duration += leg["duration_sec"]
        if leg.get("distance_km"):
            cumulative_distance += leg["distance_km"]

        results.append({
            **stop,
            "stop_id": stop.get("id"),
            "distance_km": leg["distance_km"],
            "duration_sec": leg["duration_sec"],
            "cumulative_sec": cumulative_duration,
            "cumulative_km": round(cumulative_distance, 2),
            "eta_seconds": cumulative_duration,
            "geometry": leg.get("geometry"),
        })

        if stop_lat is not None and stop_lng is not None:
            prev_lat, prev_lng = stop_lat, stop_lng

    return results


def _stops_cache_key(stops: list[dict]):
    return tuple((s.get("id"), s.get("lat"), s.get("lng")) for s in stops)


def calculate_etas_for_stops(ors_api_key: str, ors_base_url: str,
                              current_lat: float, current_lng: float,
                              stops: list[dict],
                              assignment_id: Optional[int] = None) -> list[dict]:
    """Same computation as _compute_etas_for_stops, with an optional
    in-memory cache keyed by assignment_id. A cached result is reused only
    when the remaining stop set/order/destinations are identical AND the
    vehicle hasn't moved more than ROUTE_CACHE_GPS_THRESHOLD_M — i.e. it's
    invalidated by assignment change, stop order change, stop completion/
    skip (both alter the remaining-stop set), or significant GPS movement.
    assignment_id=None (the default) bypasses the cache entirely.
    """
    if assignment_id is None:
        return _compute_etas_for_stops(ors_api_key, ors_base_url, current_lat, current_lng, stops)

    stops_key = _stops_cache_key(stops)

    with _route_cache_lock:
        cached = _route_cache.get(assignment_id)

    if cached is not None and cached["key"] == stops_key:
        moved_m = get_distance_meters(cached["gps"][0], cached["gps"][1], current_lat, current_lng)
        if moved_m < ROUTE_CACHE_GPS_THRESHOLD_M:
            return cached["result"]

    result = _compute_etas_for_stops(ors_api_key, ors_base_url, current_lat, current_lng, stops)

    with _route_cache_lock:
        _route_cache[assignment_id] = {"key": stops_key, "gps": (current_lat, current_lng), "result": result}

    return result


def calculate_travelled_distance_km(stops: list[dict], current_lat: float, current_lng: float) -> float:
    """Approximate straight-line distance already covered on this assignment:
    sums stop-to-stop gaps for stops already passed (completed/skipped, in
    planned_sequence order), plus the gap from the last passed stop to the
    vehicle's current position. Intentionally straight-line rather than
    road-based — avoids extra ORS calls for a secondary, best-effort figure.
    """
    ordered = sorted(stops, key=lambda s: s.get("planned_sequence") or 0)
    passed = [s for s in ordered if s.get("execution_status") in ("completed", "skipped")]
    if not passed:
        return 0.0

    total_m = 0.0
    prev_lat, prev_lng = None, None
    for s in passed:
        lat, lng = s.get("lat"), s.get("lng")
        if lat is None or lng is None:
            continue
        if prev_lat is not None:
            total_m += get_distance_meters(prev_lat, prev_lng, lat, lng)
        prev_lat, prev_lng = lat, lng

    if prev_lat is not None:
        total_m += get_distance_meters(prev_lat, prev_lng, current_lat, current_lng)

    return round(total_m / 1000, 2)
