import logging
import math
import requests
from typing import Optional

logger = logging.getLogger(__name__)


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
            return {
                "distance_km": round(dist_km, 2),
                "duration_sec": duration_sec,
                "eta": duration_sec,
                "source": "ors",
            }

        dist_km = get_distance_meters(from_lat, from_lng, to_lat, to_lng) / 1000
        return {
            "distance_km": round(dist_km, 2),
            "duration_sec": None,
            "eta": None,
            "source": "haversine",
        }
    except Exception as e:
        logger.warning("ORS ETA calculation failed: %s", e)
        dist_km = get_distance_meters(from_lat, from_lng, to_lat, to_lng) / 1000
        return {
            "distance_km": round(dist_km, 2),
            "duration_sec": None,
            "eta": None,
            "source": "haversine_fallback",
        }


def calculate_etas_for_stops(ors_api_key: str, ors_base_url: str,
                              current_lat: float, current_lng: float,
                              stops: list[dict]) -> list[dict]:
    cumulative_duration = 0.0
    results = []
    prev_lat, prev_lng = current_lat, current_lng

    for stop in stops:
        stop_lat = stop.get("lat")
        stop_lng = stop.get("lng")
        if stop_lat is None or stop_lng is None:
            results.append({**stop, "distance_km": None, "duration_sec": None, "cumulative_sec": None})
            continue

        leg = calculate_eta(ors_api_key, ors_base_url,
                            prev_lat, prev_lng, stop_lat, stop_lng)
        if leg.get("duration_sec"):
            cumulative_duration += leg["duration_sec"]

        results.append({
            **stop,
            "distance_km": leg["distance_km"],
            "duration_sec": leg["duration_sec"],
            "cumulative_sec": cumulative_duration,
        })

        if stop_lat is not None and stop_lng is not None:
            prev_lat, prev_lng = stop_lat, stop_lng

    return results
