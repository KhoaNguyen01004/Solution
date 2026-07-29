"""
OpenRouteService (ORS) routing helpers.

Extracted from app.py. Used by app/routes/trips.py's route refresh logic.
"""
import requests

from app import config
from app.utils.geo import get_distance_meters


def get_routing_profile(vehicle_type):
    vehicle_type = (vehicle_type or "").lower()
    if "dau" in vehicle_type or "heavy" in vehicle_type or "truck" in vehicle_type:
        return "driving-hgv"
    if "tai" in vehicle_type or "van" in vehicle_type:
        return "driving-hgv"
    return "driving-hgv"


def get_route_coords(start_lng, start_lat, end_lng, end_lat, profile="driving-hgv"):
    try:
        if not config.ORS_API_KEY:
            print("Warning: ORS_API_KEY not set, using straight line")
            return {
                "coordinates": [[start_lng, start_lat], [end_lng, end_lat]],
                "distance": get_distance_meters(start_lat, start_lng, end_lat, end_lng) / 1000,
                "duration": None
            }

        url = f"{config.ORS_BASE_URL}/{profile}"
        params = {
            "api_key": config.ORS_API_KEY,
            "start": f"{start_lng},{start_lat}",
            "end": f"{end_lng},{end_lat}"
        }
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if "features" in data and len(data["features"]) > 0:
            feature = data["features"][0]
            return {
                "coordinates": feature["geometry"]["coordinates"],
                "distance": feature["properties"]["segments"][0]["distance"] / 1000,
                "duration": feature["properties"]["segments"][0]["duration"]
            }
        return {
            "coordinates": [[start_lng, start_lat], [end_lng, end_lat]],
            "distance": get_distance_meters(start_lat, start_lng, end_lat, end_lng) / 1000,
            "duration": None
        }
    except Exception as e:
        print(f"Error fetching route: {e}")
        return {
            "coordinates": [[start_lng, start_lat], [end_lng, end_lat]],
            "distance": get_distance_meters(start_lat, start_lng, end_lat, end_lng) / 1000,
            "duration": None
        }
