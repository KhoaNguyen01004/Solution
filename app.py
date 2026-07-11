import json
import os
import time
import math
import sqlite3
import threading
from flask import Flask, jsonify, render_template, request, Response
import requests
from dotenv import load_dotenv

# --------------------------
# Load Configuration
# --------------------------
load_dotenv()
BASE_DIR = os.path.dirname(__file__)

# Validate required environment variables
required_env_vars = [
    "ORS_API_KEY",
    "ORS_BASE_URL",
    "TTAS_TRACKING_PAGE_URL",
    "TTAS_TRACKING_API"
]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing_vars)}. Please set them in .env file!")

# OpenRouteService Configuration (REQUIRED to be set in .env)
ORS_API_KEY = os.getenv("ORS_API_KEY")
ORS_BASE_URL = os.getenv("ORS_BASE_URL")

# TTAS Configuration (REQUIRED to be set in .env)
TTAS_TRACKING_PAGE_URL = os.getenv("TTAS_TRACKING_PAGE_URL")
TTAS_TRACKING_API = os.getenv("TTAS_TRACKING_API")
TTAS_PAYLOAD = {"Running": 1, "Stop": 1, "LostGPRS": 1, "devname": "", "groupxe": "", "maptype": 2}
TTAS_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/json; charset=UTF-8",
    "Origin": os.getenv("TTAS_TRACKING_PAGE_URL", ""),
    "Referer": TTAS_TRACKING_PAGE_URL,
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
}

# Database & File Paths
DB_PATH = os.path.join(BASE_DIR, os.getenv("DB_PATH", "routing_system.db"))
MANUAL_LOCATIONS_FILE = os.path.join(BASE_DIR, os.getenv("MANUAL_LOCATIONS_FILE", "manual_locations.json"))

# Application Configuration
DEFAULT_RADIUS_KM = float(os.getenv("DEFAULT_RADIUS_KM", "3"))
MAX_LIVE_FETCH_ATTEMPTS = int(os.getenv("MAX_LIVE_FETCH_ATTEMPTS", "2"))
ROUTE_REFRESH_INTERVAL = int(os.getenv("ROUTE_REFRESH_INTERVAL_SECONDS", "60"))
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"

# --------------------------
# Global State
# --------------------------
route_data_cache = {}
cache_lock = threading.Lock()
_last_manual_update = 0.0
_oil_fetch_progress = {}
_oil_fetch_lock = threading.Lock()
KNOWN_LOCATIONS = {}
fleet_session = None

# --------------------------
# Utility Functions
# --------------------------
def get_distance_meters(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in meters using Haversine formula."""
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def calculate_polygon_centroid(polygon):
    """Calculate centroid (center) of a polygon given as list of [lat, lng] points.
    Uses the formula for centroid of a planar polygon: average of vertices weighted by the area of each sub-triangle."""
    if not polygon or len(polygon) < 3:
        return None
        
    # Ensure polygon is closed
    closed_polygon = polygon + [polygon[0]]
    signed_area = 0.0
    sum_lat = 0.0
    sum_lng = 0.0
    
    for i in range(len(closed_polygon) - 1):
        lat_i, lng_i = closed_polygon[i]
        lat_j, lng_j = closed_polygon[i + 1]
        
        term = (lat_i * lng_j) - (lat_j * lng_i)
        signed_area += term
        sum_lat += (lat_i + lat_j) * term
        sum_lng += (lng_i + lng_j) * term
        
    signed_area = signed_area / 2.0
    
    if abs(signed_area) < 1e-10:  # Degenerate polygon, just return average of vertices
        avg_lat = sum(p[0] for p in polygon) / len(polygon)
        avg_lng = sum(p[1] for p in polygon) / len(polygon)
        return [avg_lat, avg_lng]
    
    centroid_lat = sum_lat / (6 * signed_area)
    centroid_lng = sum_lng / (6 * signed_area)
    return [centroid_lat, centroid_lng]


def calculate_multi_polygon_centroid(polygons):
    """Calculate centroid of a multi-polygon (multiple polygons), returns weighted average of all polygon centroids."""
    if not polygons or not isinstance(polygons, list) or len(polygons) == 0:
        return None
        
    centroids = []
    areas = []
    
    for polygon in polygons:
        centroid = calculate_polygon_centroid(polygon)
        if centroid:
            centroids.append(centroid)
            # Calculate area for weighting
            closed_poly = polygon + [polygon[0]]
            area = 0.0
            for i in range(len(closed_poly) - 1):
                lat_i, lng_i = closed_poly[i]
                lat_j, lng_j = closed_poly[i + 1]
                area += (lat_i * lng_j) - (lat_j * lng_i)
            areas.append(abs(area / 2.0))
    
    if len(centroids) == 0:
        return None
        
    total_area = sum(areas)
    if total_area < 1e-10:  # All degenerate, average the centroids
        avg_lat = sum(c[0] for c in centroids) / len(centroids)
        avg_lng = sum(c[1] for c in centroids) / len(centroids)
        return [avg_lat, avg_lng]
        
    weighted_lat = 0.0
    weighted_lng = 0.0
    for i in range(len(centroids)):
        weight = areas[i] / total_area
        weighted_lat += centroids[i][0] * weight
        weighted_lng += centroids[i][1] * weight
    return [weighted_lat, weighted_lng]


def is_point_in_polygon(lat, lng, polygon):
    """Check if point (lat, lng) is inside polygon using Ray Casting algorithm."""
    if not polygon or len(polygon) < 3:
        return False
        
    inside = False
    n = len(polygon)
    x = lng
    y = lat
    
    for i in range(n):
        j = (i - 1) % n
        xi, yi = polygon[i][1], polygon[i][0]
        xj, yj = polygon[j][1], polygon[j][0]
        
        intersect = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi)
        if intersect:
            inside = not inside
    return inside


def is_point_in_location(lat, lng, location):
    """Check if point (lat, lng) is inside any polygon of a location."""
    if not location:
        return False
        
    polygons_to_check = []
    if location.get("polygons") and isinstance(location.get("polygons"), list):
        polygons_to_check = location["polygons"]
    elif location.get("corners") and isinstance(location.get("corners"), list):
        polygons_to_check = [location["corners"]]
    else:
        return False
        
    for polygon in polygons_to_check:
        if is_point_in_polygon(lat, lng, polygon):
            return True
    return False


def get_location_centroid(location):
    """Get centroid from a location object, handling single polygon, multi-polygon, or point."""
    if not location:
        return None
    if "polygons" in location and isinstance(location["polygons"], list):
        centroid = calculate_multi_polygon_centroid(location["polygons"])
        if centroid:
            return {"lat": centroid[0], "lng": centroid[1]}
    if "corners" in location:
        centroid = calculate_polygon_centroid(location["corners"])
        if centroid:
            return {"lat": centroid[0], "lng": centroid[1]}
    if "latitude" in location and "longitude" in location:
        return {"lat": location["latitude"], "lng": location["longitude"]}
    return None


def safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def clean_text(value):
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        return text.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text

# --------------------------
# Database Functions
# --------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Check if we need to migrate the old table (where vehicle_id was primary key)
    # Check if id is the first column and primary key
    c.execute("PRAGMA table_info(vehicle_trips)")
    table_info = c.fetchall()
    
    needs_migration = False
    if len(table_info) > 0:
        # Check if first column is not id or vehicle_id is primary key
        if table_info[0][1] != 'id' or table_info[0][5] != 1:
            needs_migration = True
    
    if needs_migration:
        print("Migrating vehicle_trips table to new schema...")
        
        # Rename old table
        c.execute("ALTER TABLE vehicle_trips RENAME TO vehicle_trips_old")
        
        # Create new table with correct schema
        c.execute('''
            CREATE TABLE vehicle_trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_id TEXT NOT NULL,
                vehicle_name TEXT,
                destination_lat REAL,
                destination_lng REAL,
                destination_name TEXT,
                pickup_lat REAL,
                pickup_lng REAL,
                pickup_name TEXT,
                customer_name TEXT,
                last_known_eta REAL,
                last_known_distance REAL,
                vehicle_type TEXT,
                status TEXT DEFAULT 'queued',
                queue_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Copy data from old table to new
        # Get old columns
        c.execute("PRAGMA table_info(vehicle_trips_old)")
        old_columns = [col[1] for col in c.fetchall()]
        
        # Build columns to select (exclude any new ones we have in new that old doesn't)
        columns_to_select = []
        for col in old_columns:
            if col in [
                'vehicle_id', 'vehicle_name', 'destination_lat', 'destination_lng',
                'destination_name', 'pickup_lat', 'pickup_lng', 'pickup_name',
                'customer_name', 'last_known_eta', 'last_known_distance',
                'vehicle_type', 'status', 'queue_order', 'created_at', 'updated_at'
            ]:
                columns_to_select.append(col)
        
        # Insert data
        placeholders = ','.join('?' * len(columns_to_select))
        c.execute(f'''
            INSERT INTO vehicle_trips ({','.join(columns_to_select)})
            SELECT {','.join(columns_to_select)} FROM vehicle_trips_old
        ''')
        
        # Drop old table
        c.execute("DROP TABLE vehicle_trips_old")
        
        conn.commit()
        print("Migration complete!")
    
    # Create table with all required columns (in case it didn't exist)
    c.execute('''
        CREATE TABLE IF NOT EXISTS vehicle_trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id TEXT NOT NULL,
            vehicle_name TEXT,
            destination_lat REAL,
            destination_lng REAL,
            destination_name TEXT,
            pickup_lat REAL,
            pickup_lng REAL,
            pickup_name TEXT,
            customer_name TEXT,
            last_known_eta REAL,
            last_known_distance REAL,
            vehicle_type TEXT,
            status TEXT DEFAULT 'queued',
            queue_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Check and add missing columns for existing databases
    existing_columns = [col[1] for col in c.execute("PRAGMA table_info(vehicle_trips)")]
    required_columns = [
        ('destination_name', 'TEXT'),
        ('pickup_lat', 'REAL'),
        ('pickup_lng', 'REAL'),
        ('pickup_name', 'TEXT'),
        ('vehicle_type', 'TEXT'),
        ('customer_name', 'TEXT'),
        ('status', 'TEXT'),
        ('queue_order', 'INTEGER'),
        ('phase', 'TEXT'),
        ('completed_at', 'TIMESTAMP'),
        ('driver_name', 'TEXT'),
        ('waypoints', 'TEXT'),  # JSON array of {name, lat, lng}
        ('canceled_at', 'TIMESTAMP'),
        ('cancel_reason', 'TEXT')
    ]
    for col_name, col_type in required_columns:
        if col_name not in existing_columns:
            try:
                c.execute(f"ALTER TABLE vehicle_trips ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass  # column may already exist despite PRAGMA
    
    conn.commit()

    # Geofence event log table
    c.execute('''
        CREATE TABLE IF NOT EXISTS geofence_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id TEXT NOT NULL,
            vehicle_name TEXT,
            trip_id INTEGER,
            event_type TEXT NOT NULL,
            location_name TEXT NOT NULL,
            lat REAL,
            lng REAL,
            phase INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()

    # ----- Oil Change Maintenance Tables -----
    c.execute('''
        CREATE TABLE IF NOT EXISTS oil_maintenance (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            license_plate        TEXT    NOT NULL UNIQUE,
            last_oil_change_km   INTEGER NOT NULL DEFAULT 0,
            last_oil_change_date TEXT    NOT NULL,
            maintenance_interval INTEGER NOT NULL DEFAULT 5000,
            created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS oil_km_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            license_plate TEXT NOT NULL,
            log_date      TEXT NOT NULL,
            km            INTEGER NOT NULL DEFAULT 0,
            fetched_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(license_plate, log_date)
        )
    ''')

    # ----- Fuel Efficiency / Refuel Log Table -----
    c.execute('''
        CREATE TABLE IF NOT EXISTS fuel_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            license_plate   TEXT    NOT NULL,
            log_date        TEXT    NOT NULL,
            log_time        TEXT    NOT NULL,
            gas_store       TEXT    NOT NULL DEFAULT '',
            old_km          INTEGER NOT NULL DEFAULT 0,
            new_km          INTEGER NOT NULL DEFAULT 0,
            liters          REAL    NOT NULL DEFAULT 0,
            driver_name     TEXT    NOT NULL DEFAULT '',
            unit_price      REAL    DEFAULT NULL,
            notes           TEXT    DEFAULT '',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ----- Fuel Vehicle Profile (manual normal L/100km per vehicle) -----
    c.execute('''
        CREATE TABLE IF NOT EXISTS fuel_vehicle_profile (
            license_plate       TEXT PRIMARY KEY,
            normal_l_per_100km  REAL NOT NULL DEFAULT 10.0,
            updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ----- Master Vehicles Table -----
    c.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number    TEXT NOT NULL UNIQUE,
            vehicle_type    TEXT NOT NULL DEFAULT '',
            current_driver  TEXT NOT NULL DEFAULT '',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ----- Vehicle Types Table -----
    c.execute('''
        CREATE TABLE IF NOT EXISTS vehicle_types (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')
    # Seed default types if table is empty
    c.execute("SELECT COUNT(*) FROM vehicle_types")
    if c.fetchone()[0] == 0:
        default_types = ["1 Ton", "1.5 Tons", "2 Tons", "3.5 Tons", "5 Tons", "8 Tons", "Tractor Head", "Container Truck"]
        for t in default_types:
            c.execute("INSERT OR IGNORE INTO vehicle_types (name) VALUES (?)", (t,))

    # Add vehicle_id column to fuel_log if missing
    c.execute("PRAGMA table_info(fuel_log)")
    fuel_cols = {col[1] for col in c.fetchall()}
    if 'vehicle_id' not in fuel_cols:
        c.execute("ALTER TABLE fuel_log ADD COLUMN vehicle_id INTEGER DEFAULT NULL")

    conn.commit()

    # Backfill vehicles + vehicle_id from existing fuel_log entries
    c.execute("SELECT DISTINCT license_plate, driver_name FROM fuel_log WHERE license_plate IS NOT NULL AND license_plate != ''")
    distinct_plates = c.fetchall()
    for plate, driver in distinct_plates:
        # Upsert vehicle
        c.execute(
            "INSERT INTO vehicles (plate_number, current_driver) VALUES (?, ?) ON CONFLICT(plate_number) DO UPDATE SET current_driver = COALESCE(NULLIF(?, ''), current_driver)",
            (plate, driver or '', driver or '')
        )
        # Link vehicle_id to fuel_log rows that don't have it
        c.execute(
            "UPDATE fuel_log SET vehicle_id = (SELECT id FROM vehicles WHERE plate_number = ?) WHERE vehicle_id IS NULL AND license_plate = ?",
            (plate, plate)
        )
    conn.commit()
    conn.close()

# --------------------------
# Location Management Functions
# --------------------------
def read_manual_locations():
    if not os.path.exists(MANUAL_LOCATIONS_FILE):
        return {}
    try:
        with open(MANUAL_LOCATIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"Error reading manual locations file: {e}")
        return {}


def write_manual_locations(locations):
    with open(MANUAL_LOCATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(locations, f, indent=2, ensure_ascii=False)


def parse_location_payload(data):
    name = (data.get("name") or "").strip()
    corners = data.get("corners")

    if not name:
        return None, "Location name is required"

    if not corners or not isinstance(corners, list) or len(corners) < 3:
        return None, "At least 3 corners are required"

    try:
        parsed_corners = []
        for corner in corners:
            if not isinstance(corner, list) or len(corner) < 2:
                return None, "Each corner must be [lat, lng]"
            lat = float(corner[0])
            lng = float(corner[1])
            if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                return None, "Invalid coordinate range"
            parsed_corners.append([lat, lng])
    except (TypeError, ValueError):
        return None, "Invalid corner coordinates"

    return {"name": name, "corners": parsed_corners}, None


def load_known_locations():
    normalized = {}
    for name, location in read_manual_locations().items():
        try:
            # Handle both old format (single corners) and new format (multiple polygons)
            if "polygons" in location and isinstance(location["polygons"], list):
                normalized[name] = {
                    "polygons": [
                        [[float(c[0]), float(c[1])] for c in polygon]
                        for polygon in location["polygons"]
                    ],
                    "type": "multi_polygon"
                }
            elif "corners" in location and len(location["corners"]) >= 3:
                normalized[name] = {
                    "polygons": [
                        [[float(c[0]), float(c[1])] for c in location["corners"]]
                    ],
                    "type": "multi_polygon"
                }
            elif "latitude" in location and "longitude" in location:
                lat = float(location["latitude"])
                lng = float(location["longitude"])
                radius_km = float(location.get("radius_km", DEFAULT_RADIUS_KM))
                delta_lat = radius_km / 111
                delta_lng = radius_km / (111 * math.cos(math.radians(lat)))
                normalized[name] = {
                    "polygons": [
                        [[lat + delta_lat, lng - delta_lng],
                         [lat + delta_lat, lng + delta_lng],
                         [lat - delta_lat, lng + delta_lng],
                         [lat - delta_lat, lng - delta_lng]]
                    ],
                    "type": "multi_polygon"
                }
        except (KeyError, TypeError, ValueError):
            continue
    return normalized

# --------------------------
# Routing Functions
# --------------------------
def get_routing_profile(vehicle_type):
    vehicle_type = (vehicle_type or "").lower()
    if "dau" in vehicle_type or "heavy" in vehicle_type or "truck" in vehicle_type:
        return "driving-hgv"
    if "tai" in vehicle_type or "van" in vehicle_type:
        return "driving-hgv"
    return "driving-hgv"


def get_route_coords(start_lng, start_lat, end_lng, end_lat, profile="driving-hgv"):
    try:
        if not ORS_API_KEY:
            print("Warning: ORS_API_KEY not set, using straight line")
            return {
                "coordinates": [[start_lng, start_lat], [end_lng, end_lat]],
                "distance": get_distance_meters(start_lat, start_lng, end_lat, end_lng) / 1000,
                "duration": None
            }

        url = f"{ORS_BASE_URL}/{profile}"
        params = {
            "api_key": ORS_API_KEY,
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

# --------------------------
# TTAS & Vehicle Data Functions
# --------------------------
class LiveVehicleFetchError(Exception):
    pass


def create_fleet_session():
    session = requests.Session()
    session.headers.update(TTAS_HEADERS)
    return session


def get_session_cookies():
    from main import get_session_cookies as _get_session_cookies
    return _get_session_cookies()


def ensure_session():
    global fleet_session
    if not fleet_session.cookies.get_dict():
        cookies = get_session_cookies()
        if not cookies:
            raise LiveVehicleFetchError("TTAS login failed - no cookies")
        fleet_session.cookies.update(cookies)
    return fleet_session


def refresh_session():
    global fleet_session
    cookies = get_session_cookies()
    if not cookies:
        raise LiveVehicleFetchError("TTAS login failed - no cookies")
    fleet_session = create_fleet_session()
    fleet_session.cookies.update(cookies)
    return fleet_session


def load_last_json_document(content):
    decoder = json.JSONDecoder()
    index = 0
    last_document = None
    length = len(content)
    while index < length:
        while index < length and content[index].isspace():
            index += 1
        if index >= length:
            break
        try:
            document, next_index = decoder.raw_decode(content, index)
        except json.JSONDecodeError:
            break
        last_document = document
        index = next_index
    return last_document


def load_sample_data():
    sample_path = os.path.join(BASE_DIR, "log.json")
    if not os.path.exists(sample_path):
        return []
    try:
        with open(sample_path, encoding="utf-8") as f:
            content = f.read().strip()
    except Exception as e:
        print(f"Error reading sample: {e}")
        return []
    if not content:
        return []
    try:
        doc = json.loads(content)
    except json.JSONDecodeError:
        doc = load_last_json_document(content)
    return doc.get("d", {}).get("DevList", []) or []


def fetch_live_vehicle_data():
    last_error = None
    for attempt in range(MAX_LIVE_FETCH_ATTEMPTS):
        try:
            session = refresh_session() if attempt else ensure_session()
            response = session.post(TTAS_TRACKING_API, json=TTAS_PAYLOAD, timeout=15, allow_redirects=False)

            if response.status_code in (301, 302, 401, 403):
                raise LiveVehicleFetchError(f"TTAS HTTP {response.status_code}")

            response.raise_for_status()

            if "ttas_login" in response.text.lower():
                raise LiveVehicleFetchError("TTAS returned login page")

            data = response.json()
            raw_vehicles = data.get("d", {}).get("DevList", [])
            if not isinstance(raw_vehicles, list):
                raise LiveVehicleFetchError("TTAS response invalid")
            return raw_vehicles
        except Exception as e:
            last_error = e
            fleet_session.cookies.clear()
            time.sleep(0.5)
    raise LiveVehicleFetchError(f"{type(last_error).__name__}: {last_error}")


def fetch_vehicle_data():
    try:
        return fetch_live_vehicle_data(), "live", None
    except Exception as e:
        print(f"Live fetch failed: {type(e).__name__}: {e}")
        return load_sample_data(), "sample", str(e)


def normalize_vehicle(raw):
    speed = clean_text(raw.get("speed", ""))
    ad3 = clean_text(raw.get("ad3", ""))
    status = clean_text(raw.get("status", ""))
    
    vehicle_status = "unknown"
    if speed.startswith("Chạy"):
        vehicle_status = "running"
    elif speed.startswith("Dừng"):
        vehicle_status = "stopped_engine_on" if ad3 == "Nổ" else "stopped_engine_off"

    license_plate = (
        clean_text(raw.get("biensoxe", ""))
        or clean_text(raw.get("plate", ""))
        or clean_text(raw.get("license_plate", ""))
        or clean_text(raw.get("car_number", ""))
        or clean_text(raw.get("vehicle_number", ""))
        or clean_text(raw.get("devicename", ""))
    )

    return {
        "id": raw.get("id", raw.get("devimei", "")),
        "device_name": license_plate,
        "driver_name": clean_text(raw.get("driver") or "Unknown"),
        "latitude": safe_float(raw.get("latitude")),
        "longitude": safe_float(raw.get("longitude")),
        "speed_status": speed,
        "last_update": clean_text(raw.get("trktime", raw.get("time", ""))),
        "car_type": clean_text(raw.get("car_type", raw.get("tenloaihinh", ""))),
        "position": clean_text(raw.get("position", "")),
        "status": status,
        "vehicle_type": clean_text(raw.get("tenloaihinh", "")),
        "tracking_url": clean_text(raw.get("link", "")),
        "engine_status": ad3,
        "vehicle_status": vehicle_status,
    }

# --------------------------
# Route Refresh Functions
# --------------------------
def do_refresh_route_data():
    _call_start = time.time()
    try:
        raw_vehicles, _, _ = fetch_vehicle_data()
        vehicles = [normalize_vehicle(v) for v in raw_vehicles]

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Process active trips: determine phase from GPS position
        try:
            c.execute('''
                SELECT * FROM vehicle_trips WHERE status = 'active' ORDER BY queue_order
            ''')
            active_trips = [dict(row) for row in c.fetchall()]
            
            for active_trip in active_trips:
                try:
                    vehicle_id = active_trip['vehicle_id']
                    current_vehicle = next((v for v in vehicles if v['id'] == vehicle_id), None)
                    if not current_vehicle:
                        continue
                        
                    current_lat = current_vehicle['latitude']
                    current_lng = current_vehicle['longitude']
                    pickup_lat = active_trip['pickup_lat']
                    pickup_lng = active_trip['pickup_lng']
                    pickup_name = active_trip['pickup_name']
                    dest_lat = active_trip['destination_lat']
                    dest_lng = active_trip['destination_lng']
                    dest_name = active_trip['destination_name']
                    trip_id = active_trip['id']
                    driver_name = current_vehicle.get('driver_name', '')
                    
                    # Parse waypoints for multi-stop support
                    waypoints_raw = active_trip.get('waypoints')
                    waypoints = []
                    if waypoints_raw:
                        try:
                            waypoints = json.loads(waypoints_raw)
                        except:
                            waypoints = []
                    
                    try:
                        db_phase = int(active_trip.get('phase', 1) or 1)
                    except:
                        db_phase = 1
                    
                    has_pickup = bool(pickup_name and pickup_lat and pickup_lng)
                    has_destination = bool(dest_name and dest_lat and dest_lng)
                    
                    # Calculate number of total stops: pickup + waypoints + destination
                    total_stops = 0
                    if has_pickup:
                        total_stops += 1
                    total_stops += len(waypoints)
                    if has_destination:
                        total_stops += 1
                    
                    # Map phase to target coordinates
                    def get_target_for_phase(p):
                        idx = p - 1  # 0-indexed
                        if has_pickup:
                            if idx == 0:
                                return pickup_lat, pickup_lng, pickup_name, 'pickup'
                            idx -= 1
                        if idx < len(waypoints):
                            wp = waypoints[idx]
                            return wp['lat'], wp['lng'], wp['name'], 'waypoint'
                        if has_destination:
                            return dest_lat, dest_lng, dest_name, 'destination'
                        return None, None, None, None
                    
                    # Update driver_name on trip
                    if driver_name and driver_name != active_trip.get('driver_name', ''):
                        c.execute('UPDATE vehicle_trips SET driver_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (driver_name, trip_id))
                    
                    # Begin transaction for geofence detection
                    conn.execute('BEGIN')
                    try:
                        # Check geofence for current target
                        target_lat, target_lng, target_name, target_type = get_target_for_phase(db_phase)
                        
                        if target_name and target_lat and target_lng:
                            target_location = KNOWN_LOCATIONS.get(target_name)
                            if target_location and is_point_in_location(current_lat, current_lng, target_location):
                                # Arrived at current phase target
                                next_phase = db_phase + 1
                                
                                # Log geofence event
                                c.execute('''
                                    INSERT INTO geofence_events (vehicle_id, vehicle_name, trip_id, event_type, location_name, lat, lng, phase)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                ''', (vehicle_id, current_vehicle.get('device_name', ''), trip_id, 'arrive', target_name, current_lat, current_lng, db_phase))
                                
                                if next_phase > total_stops:
                                    # All stops completed, finish trip
                                    c.execute('''
                                        UPDATE vehicle_trips 
                                        SET status = 'completed', phase = NULL, completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                                        WHERE id = ?
                                    ''', (trip_id,))
                                    print(f"Vehicle {vehicle_id} arrived at final stop '{target_name}', completing trip {trip_id}")
                                    
                                    # Activate next queued trip if any
                                    c.execute('''
                                        SELECT * FROM vehicle_trips 
                                        WHERE vehicle_id = ? AND status = 'queued' 
                                        ORDER BY queue_order LIMIT 1
                                    ''', (vehicle_id,))
                                    next_trip = c.fetchone()
                                    if next_trip:
                                        c.execute('''
                                            UPDATE vehicle_trips SET status = 'active', phase = 1 WHERE id = ?
                                        ''', (next_trip['id'],))
                                        print(f"Activating next trip for vehicle {vehicle_id}")
                                    
                                    conn.commit()
                                    continue
                                else:
                                    # Advance to next phase
                                    c.execute('''
                                        UPDATE vehicle_trips SET phase = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
                                    ''', (next_phase, trip_id))
                                    print(f"Vehicle {vehicle_id} arrived at '{target_name}' (phase {db_phase}), advancing to phase {next_phase}")
                                
                                conn.commit()
                    except Exception:
                        conn.rollback()
                        raise
                
                except Exception as e:
                    print(f"Error processing active trip {active_trip.get('id', 'unknown')}: {e}")
                    import traceback
                    traceback.print_exc()
        except Exception as e:
            print(f"Error checking active trips: {e}")
            import traceback
            traceback.print_exc()

        # Now refresh all active and queued trips
        new_route_data = {}
        try:
            c.execute('''
                SELECT * FROM vehicle_trips WHERE status IN ('active', 'queued') ORDER BY vehicle_id, queue_order
            ''')
            trips = [dict(row) for row in c.fetchall()]

            for trip in trips:
                try:
                    vehicle_id = trip['vehicle_id']
                    dest_lat = trip['destination_lat']
                    dest_lng = trip['destination_lng']
                    dest_name = trip['destination_name']
                    pickup_lat = trip['pickup_lat']
                    pickup_lng = trip['pickup_lng']
                    pickup_name = trip['pickup_name']
                    veh_name = trip['vehicle_name']
                    veh_type = trip['vehicle_type']
                    customer_name = trip['customer_name']
                    status = trip['status']
                    queue_order = trip['queue_order']
                    trip_id = trip['id']
                    phase = int(trip['phase']) if trip.get('phase') is not None else None
                    driver_name = trip.get('driver_name', '')
                    created_at = trip.get('created_at', '')

                    if not dest_lat or not dest_lng or dest_lat == 0 or dest_lng == 0:
                        continue

                    current_vehicle = next((v for v in vehicles if v['id'] == vehicle_id), None)
                    if not current_vehicle:
                        continue

                    current_lat = current_vehicle['latitude']
                    current_lng = current_vehicle['longitude']
                    driver_name = driver_name or current_vehicle.get('driver_name', '')
                    speed_str = current_vehicle.get('speed_status', '')
                    current_speed = 0
                    import re
                    speed_match = re.search(r'(\d+(?:\.\d+)?)', speed_str)
                    if speed_match:
                        try:
                            current_speed = float(speed_match.group(1))
                        except:
                            pass

                    profile = get_routing_profile(veh_type)
                    
                    eta_seconds = 0
                    distance_km = 0
                    route_coords = []
                    
                    # Parse waypoints
                    waypoints_raw = trip.get('waypoints')
                    waypoints = []
                    if waypoints_raw:
                        try:
                            waypoints = json.loads(waypoints_raw)
                        except:
                            waypoints = []
                    
                    def get_target_for_phase_route(p):
                        idx = p - 1
                        if pickup_lat and pickup_lng and pickup_name:
                            if idx == 0:
                                return pickup_lat, pickup_lng, pickup_name
                            idx -= 1
                        if idx < len(waypoints):
                            return waypoints[idx]['lat'], waypoints[idx]['lng'], waypoints[idx]['name']
                        return dest_lat, dest_lng, dest_name
                    
                    if status == 'active':
                        tlat, tlng, tname = get_target_for_phase_route(phase or 1)
                        route = get_route_coords(current_lng, current_lat, tlng, tlat, profile)
                        route_coords = route['coordinates']
                        eta_seconds = route['duration'] if route['duration'] else 0
                        distance_km = route['distance']
                    elif status == 'queued':
                        # Route preview: route from current position to pickup (or destination)
                        if pickup_lat and pickup_lng:
                            route = get_route_coords(current_lng, current_lat, pickup_lng, pickup_lat, profile)
                        else:
                            route = get_route_coords(current_lng, current_lat, dest_lng, dest_lat, profile)
                        route_coords = route['coordinates']
                        distance_km = route['distance']

                    leaflet_coords = [[coord[1], coord[0]] for coord in route_coords]
                    
                    # Update only active trip's last known eta
                    if status == 'active':
                        c.execute('''
                            UPDATE vehicle_trips
                            SET last_known_eta = ?, last_known_distance = ?, driver_name = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        ''', (eta_seconds, distance_km, driver_name, trip_id))
                        conn.commit()
                    
                    # Add all trips (active and queued) to route data
                    new_route_data[f"{vehicle_id}-{trip_id}"] = {
                        'trip_id': trip_id,
                        'vehicle_id': vehicle_id,
                        'vehicle_name': veh_name,
                        'driver_name': driver_name,
                        'current_lat': current_lat,
                        'current_lng': current_lng,
                        'destination_lat': dest_lat,
                        'destination_lng': dest_lng,
                        'destination_name': dest_name,
                        'pickup_lat': pickup_lat,
                        'pickup_lng': pickup_lng,
                        'pickup_name': pickup_name,
                        'customer_name': customer_name,
                        'route_coords': leaflet_coords,
                        'distance_remaining_km': distance_km,
                        'eta_seconds': eta_seconds if status == 'active' else None,
                        'current_speed': current_speed,
                        'status': status,
                        'queue_order': queue_order,
                        'phase': phase,
                        'created_at': created_at,
                        'waypoints': waypoints
                    }
                except Exception as e:
                    print(f"Error processing trip {trip.get('id', 'unknown')}: {e}")
                    import traceback
                    traceback.print_exc()
        except Exception as e:
            print(f"Error fetching trips: {e}")

        conn.close()

        with cache_lock:
            global route_data_cache, _last_manual_update
            if _call_start >= _last_manual_update:
                route_data_cache = new_route_data
            else:
                pass  # stale data from bg thread, skip
        return True
    except Exception as e:
        print(f"Error refreshing routes: {e}")
        import traceback
        traceback.print_exc()
        return False


def refresh_route_data():
    while True:
        do_refresh_route_data()
        time.sleep(ROUTE_REFRESH_INTERVAL)


def start_route_refresh_thread():
    thread = threading.Thread(target=refresh_route_data, daemon=True)
    thread.start()

# --------------------------
# Initialize & Setup Flask
# --------------------------
app = Flask(__name__, static_folder='static', template_folder='templates')
KNOWN_LOCATIONS = load_known_locations()
fleet_session = create_fleet_session()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/vehicles")
def api_vehicles():
    raw_vehicles, source, error = fetch_vehicle_data()
    cleaned = [normalize_vehicle(item) for item in raw_vehicles]
    return jsonify({
        "vehicles": cleaned,
        "source": source,
        "source_url": TTAS_TRACKING_PAGE_URL,
        "error": error,
    })


@app.route("/api/known-locations")
def api_known_locations():
    return jsonify(KNOWN_LOCATIONS)


@app.route("/api/save-location", methods=["POST"])
def api_save_location():
    try:
        data = request.json or {}
        parsed, error = parse_location_payload(data)
        if error:
            return jsonify({"success": False, "message": error}), 400
        
        name = parsed["name"]
        new_polygon = parsed["corners"]
        
        manual_locs = read_manual_locations()
        
        if name in KNOWN_LOCATIONS:
            # Add to existing location
            existing = KNOWN_LOCATIONS[name]
            polygons = existing.get("polygons", [])
            polygons.append(new_polygon)
            
            # Update both KNOWN_LOCATIONS and manual_locs
            updated_loc = {"polygons": polygons, "type": "multi_polygon"}
            KNOWN_LOCATIONS[name] = updated_loc
            manual_locs[name] = updated_loc
        else:
            # Create new location
            new_loc = {"polygons": [new_polygon], "type": "multi_polygon"}
            KNOWN_LOCATIONS[name] = new_loc
            manual_locs[name] = new_loc
        
        write_manual_locations(manual_locs)
        
        return jsonify({"success": True, "message": f"Location '{name}' saved"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/update-location", methods=["POST"])
def api_update_location():
    try:
        data = request.json or {}
        original_name = (data.get("original_name") or "").strip()
        parsed, error = parse_location_payload(data)
        if error:
            return jsonify({"success": False, "message": error}), 400
        if not original_name:
            return jsonify({"success": False, "message": "Original name required"}), 400
        
        manual_locs = read_manual_locations()
        if original_name not in KNOWN_LOCATIONS and original_name not in manual_locs:
            return jsonify({"success": False, "message": "Not found"}), 404
        
        name = parsed["name"]
        new_polygon = parsed["corners"]
        
        # Handle renaming if needed
        if name != original_name:
            if name in KNOWN_LOCATIONS or name in manual_locs:
                return jsonify({"success": False, "message": "Name exists"}), 409
            
            # Move location to new name
            if original_name in manual_locs:
                manual_locs[name] = manual_locs.pop(original_name)
            if original_name in KNOWN_LOCATIONS:
                KNOWN_LOCATIONS[name] = KNOWN_LOCATIONS.pop(original_name)
        
        # Update the polygons (replace all polygons with new one for edit mode)
        updated_loc = {"polygons": [new_polygon], "type": "multi_polygon"}
        manual_locs[name] = updated_loc
        KNOWN_LOCATIONS[name] = updated_loc
        write_manual_locations(manual_locs)
        
        return jsonify({"success": True, "name": name, "location": updated_loc})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/delete-location", methods=["POST"])
def api_delete_location():
    try:
        data = request.json or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"success": False, "message": "Name required"}), 400
        
        manual_locs = read_manual_locations()
        if name not in KNOWN_LOCATIONS and name not in manual_locs:
            return jsonify({"success": False, "message": "Not found"}), 404
        
        KNOWN_LOCATIONS.pop(name, None)
        manual_locs.pop(name, None)
        write_manual_locations(manual_locs)
        
        return jsonify({"success": True, "message": f"Location '{name}' deleted"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/clear-all-locations", methods=["POST"])
def api_clear_all_locations():
    try:
        global KNOWN_LOCATIONS
        KNOWN_LOCATIONS = {}
        write_manual_locations({})
        
        return jsonify({"success": True, "message": "All locations cleared"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/manage-trips")
def manage_trips():
    return render_template("manage-trips.html")


@app.route("/locations")
def locations():
    return render_template("locations.html")


@app.route("/trip-history")
def trip_history():
    return render_template("trip-history.html")


@app.route("/api/set-destination", methods=["POST"])
def set_destination():
    """Set or update a vehicle's destination."""
    try:
        data = request.json or {}
        vehicle_id = (data.get("vehicle_id") or "").strip()
        vehicle_name = (data.get("vehicle_name") or "").strip()
        destination_lat = data.get("destination_lat")
        destination_lng = data.get("destination_lng")
        destination_name = (data.get("destination_name") or "").strip()
        pickup_lat = data.get("pickup_lat")
        pickup_lng = data.get("pickup_lng")
        pickup_name = (data.get("pickup_name") or "").strip()
        customer_name = (data.get("customer_name") or "").strip()
        vehicle_type = (data.get("vehicle_type") or "").strip()

        if not vehicle_id:
            return jsonify({"success": False, "message": "ID required"}), 400

        if destination_lat is None or destination_lng is None:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('DELETE FROM vehicle_trips WHERE vehicle_id = ?', (vehicle_id,))
            conn.commit()
            conn.close()
            return jsonify({"success": True, "message": "All destinations cleared"})

        # Validate location names against known locations
        if destination_name and destination_name not in KNOWN_LOCATIONS:
            # Try fuzzy match
            matched = None
            dest_lower = destination_name.lower().strip()
            for known_name in KNOWN_LOCATIONS:
                if dest_lower == known_name.lower().strip():
                    matched = known_name
                    break
            if matched:
                destination_name = matched
            else:
                print(f"Warning: destination_name '{destination_name}' not found in known locations")
        if pickup_name and pickup_name not in KNOWN_LOCATIONS:
            matched = None
            pickup_lower = pickup_name.lower().strip()
            for known_name in KNOWN_LOCATIONS:
                if pickup_lower == known_name.lower().strip():
                    matched = known_name
                    break
            if matched:
                pickup_name = matched
            else:
                print(f"Warning: pickup_name '{pickup_name}' not found in known locations")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Calculate next queue order for this vehicle
        c.execute('''
            SELECT COALESCE(MAX(queue_order), 0) + 1 FROM vehicle_trips WHERE vehicle_id = ?
        ''', (vehicle_id,))
        next_queue_order = c.fetchone()[0]
        
        # Check if vehicle has active trip, if not set this one as active
        c.execute('''
            SELECT COUNT(*) FROM vehicle_trips WHERE vehicle_id = ? AND status = 'active'
        ''', (vehicle_id,))
        active_count = c.fetchone()[0]
        status = 'active' if active_count == 0 else 'queued'
        
        # Fetch driver name from vehicle data
        driver_name = ''
        try:
            raw_vehicles, _, _ = fetch_vehicle_data()
            for v in raw_vehicles:
                vid = str(v.get("id", v.get("devimei", "")))
                if vid == vehicle_id:
                    driver_name = clean_text(v.get("driver") or "")
                    break
        except:
            pass
        
        c.execute('''
            INSERT INTO vehicle_trips
            (vehicle_id, vehicle_name, driver_name, destination_lat, destination_lng, destination_name, 
             pickup_lat, pickup_lng, pickup_name, customer_name, last_known_eta, last_known_distance, vehicle_type, status, queue_order, phase)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?)
        ''', (vehicle_id, vehicle_name, driver_name, destination_lat, destination_lng, destination_name, 
              pickup_lat, pickup_lng, pickup_name, customer_name, vehicle_type, status, next_queue_order, 1 if status == 'active' else None))
        conn.commit()
        conn.close()
        
        global _last_manual_update
        _last_manual_update = time.time()
        # Refresh routes immediately to update state
        do_refresh_route_data()
        
        return jsonify({"success": True, "message": "Trip added successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/route-data")
def get_route_data():
    with cache_lock:
        return jsonify(list(route_data_cache.values()))


@app.route("/api/trips/history")
@app.route("/api/trip-history", methods=["GET"])
def get_trip_history():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('''
            SELECT * FROM vehicle_trips 
            ORDER BY COALESCE(completed_at, created_at) DESC
        ''')
        history = []
        for row in c.fetchall():
            history.append(dict(row))
        conn.close()
        return jsonify(history)
    except Exception as e:
        print(f"Error getting trip history: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route("/api/manual-locations")
def api_manual_locations():
    return jsonify(read_manual_locations())


@app.route("/api/clear-trip", methods=["POST"])
def clear_trip():
    try:
        data = request.json or {}
        trip_id = data.get("trip_id")
        vehicle_id = data.get("vehicle_id")
        
        if not trip_id or not vehicle_id:
            return jsonify({"success": False, "message": "Missing trip_id or vehicle_id"}), 400
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM vehicle_trips WHERE id = ? AND vehicle_id = ?", (trip_id, vehicle_id))
        conn.commit()
        conn.close()
        
        do_refresh_route_data()
        
        return jsonify({"success": True, "message": "Trip removed successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500



@app.route("/api/update-trip", methods=["POST"])
def update_trip():
    try:
        data = request.json or {}
        trip_id = data.get("trip_id")
        
        if not trip_id:
            return jsonify({"success": False, "message": "Missing trip_id"}), 400
        
        # Update fields
        updates = []
        params = []
        
        if "vehicle_id" in data:
            updates.append("vehicle_id = ?")
            params.append(data["vehicle_id"])
        if "vehicle_name" in data:
            updates.append("vehicle_name = ?")
            params.append(data["vehicle_name"])
        if "destination_lat" in data:
            updates.append("destination_lat = ?")
            params.append(data["destination_lat"])
        if "destination_lng" in data:
            updates.append("destination_lng = ?")
            params.append(data["destination_lng"])
        if "destination_name" in data:
            updates.append("destination_name = ?")
            params.append(data["destination_name"])
        if "pickup_lat" in data:
            updates.append("pickup_lat = ?")
            params.append(data["pickup_lat"])
        if "pickup_lng" in data:
            updates.append("pickup_lng = ?")
            params.append(data["pickup_lng"])
        if "pickup_name" in data:
            updates.append("pickup_name = ?")
            params.append(data["pickup_name"])
        if "customer_name" in data:
            updates.append("customer_name = ?")
            params.append(data["customer_name"])
        if "vehicle_type" in data:
            updates.append("vehicle_type = ?")
            params.append(data["vehicle_type"])
        if "status" in data:
            updates.append("status = ?")
            params.append(data["status"])
            if data["status"] == "completed":
                updates.append("completed_at = CURRENT_TIMESTAMP")
            else:
                updates.append("completed_at = NULL")
        if "queue_order" in data:
            updates.append("queue_order = ?")
            params.append(data["queue_order"])
        if "phase" in data:
            updates.append("phase = ?")
            params.append(data["phase"])
        if "driver_name" in data:
            updates.append("driver_name = ?")
            params.append(data["driver_name"])
        if "waypoints" in data:
            updates.append("waypoints = ?")
            params.append(json.dumps(data["waypoints"]))
        
        if not updates:
            return jsonify({"success": False, "message": "No fields to update"}), 400
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(trip_id)
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(f"UPDATE vehicle_trips SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        conn.close()
        
        global _last_manual_update
        _last_manual_update = time.time()
        do_refresh_route_data()
        
        return jsonify({"success": True, "message": "Trip updated successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/clear-all-trips", methods=["POST"])
def clear_all_trips():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM vehicle_trips")
        conn.commit()
        conn.close()
        
        do_refresh_route_data()
        
        return jsonify({"success": True, "message": "All trips cleared successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/refresh-routes", methods=["POST"])
def api_refresh_routes():
    success = do_refresh_route_data()
    if success:
        return jsonify({"success": True, "route_data": list(route_data_cache.values())})
    return jsonify({"success": False, "message": "Failed to refresh"}), 500

@app.route("/api/advance-trip", methods=["POST"])
def api_advance_trip():
    """Force advance trip phase or complete trip."""
    try:
        data = request.json or {}
        trip_id = data.get("trip_id")
        action = data.get("action", "advance")  # 'advance' or 'complete'
        
        if not trip_id:
            return jsonify({"success": False, "message": "Missing trip_id"}), 400
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute('SELECT * FROM vehicle_trips WHERE id = ?', (trip_id,))
        trip = c.fetchone()
        if not trip:
            conn.close()
            return jsonify({"success": False, "message": "Trip not found"}), 404
        
        trip = dict(trip)
        
        if action == 'complete':
            c.execute('''
                UPDATE vehicle_trips 
                SET status = 'completed', phase = NULL, completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (trip_id,))
            
            # Activate next queued trip
            c.execute('''
                SELECT * FROM vehicle_trips 
                WHERE vehicle_id = ? AND status = 'queued' 
                ORDER BY queue_order LIMIT 1
            ''', (trip['vehicle_id'],))
            next_trip = c.fetchone()
            if next_trip:
                c.execute('''
                    UPDATE vehicle_trips SET status = 'active', phase = 1 WHERE id = ?
                ''', (next_trip['id'],))
            
            conn.commit()
            conn.close()
            
            _last_manual_update = time.time()
            do_refresh_route_data()
            
            return jsonify({"success": True, "message": "Trip force-completed"})
        
        else:
            # Advance: increment phase
            db_phase = int(trip.get('phase', 1) or 1)
            
            # Check if there's a next stop
            has_pickup = bool(trip['pickup_name'] and trip['pickup_lat'] and trip['pickup_lng'])
            has_destination = bool(trip['destination_name'] and trip['destination_lat'] and trip['destination_lng'])
            
            waypoints = []
            if trip.get('waypoints'):
                try:
                    waypoints = json.loads(trip['waypoints'])
                except:
                    waypoints = []
            
            total_stops = 0
            if has_pickup: total_stops += 1
            total_stops += len(waypoints)
            if has_destination: total_stops += 1
            
            next_phase = db_phase + 1
            
            if next_phase > total_stops:
                # Auto-complete
                c.execute('''
                    UPDATE vehicle_trips 
                    SET status = 'completed', phase = NULL, completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (trip_id,))
                
                c.execute('''
                    SELECT * FROM vehicle_trips 
                    WHERE vehicle_id = ? AND status = 'queued' 
                    ORDER BY queue_order LIMIT 1
                ''', (trip['vehicle_id'],))
                next_trip = c.fetchone()
                if next_trip:
                    c.execute('''
                        UPDATE vehicle_trips SET status = 'active', phase = 1 WHERE id = ?
                    ''', (next_trip['id'],))
                
                conn.commit()
                conn.close()
                
                _last_manual_update = time.time()
                do_refresh_route_data()
                
                return jsonify({"success": True, "message": "Trip force-completed (no more stops)"})
            else:
                c.execute('''
                    UPDATE vehicle_trips SET phase = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
                ''', (next_phase, trip_id))
                conn.commit()
                conn.close()
                
                _last_manual_update = time.time()
                do_refresh_route_data()
                
                return jsonify({"success": True, "message": f"Trip advanced to phase {next_phase}"})
    
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/cancel-trip", methods=["POST"])
def api_cancel_trip():
    """Cancel an active or queued trip."""
    try:
        data = request.json or {}
        trip_id = data.get("trip_id")
        reason = (data.get("reason") or "Manual cancellation").strip()
        
        if not trip_id:
            return jsonify({"success": False, "message": "Missing trip_id"}), 400
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Get current status before updating
        c.execute('SELECT vehicle_id, status FROM vehicle_trips WHERE id = ?', (trip_id,))
        trip_before = c.fetchone()
        if not trip_before:
            conn.close()
            return jsonify({"success": False, "message": "Trip not found"}), 404
        
        was_active = trip_before['status'] == 'active'
        vehicle_id = trip_before['vehicle_id']
        
        c.execute('''
            UPDATE vehicle_trips 
            SET status = 'canceled', phase = NULL, canceled_at = CURRENT_TIMESTAMP, cancel_reason = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (reason, trip_id))
        
        # If the trip was active, activate the next queued trip
        if was_active:
            c.execute('''
                SELECT * FROM vehicle_trips 
                WHERE vehicle_id = ? AND status = 'queued' 
                ORDER BY queue_order LIMIT 1
            ''', (vehicle_id,))
            next_trip = c.fetchone()
            if next_trip:
                c.execute('''
                    UPDATE vehicle_trips SET status = 'active', phase = 1 WHERE id = ?
                ''', (next_trip['id'],))
        
        conn.commit()
        conn.close()
        
        _last_manual_update = time.time()
        do_refresh_route_data()
        
        return jsonify({"success": True, "message": "Trip canceled"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/geofence-events", methods=["GET"])
def api_geofence_events():
    """Get geofence event log, optionally filtered by vehicle_id."""
    try:
        vehicle_id = request.args.get("vehicle_id", "")
        limit = int(request.args.get("limit", 100))
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        if vehicle_id:
            c.execute('''
                SELECT * FROM geofence_events 
                WHERE vehicle_id = ? 
                ORDER BY created_at DESC LIMIT ?
            ''', (vehicle_id, limit))
        else:
            c.execute('''
                SELECT * FROM geofence_events 
                ORDER BY created_at DESC LIMIT ?
            ''', (limit,))
        
        events = [dict(row) for row in c.fetchall()]
        conn.close()
        
        return jsonify({"success": True, "events": events})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/geocode', methods=['GET'])
def api_geocode():
    query = request.args.get('q', '')
    if not query:
        return jsonify({'success': False, 'error': 'No query provided'}), 400
    
    try:
        import requests
        # Use Nominatim (OpenStreetMap) for free geocoding
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': query,
            'format': 'json',
            'addressdetails': 1,
            'limit': 5
        }
        headers = {
            'User-Agent': 'ChiTuyen-Fleet-Management/1.0'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        results = []
        for place in response.json():
            results.append({
                'name': place.get('display_name', ''),
                'lat': float(place.get('lat')),
                'lng': float(place.get('lon'))
            })
        
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        print(f"Geocoding error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==============================================================
# OIL CHANGE MAINTENANCE TRACKER
# ==============================================================
import re as _re
from datetime import date as _date, timedelta as _timedelta, datetime as _datetime
from bs4 import BeautifulSoup as _BeautifulSoup
from main import fetch_report as _playwright_fetch_report

TTAS_REPORT_URL = "https://dinhvihopquy.vn/baocao/ttas_baocao_tonghop_theongay.aspx"


def _fetch_ttas_report_page(session, plate: str, from_date_ddmmyyyy: str, to_date_ddmmyyyy: str) -> str:
    """Fetch the TTAS report page for a specific vehicle and date range."""
    try:
        # Step 1: GET to retrieve __VIEWSTATE and find select option
        get_resp = session.get(TTAS_REPORT_URL, timeout=20)
        get_resp.raise_for_status()
        soup = _BeautifulSoup(get_resp.text, "html.parser")

        def _hidden(name):
            tag = soup.find("input", {"name": name})
            return tag["value"] if tag and tag.get("value") else ""

        viewstate           = _hidden("__VIEWSTATE")
        viewstate_gen       = _hidden("__VIEWSTATEGENERATOR")
        event_validation    = _hidden("__EVENTVALIDATION")

        # Find select element for vehicle
        drp_input = soup.find("select", {"id": lambda x: x and "drpchonxe" in x.lower()})
        drp_name = drp_input["name"] if drp_input else "ctl00$ttasbaocao$drpchonxe"
        
        # Mapped vehicle option value
        drp_value = ""
        if drp_input:
            import re
            clean_plate = re.sub(r'[^a-zA-Z0-9]', '', plate).upper()
            for opt in drp_input.find_all("option"):
                opt_text_clean = re.sub(r'[^a-zA-Z0-9]', '', opt.text).upper()
                opt_val_clean = re.sub(r'[^a-zA-Z0-9]', '', opt.get("value", "")).upper()
                if opt_text_clean == clean_plate or opt_val_clean == clean_plate:
                    drp_value = opt.get("value", "")
                    break
            # Fallback if not found
            if not drp_value:
                drp_value = plate
        else:
            drp_value = plate

        # Date input IDs and names
        date_from_input = soup.find("input", {"id": lambda x: x and "txttungay" in x.lower()})
        date_to_input   = soup.find("input", {"id": lambda x: x and "txtdenngay" in x.lower()})
        btn_input       = soup.find("input", {"id": lambda x: x and "btndealscreen" in x.lower()})

        date_from_name = date_from_input["name"] if date_from_input else "ctl00$ttasbaocao$txttungay"
        date_to_name   = date_to_input["name"]   if date_to_input   else "ctl00$ttasbaocao$txtdenngay"
        btn_name       = btn_input["name"]        if btn_input       else "ctl00$ttashtkt$btndealscreen"
        btn_value      = btn_input["value"]       if btn_input       else "Xem BC"

        post_data = {
            "__VIEWSTATE":          viewstate,
            "__VIEWSTATEGENERATOR": viewstate_gen,
            "__EVENTVALIDATION":    event_validation,
            drp_name:               drp_value,
            date_from_name:         from_date_ddmmyyyy,
            date_to_name:           to_date_ddmmyyyy,
            btn_name:               btn_value,
        }
        post_resp = session.post(TTAS_REPORT_URL, data=post_data, timeout=30)
        post_resp.raise_for_status()
        return post_resp.text
    except Exception as e:
        print(f"[OilTracker] TTAS report fetch failed for {plate} ({from_date_ddmmyyyy} to {to_date_ddmmyyyy}): {e}")
        return ""


def _parse_ttas_report_html(html: str, target_plate: str) -> list:
    """Parse tData tbody from the TTAS daily summary report.
    Returns: [{"license_plate": str, "log_date": str, "daily_km": int}, ...]"""
    if not html:
        return []
    try:
        import re
        soup = _BeautifulSoup(html, "html.parser")
        tbody = soup.find(id="tData")
        if not tbody:
            return []

        rows = tbody.find_all("tr")
        results = []
        
        # Clean target plate for matching
        clean_target = re.sub(r'[^a-zA-Z0-9]', '', target_plate).upper()
        # Default to True in case there's no header row
        current_match = True

        for row in rows:
            tds = row.find_all("td")
            if not tds:
                continue

            # Plate row: single <td colspan="10"> containing "Biển số xe"
            if len(tds) == 1 and "Biển số xe" in tds[0].get_text():
                raw = tds[0].get_text(strip=True)
                parsed_plate = raw.split(":")[-1].strip()
                clean_parsed = re.sub(r'[^a-zA-Z0-9]', '', parsed_plate).upper()
                current_match = (clean_parsed == clean_target)
                continue

            # Skip totals row
            first_text = tds[0].get_text(strip=True)
            combined_first = (tds[0].get_text(strip=True) + (tds[1].get_text(strip=True) if len(tds) > 1 else ""))
            if "Tổng cộng" in first_text or "Tổng cộng" in combined_first:
                continue

            # Regular log row
            if current_match and len(tds) >= 4:
                idx_text = tds[0].get_text(strip=True)
                if idx_text.isdigit():
                    date_str = tds[1].get_text(strip=True)
                    km_text = tds[3].get_text(strip=True)
                    
                    try:
                        dt_obj = _datetime.strptime(date_str, "%d/%m/%Y").date()
                        log_date_iso = dt_obj.strftime("%Y-%m-%d")
                        
                        km_match = _re.search(r"(\d+)", km_text)
                        km = int(km_match.group(1)) if km_match else 0
                        
                        results.append({
                            "license_plate": target_plate,
                            "log_date": log_date_iso,
                            "daily_km": km
                        })
                    except Exception as ex:
                        print(f"[OilTracker] Row parsing error: {ex}")
                        pass

        return results
    except Exception as e:
        print(f"[OilTracker] HTML parse error: {e}")
        return []


def _parse_ttas_total_km(table_html: str, plate: str, to_date_str: str) -> list:
    """Parse the full #tData table HTML and return total KM for the target plate.
    Finds the 'Biển số xe: {plate}' header, then the 'Tổng cộng' row for that
    vehicle, and extracts the KM value. Falls back to summing daily rows.
    Returns a single entry with total KM logged on to_date.
    """
    if not table_html:
        print(f"[OilTracker] Empty table HTML for {plate}")
        return []
    try:
        import re
        soup = _BeautifulSoup(f"<table><tbody>{table_html}</tbody></table>", "html.parser")
        tbody = soup.find("tbody")
        if not tbody:
            print(f"[OilTracker] No tbody in table HTML for {plate}")
            return []

        clean_target = re.sub(r'[^a-zA-Z0-9]', '', plate).upper()
        in_target = True  # assume single-vehicle report unless a plate header says otherwise
        total_km = 0

        for row in tbody.find_all("tr"):
            tds = row.find_all("td")
            if not tds:
                continue

            # Plate header row
            if len(tds) == 1 and "Biển số xe" in tds[0].get_text():
                raw = tds[0].get_text(strip=True)
                parsed_plate = raw.split(":")[-1].strip()
                clean_parsed = re.sub(r'[^a-zA-Z0-9]', '', parsed_plate).upper()
                in_target = (clean_parsed == clean_target)
                continue

            if not in_target:
                continue

            # Total row for this vehicle
            first_text = tds[0].get_text(strip=True)
            combined = first_text + (tds[1].get_text(strip=True) if len(tds) > 1 else "")
            if "Tổng cộng" in first_text or "Tổng cộng" in combined:
                for td in tds:
                    text = td.get_text(strip=True).replace(".", "")
                    m = _re.search(r"([\d]+)\s*km", text, _re.IGNORECASE)
                    if m:
                        total_km = int(m.group(1))
                        break
                break  # stop after processing the total row for this vehicle

            # Daily row: sum as fallback
            idx_text = tds[0].get_text(strip=True)
            if idx_text.isdigit() and len(tds) >= 4:
                km_text = tds[3].get_text(strip=True)
                km_match = _re.search(r"(\d+)", km_text.replace(".", ""))
                if km_match:
                    total_km += int(km_match.group(1))

        print(f"[OilTracker] Parsed {plate}: total_km={total_km}, in_target={in_target}")
        if total_km == 0:
            return []
        try:
            end_dt = _datetime.strptime(to_date_str, "%d/%m/%Y").date()
            log_date_iso = end_dt.strftime("%Y-%m-%d")
        except Exception:
            log_date_iso = _date.today().strftime("%Y-%m-%d")
        return [{"license_plate": plate, "log_date": log_date_iso, "daily_km": total_km}]
    except Exception as e:
        print(f"[OilTracker] Table total parse error: {e}")
        return []


def _store_km_log(entries: list):
    """Upsert parsed KM entries into oil_km_log using INSERT OR REPLACE.
    
    Each entry is a cumulative total from the oil change date to log_date.
    Delete any older entries for the same vehicle so they don't double-count.
    """
    if not entries:
        return
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        c = conn.cursor()
        for entry in entries:
            # Delete older cumulative entries for this vehicle (they are superseded)
            c.execute(
                "DELETE FROM oil_km_log WHERE license_plate = ? AND log_date < ?",
                (entry["license_plate"], entry["log_date"])
            )
            c.execute(
                "INSERT OR REPLACE INTO oil_km_log (license_plate, log_date, km) VALUES (?, ?, ?)",
                (entry["license_plate"], entry["log_date"], entry["daily_km"])
            )
        conn.commit()
        conn.close()
        print(f"[OilTracker] Stored {len(entries)} entries: {entries[0]['license_plate']} log_date={entries[0]['log_date']} km={entries[0]['daily_km']}")
    except Exception as e:
        print(f"[OilTracker] DB write error: {e}")
        raise



def _compute_oil_metrics(vehicle_row: dict, km_log_rows: list) -> dict:
    """Compute derived maintenance metrics for a vehicle."""
    total_km = sum(r["km"] for r in km_log_rows)
    interval = vehicle_row["maintenance_interval"] or 5000
    remaining = interval - total_km
    pct = round((total_km / interval) * 100, 1) if interval else 0
    if pct < 70:
        status = "safe"
    elif pct < 90:
        status = "warning"
    else:
        status = "danger"
    result = {k: v for k, v in vehicle_row.items() if k != "last_oil_change_km"}
    result.update({
        "total_km_since_change": total_km,
        "remaining_km": remaining,
        "progress_pct": pct,
        "maintenance_status": status,
    })
    return result


@app.route("/oil-change")
def oil_change_page():
    return render_template("oil-change.html")


@app.route("/api/oil-maintenance", methods=["GET"])
def api_oil_maintenance_list():
    """Return all vehicles with computed oil change metrics."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM oil_maintenance ORDER BY license_plate")
        vehicles = [dict(row) for row in c.fetchall()]

        results = []
        for v in vehicles:
            c.execute(
                "SELECT km, log_date FROM oil_km_log WHERE license_plate = ? AND log_date >= ? ORDER BY log_date",
                (v["license_plate"], v["last_oil_change_date"])
            )
            km_rows = [dict(r) for r in c.fetchall()]
            results.append(_compute_oil_metrics(v, km_rows))

        conn.close()
        resp = jsonify({"success": True, "data": results})
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return resp
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/oil-maintenance/export")
def api_oil_maintenance_export():
    """Export oil maintenance data as CSV."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM oil_maintenance ORDER BY license_plate")
        vehicles = [dict(row) for row in c.fetchall()]

        rows = []
        for v in vehicles:
            c.execute(
                "SELECT km, log_date FROM oil_km_log WHERE license_plate = ? AND log_date >= ? ORDER BY log_date",
                (v["license_plate"], v["last_oil_change_date"])
            )
            km_rows = [dict(r) for r in c.fetchall()]
            rows.append(_compute_oil_metrics(v, km_rows))

        conn.close()

        import io
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "License Plate", "Last Change Date",
            "Interval (km)", "KM Since Change", "Remaining KM",
            "Progress (%)", "Status"
        ])
        for r in rows:
            writer.writerow([
                r["license_plate"],
                r["last_oil_change_date"],
                r["maintenance_interval"],
                r["total_km_since_change"],
                r["remaining_km"],
                r["progress_pct"],
                r["maintenance_status"]
            ])

        csv_bytes = output.getvalue().encode("utf-8-sig")
        return Response(
            csv_bytes,
            mimetype="text/csv; charset=utf-8-sig",
            headers={"Content-Disposition": "attachment; filename=oil_maintenance_report.csv"}
        )
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/oil-maintenance", methods=["POST"])
def api_oil_maintenance_create():
    """Create a new vehicle oil maintenance record."""
    try:
        data = request.json or {}
        plate    = (data.get("license_plate") or "").strip().upper()
        dt       = (data.get("last_oil_change_date") or "").strip()
        interval = int(data.get("maintenance_interval") or 5000)

        if not plate:
            return jsonify({"success": False, "message": "license_plate is required"}), 400
        if not dt:
            return jsonify({"success": False, "message": "last_oil_change_date is required"}), 400

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT INTO oil_maintenance (license_plate, last_oil_change_date, maintenance_interval) VALUES (?, ?, ?)",
            (plate, dt, interval)
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Vehicle added"})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "message": "Vehicle with that license plate already exists"}), 409
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/oil-maintenance/<plate>", methods=["PUT"])
def api_oil_maintenance_update(plate):
    """Update an existing vehicle oil maintenance record."""
    try:
        data     = request.json or {}
        plate    = plate.strip().upper()
        dt       = (data.get("last_oil_change_date") or "").strip()
        interval = int(data.get("maintenance_interval") or 5000)

        if not dt:
            return jsonify({"success": False, "message": "last_oil_change_date is required"}), 400

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "UPDATE oil_maintenance SET last_oil_change_date=?, maintenance_interval=?, updated_at=CURRENT_TIMESTAMP WHERE license_plate=?",
            (dt, interval, plate)
        )
        if c.rowcount == 0:
            conn.close()
            return jsonify({"success": False, "message": "Vehicle not found"}), 404
        # When oil change date is updated, clear all KM logs (they were computed from old date)
        c.execute("DELETE FROM oil_km_log WHERE license_plate=?", (plate,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Vehicle updated"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/oil-maintenance/<plate>", methods=["DELETE"])
def api_oil_maintenance_delete(plate):
    """Delete a vehicle oil maintenance record and its KM log."""
    try:
        plate = plate.strip().upper()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM oil_maintenance WHERE license_plate=?", (plate,))
        c.execute("DELETE FROM oil_km_log WHERE license_plate=?", (plate,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Vehicle deleted"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/oil-maintenance/<plate>/maintenance", methods=["POST"])
def api_oil_maintenance_mark_done(plate):
    """Mark oil change as done: set last_oil_change_date to today and clear KM logs."""
    try:
        plate = plate.strip().upper()
        today = _date.today().strftime("%Y-%m-%d")
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "UPDATE oil_maintenance SET last_oil_change_date=?, updated_at=CURRENT_TIMESTAMP WHERE license_plate=?",
            (today, plate)
        )
        if c.rowcount == 0:
            conn.close()
            return jsonify({"success": False, "message": "Vehicle not found"}), 404
        # Clear all KM logs since they were computed from the old oil change date
        c.execute("DELETE FROM oil_km_log WHERE license_plate=?", (plate,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"Oil change marked as done for {plate}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/oil-maintenance/fetch-km", methods=["POST"])
def api_oil_maintenance_fetch_km():
    """Scrape the TTAS report for all vehicles from their last oil change date to yesterday."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT license_plate, last_oil_change_date FROM oil_maintenance")
        vehicles = [dict(row) for row in c.fetchall()]
        conn.close()

        if not vehicles:
            return jsonify({"success": True, "message": "No vehicles to update", "vehicles_fetched": 0})

        # Determine start date and yesterday's date
        today = _date.today()
        yesterday = today - _timedelta(days=1)

        # Use the existing fleet session
        try:
            session = ensure_session()
        except Exception:
            try:
                session = refresh_session()
            except Exception as e:
                return jsonify({"success": False, "message": f"TTAS session error: {e}"}), 503

        vehicles_fetched = 0
        total_entries = 0
        errors = []

        total_vehicles = len(vehicles)
        with _oil_fetch_lock:
            _oil_fetch_progress.clear()
            _oil_fetch_progress['total'] = total_vehicles
            _oil_fetch_progress['current'] = 0
            _oil_fetch_progress['plate'] = ''
            _oil_fetch_progress['status'] = 'fetching'
            _oil_fetch_progress['started_at'] = time.time()

        for idx, v in enumerate(vehicles, start=1):
            plate = v["license_plate"]
            with _oil_fetch_lock:
                _oil_fetch_progress['current'] = idx
                _oil_fetch_progress['plate'] = plate
            try:
                start_date = _datetime.strptime(v["last_oil_change_date"], "%Y-%m-%d").date()
                if start_date > yesterday:
                    # Last change date was today or in the future
                    continue

                start_date_str = start_date.strftime("%d/%m/%Y")
                yesterday_str = yesterday.strftime("%d/%m/%Y")

                # Use Playwright-based fetch (handles login + report in one session)
                html = _playwright_fetch_report(plate, start_date_str, yesterday_str)
                entries = _parse_ttas_total_km(html, plate, yesterday_str)
                _store_km_log(entries)

                vehicles_fetched += 1
                total_entries += len(entries)
            except Exception as e:
                errors.append(f"{plate}: {e}")

        with _oil_fetch_lock:
            _oil_fetch_progress['status'] = 'done'

        msg = f"Fetched data for {vehicles_fetched} vehicle(s), {total_entries} KM entry/entries stored."
        if errors:
            msg += f" Errors on {len(errors)} vehicle(s)."

        return jsonify({
            "success": True,
            "message": msg,
            "vehicles_fetched": vehicles_fetched,
            "entries_stored": total_entries,
            "errors": errors[:10]
        })
    except Exception as e:
        with _oil_fetch_lock:
            _oil_fetch_progress['status'] = 'error'
            _oil_fetch_progress['error'] = str(e)
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/oil-maintenance/fetch-progress")
def api_oil_fetch_progress():
    with _oil_fetch_lock:
        return jsonify(dict(_oil_fetch_progress) if _oil_fetch_progress else {"status": "idle"})


# ==============================================================
# VEHICLE MANAGEMENT
# ==============================================================

@app.route("/vehicle-management")
def vehicle_management_page():
    return render_template("vehicle-management.html")


@app.route("/api/fleet/vehicles", methods=["GET"])
def api_vehicles_list():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        q = request.args.get("q", "").strip()
        if q:
            c.execute(
                "SELECT * FROM vehicles WHERE plate_number LIKE ? ORDER BY plate_number",
                (f"%{q}%",)
            )
        else:
            c.execute("SELECT * FROM vehicles ORDER BY plate_number")
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({"success": True, "data": rows})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/fleet/vehicles", methods=["POST"])
def api_vehicles_create():
    try:
        data = request.json or {}
        plate = (data.get("plate_number") or "").strip().upper()
        vtype = (data.get("vehicle_type") or "").strip()
        driver = (data.get("current_driver") or "").strip()
        if not plate:
            return jsonify({"success": False, "message": "Plate number is required"}), 400
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT INTO vehicles (plate_number, vehicle_type, current_driver) VALUES (?, ?, ?)",
            (plate, vtype, driver)
        )
        conn.commit()
        vehicle_id = c.lastrowid
        conn.close()
        return jsonify({"success": True, "message": "Vehicle created", "vehicle": {
            "id": vehicle_id, "plate_number": plate, "vehicle_type": vtype, "current_driver": driver
        }})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "message": "Vehicle with that plate number already exists"}), 409
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/fleet/vehicles/<int:vehicle_id>", methods=["PUT"])
def api_vehicles_update(vehicle_id):
    try:
        data = request.json or {}
        plate = (data.get("plate_number") or "").strip().upper()
        vtype = (data.get("vehicle_type") or "").strip()
        driver = (data.get("current_driver") or "").strip()
        if not plate:
            return jsonify({"success": False, "message": "Plate number is required"}), 400
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "UPDATE vehicles SET plate_number=?, vehicle_type=?, current_driver=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (plate, vtype, driver, vehicle_id)
        )
        if c.rowcount == 0:
            conn.close()
            return jsonify({"success": False, "message": "Vehicle not found"}), 404
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Vehicle updated"})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "message": "Plate number already exists"}), 409
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/fleet/vehicles/<int:vehicle_id>", methods=["DELETE"])
def api_vehicles_delete(vehicle_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM vehicles WHERE id=?", (vehicle_id,))
        if c.rowcount == 0:
            conn.close()
            return jsonify({"success": False, "message": "Vehicle not found"}), 404
        # Unlink fuel_log entries referencing this vehicle
        c.execute("UPDATE fuel_log SET vehicle_id = NULL WHERE vehicle_id = ?", (vehicle_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Vehicle deleted"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/fleet/vehicles/search")
def api_vehicles_search():
    """Autocomplete: returns matching vehicles with plate, type, driver."""
    try:
        q = request.args.get("q", "").strip()
        if not q:
            return jsonify({"success": True, "data": []})
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            "SELECT id, plate_number, vehicle_type, current_driver FROM vehicles WHERE plate_number LIKE ? ORDER BY plate_number LIMIT 10",
            (f"%{q}%",)
        )
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({"success": True, "data": rows})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ----- Vehicle Types -----
@app.route("/api/fleet/vehicle-types", methods=["GET"])
def api_vehicle_types_list():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM vehicle_types ORDER BY name")
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({"success": True, "data": rows})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/fleet/vehicle-types", methods=["POST"])
def api_vehicle_types_create():
    try:
        data = request.json or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"success": False, "message": "Type name is required"}), 400
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO vehicle_types (name) VALUES (?)", (name,))
        conn.commit()
        type_id = c.lastrowid
        conn.close()
        return jsonify({"success": True, "message": "Type added", "id": type_id, "name": name})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "message": "Type already exists"}), 409
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/fleet/vehicle-types/<int:type_id>", methods=["DELETE"])
def api_vehicle_types_delete(type_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM vehicle_types WHERE id = ?", (type_id,))
        if c.rowcount == 0:
            conn.close()
            return jsonify({"success": False, "message": "Type not found"}), 404
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Type deleted"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ==============================================================
# FUEL EFFICIENCY / REFUEL LOG
# ==============================================================

def _compute_fuel_entry(row: dict) -> dict:
    """Add computed fields to a fuel_log row."""
    entry = dict(row)
    entry["distance_km"] = max(0, (entry["new_km"] or 0) - (entry["old_km"] or 0))
    dist = entry["distance_km"]
    liters = entry["liters"] or 0
    entry["l_per_100km"] = round((liters / dist * 100), 2) if dist > 0 else 0
    entry["total_cost"] = round((liters * (entry["unit_price"] or 0)), 2)
    entry["is_anomaly"] = False
    return entry


def _get_normal_l_per_100km(plate: str) -> float:
    """Look up the user-defined normal L/100km for a vehicle."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT normal_l_per_100km FROM fuel_vehicle_profile WHERE license_plate = ?", (plate,))
        row = c.fetchone()
        conn.close()
        return float(row[0]) if row else 0
    except Exception:
        return 0


def _compute_baseline(plate: str, exclude_id: int = None) -> float:
    """Compute moving average of l_per_100km of last 5 entries for a plate.
    If a manual normal_l_per_100km is set for this vehicle, returns that instead."""
    manual = _get_normal_l_per_100km(plate)
    if manual > 0:
        return manual
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if exclude_id:
        c.execute(
            "SELECT old_km, new_km, liters FROM fuel_log WHERE license_plate = ? AND id != ? ORDER BY id DESC LIMIT 5",
            (plate, exclude_id)
        )
    else:
        c.execute(
            "SELECT old_km, new_km, liters FROM fuel_log WHERE license_plate = ? ORDER BY id DESC LIMIT 5",
            (plate,)
        )
    rows = c.fetchall()
    conn.close()
    ratios = []
    for old_km, new_km, liters in rows:
        d = (new_km or 0) - (old_km or 0)
        if d > 0 and (liters or 0) > 0:
            ratios.append(liters / d * 100)
    return sum(ratios) / len(ratios) if ratios else 0


def _apply_anomaly_flag(entry: dict, baseline: float) -> dict:
    """Mark entry as anomaly if l_per_100km > 1.20 * baseline."""
    entry["baseline"] = round(baseline, 2)
    entry["normal_l_per_100km"] = round(_get_normal_l_per_100km(entry["license_plate"]), 2)
    if baseline > 0 and entry["l_per_100km"] > baseline * 1.20:
        entry["is_anomaly"] = True
    return entry


@app.route("/fuel-efficiency")
def fuel_efficiency_page():
    return render_template("fuel-efficiency.html")


def _enrich_fuel_entry(entry: dict) -> dict:
    """Add vehicle_type from vehicles table to a fuel entry."""
    if entry.get("vehicle_id"):
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT vehicle_type, current_driver FROM vehicles WHERE id = ?", (entry["vehicle_id"],))
            row = c.fetchone()
            conn.close()
            if row:
                entry["vehicle_type"] = row[0] or ""
                if not entry.get("driver_name"):
                    entry["driver_name"] = row[1] or ""
        except Exception:
            pass
    return entry


@app.route("/api/fuel-log", methods=["GET"])
def api_fuel_log_list():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        plate = request.args.get("license_plate", "").strip().upper()
        month = request.args.get("month", "").strip()
        vehicle_ids = request.args.get("vehicle_ids", "").strip()

        conditions = []
        params = []
        if plate:
            conditions.append("license_plate = ?")
            params.append(plate)
        if month:
            conditions.append("log_date LIKE ?")
            params.append(f"{month}%")
        if vehicle_ids:
            ids = [x.strip() for x in vehicle_ids.split(",") if x.strip().isdigit()]
            if ids:
                conditions.append(f"vehicle_id IN ({','.join('?' * len(ids))})")
                params.extend(ids)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        c.execute(f"SELECT * FROM fuel_log {where} ORDER BY log_date DESC, log_time DESC", params)
        rows = [dict(r) for r in c.fetchall()]
        conn.close()

        results = []
        for r in rows:
            entry = _compute_fuel_entry(r)
            entry = _enrich_fuel_entry(entry)
            baseline = _compute_baseline(entry["license_plate"], entry["id"])
            entry = _apply_anomaly_flag(entry, baseline)
            results.append(entry)

        return jsonify({"success": True, "data": results})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/fuel-log/months", methods=["GET"])
def api_fuel_log_months():
    """Return all distinct months (YYYY-MM) that have fuel_log entries."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT DISTINCT substr(log_date,1,7) AS ym FROM fuel_log ORDER BY ym DESC")
        months = [r[0] for r in c.fetchall()]
        conn.close()
        return jsonify({"success": True, "data": months})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/fuel-log/days", methods=["GET"])
def api_fuel_log_days():
    """Return all distinct days in a given month (YYYY-MM-DD) that have entries."""
    try:
        month = request.args.get("month", "").strip()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        if month:
            c.execute("SELECT DISTINCT log_date FROM fuel_log WHERE log_date LIKE ? ORDER BY log_date", (f"{month}%",))
        else:
            c.execute("SELECT DISTINCT log_date FROM fuel_log ORDER BY log_date")
        days = [r[0] for r in c.fetchall()]
        conn.close()
        return jsonify({"success": True, "data": days})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/fuel-log/stats", methods=["GET"])
def api_fuel_log_stats():
    """Monthly stats: total distance, total fuel, avg L/100km, anomaly count."""
    try:
        month = request.args.get("month", "").strip()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        if month:
            c.execute("SELECT * FROM fuel_log WHERE log_date LIKE ?", (f"{month}%",))
        else:
            c.execute("SELECT * FROM fuel_log")
        rows = [dict(r) for r in c.fetchall()]
        conn.close()

        total_distance = 0
        total_fuel = 0.0
        valid_entries = 0
        total_anomalies = 0
        sum_l100 = 0.0

        for r in rows:
            entry = _compute_fuel_entry(r)
            entry = _enrich_fuel_entry(entry)
            baseline = _compute_baseline(entry["license_plate"], entry["id"])
            entry = _apply_anomaly_flag(entry, baseline)
            dist = entry.get("distance_km", 0)
            liters = entry.get("liters", 0)
            if dist > 0 and liters > 0:
                total_distance += dist
                total_fuel += liters
                sum_l100 += entry["l_per_100km"]
                valid_entries += 1
            if entry.get("is_anomaly"):
                total_anomalies += 1

        avg_l_per_100km = round(sum_l100 / valid_entries, 2) if valid_entries > 0 else 0
        return jsonify({
            "success": True,
            "total_distance": total_distance,
            "total_fuel": round(total_fuel, 2),
            "avg_l_per_100km": avg_l_per_100km,
            "entry_count": len(rows),
            "anomaly_count": total_anomalies
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/fuel-log", methods=["POST"])
def api_fuel_log_create():
    try:
        data = request.json or {}
        vehicle_id = data.get("vehicle_id")
        plate = (data.get("license_plate") or "").strip().upper()
        log_date = (data.get("log_date") or "").strip()
        log_time = (data.get("log_time") or "").strip()
        gas_store = (data.get("gas_store") or "").strip()
        old_km = int(data.get("old_km") or 0)
        new_km = int(data.get("new_km") or 0)
        liters = float(data.get("liters") or 0)
        driver_name = (data.get("driver_name") or "").strip()
        unit_price = data.get("unit_price")
        if unit_price is not None:
            unit_price = float(unit_price)
        notes = (data.get("notes") or "").strip()

        # If vehicle_id is provided, look up plate and driver from vehicles table
        if vehicle_id:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT plate_number, current_driver FROM vehicles WHERE id = ?", (vehicle_id,))
            row = c.fetchone()
            conn.close()
            if row:
                if not plate:
                    plate = row[0]
                if not driver_name:
                    driver_name = row[1] or ""

        if not plate:
            return jsonify({"success": False, "message": "License plate is required"}), 400
        if not log_date:
            return jsonify({"success": False, "message": "Date is required"}), 400
        if not log_time:
            return jsonify({"success": False, "message": "Time is required"}), 400
        if new_km < old_km:
            return jsonify({"success": False, "message": "New KM must be >= Old KM"}), 400
        if liters <= 0:
            return jsonify({"success": False, "message": "Liters must be > 0"}), 400

        distance_km = new_km - old_km
        warnings = []
        if distance_km > 2000:
            warnings.append("Distance exceeds 2000 km — please verify.")
        if distance_km < 1:
            warnings.append("Distance is less than 1 km — please verify.")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT INTO fuel_log (license_plate, log_date, log_time, gas_store, old_km, new_km, liters, driver_name, unit_price, notes, vehicle_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (plate, log_date, log_time, gas_store, old_km, new_km, liters, driver_name, unit_price, notes, vehicle_id)
        )
        conn.commit()
        new_id = c.lastrowid
        # Ensure vehicle exists in vehicles table
        c.execute(
            "INSERT INTO vehicles (plate_number, current_driver) VALUES (?, ?) ON CONFLICT(plate_number) DO UPDATE SET current_driver = COALESCE(NULLIF(?, ''), current_driver)",
            (plate, driver_name, driver_name)
        )
        # Link vehicle_id if not already set
        if not vehicle_id:
            c.execute(
                "UPDATE fuel_log SET vehicle_id = (SELECT id FROM vehicles WHERE plate_number = ?) WHERE id = ?",
                (plate, new_id)
            )
        conn.commit()
        conn.close()

        entry = _compute_fuel_entry({
            "id": new_id, "license_plate": plate, "log_date": log_date, "log_time": log_time,
            "gas_store": gas_store, "old_km": old_km, "new_km": new_km, "liters": liters,
            "driver_name": driver_name, "unit_price": unit_price, "notes": notes, "created_at": "",
            "vehicle_id": vehicle_id
        })
        entry = _enrich_fuel_entry(entry)
        baseline = _compute_baseline(plate, new_id)
        entry = _apply_anomaly_flag(entry, baseline)

        resp = {"success": True, "message": "Fuel log entry created", "entry": entry}
        if warnings:
            resp["warnings"] = warnings
        return jsonify(resp)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/fuel-log/<int:entry_id>", methods=["PUT"])
def api_fuel_log_update(entry_id):
    try:
        data = request.json or {}
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute("SELECT * FROM fuel_log WHERE id = ?", (entry_id,))
        existing = c.fetchone()
        if not existing:
            conn.close()
            return jsonify({"success": False, "message": "Entry not found"}), 404

        vehicle_id = data.get("vehicle_id", existing["vehicle_id"])
        plate = (data.get("license_plate") or existing["license_plate"]).strip().upper()
        log_date = (data.get("log_date") or existing["log_date"]).strip()
        log_time = (data.get("log_time") or existing["log_time"]).strip()
        gas_store = (data.get("gas_store") if "gas_store" in data else existing["gas_store"]).strip()
        old_km = int(data.get("old_km", existing["old_km"]))
        new_km = int(data.get("new_km", existing["new_km"]))
        liters = float(data.get("liters", existing["liters"]))
        driver_name = (data.get("driver_name") if "driver_name" in data else existing["driver_name"]).strip()
        unit_price = data.get("unit_price", existing["unit_price"])
        if unit_price is not None:
            unit_price = float(unit_price)
        notes = (data.get("notes") if "notes" in data else existing["notes"]).strip()

        if new_km < old_km:
            conn.close()
            return jsonify({"success": False, "message": "New KM must be >= Old KM"}), 400
        if liters <= 0:
            conn.close()
            return jsonify({"success": False, "message": "Liters must be > 0"}), 400

        distance_km = new_km - old_km
        warnings = []
        if distance_km > 2000:
            warnings.append("Distance exceeds 2000 km — please verify.")
        if distance_km < 1:
            warnings.append("Distance is less than 1 km — please verify.")

        c.execute(
            "UPDATE fuel_log SET license_plate=?, log_date=?, log_time=?, gas_store=?, old_km=?, new_km=?, liters=?, driver_name=?, unit_price=?, notes=?, vehicle_id=? WHERE id=?",
            (plate, log_date, log_time, gas_store, old_km, new_km, liters, driver_name, unit_price, notes, vehicle_id, entry_id)
        )
        conn.commit()

        c.execute("SELECT * FROM fuel_log WHERE id = ?", (entry_id,))
        updated = dict(c.fetchone())
        conn.close()

        entry = _compute_fuel_entry(updated)
        entry = _enrich_fuel_entry(entry)
        baseline = _compute_baseline(plate, entry_id)
        entry = _apply_anomaly_flag(entry, baseline)

        resp = {"success": True, "message": "Fuel log entry updated", "entry": entry}
        if warnings:
            resp["warnings"] = warnings
        return jsonify(resp)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/fuel-log/<int:entry_id>", methods=["DELETE"])
def api_fuel_log_delete(entry_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM fuel_log WHERE id = ?", (entry_id,))
        if c.rowcount == 0:
            conn.close()
            return jsonify({"success": False, "message": "Entry not found"}), 404
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Entry deleted"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/fuel-log/summary")
def api_fuel_log_summary():
    try:
        month = request.args.get("month", "").strip()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        if month:
            c.execute("SELECT DISTINCT license_plate FROM fuel_log WHERE log_date LIKE ? ORDER BY license_plate", (f"{month}%",))
        else:
            c.execute("SELECT DISTINCT license_plate FROM fuel_log ORDER BY license_plate")
        plates = [r["license_plate"] for r in c.fetchall()]

        summaries = []
        total_anomalies = 0
        fleet_sum_l100 = fleet_cnt = 0
        for plate in plates:
            if month:
                c.execute(
                    "SELECT * FROM fuel_log WHERE license_plate = ? AND log_date LIKE ? ORDER BY log_date DESC, log_time DESC",
                    (plate, f"{month}%")
                )
            else:
                c.execute(
                    "SELECT * FROM fuel_log WHERE license_plate = ? ORDER BY log_date DESC, log_time DESC",
                    (plate,)
                )
            rows = [dict(r) for r in c.fetchall()]
            entries = [_compute_fuel_entry(r) for r in rows]
            baseline = _compute_baseline(plate)
            entries = [_apply_anomaly_flag(e, baseline) for e in entries]
            anomalies = [e for e in entries if e["is_anomaly"]]
            total_anomalies += len(anomalies)
            valid = [e for e in entries if e["l_per_100km"] > 0]
            sum_l100 = sum(e["l_per_100km"] for e in valid)
            cnt = len(valid)
            fleet_sum_l100 += sum_l100
            fleet_cnt += cnt
            summaries.append({
                "license_plate": plate,
                "total_entries": len(entries),
                "avg_l_per_100km": round(sum_l100 / cnt, 2) if cnt > 0 else 0,
                "baseline": round(baseline, 2),
                "active_anomalies": len(anomalies),
                "total_liters": round(sum(e["liters"] for e in entries), 2),
                "total_cost": round(sum(e["total_cost"] for e in entries), 2)
            })

        conn.close()
        return jsonify({
            "success": True,
            "data": summaries,
            "total_anomalies": total_anomalies,
            "total_entries": sum(s["total_entries"] for s in summaries),
            "fleet_avg_l_per_100km": round(fleet_sum_l100 / fleet_cnt, 2) if fleet_cnt > 0 else 0
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/fuel-log/export")
def api_fuel_log_export():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        plate = request.args.get("license_plate", "").strip().upper()
        month = request.args.get("month", "").strip()
        conditions = []
        params = []
        if plate:
            conditions.append("license_plate = ?")
            params.append(plate)
        if month:
            conditions.append("log_date LIKE ?")
            params.append(f"{month}%")
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        c.execute(f"SELECT * FROM fuel_log {where} ORDER BY log_date DESC, log_time DESC", params)
        rows = [dict(r) for r in c.fetchall()]
        conn.close()

        import io, csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "License Plate", "Date", "Time", "Gas Store",
            "Old KM", "New KM", "Distance KM", "Liters",
            "L/100km", "Unit Price", "Total Cost",
            "Driver Name", "Notes", "Anomaly"
        ])
        for r in rows:
            entry = _compute_fuel_entry(r)
            baseline = _compute_baseline(entry["license_plate"], entry["id"])
            entry = _apply_anomaly_flag(entry, baseline)
            writer.writerow([
                entry["id"], "\t" + entry["license_plate"], entry["log_date"], entry["log_time"],
                entry["gas_store"], entry["old_km"], entry["new_km"],
                entry["distance_km"], entry["liters"], entry["l_per_100km"],
                entry.get("unit_price") or "",
                entry["total_cost"], entry["driver_name"], entry["notes"],
                "Yes" if entry["is_anomaly"] else "No"
            ])

        csv_bytes = output.getvalue().encode("utf-8-sig")
        return Response(
            csv_bytes,
            mimetype="text/csv; charset=utf-8-sig",
            headers={"Content-Disposition": "attachment; filename=fuel_efficiency_report.csv"}
        )
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/fuel-log/profiles", methods=["GET"])
def api_fuel_log_profiles_list():
    """Return all vehicle fuel profiles with their normal L/100km."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM fuel_vehicle_profile ORDER BY license_plate")
        profiles = [dict(r) for r in c.fetchall()]
        conn.close()

        # Also include vehicles that have fuel_log entries but no profile yet
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT DISTINCT license_plate FROM fuel_log ORDER BY license_plate")
        all_plates = [r[0] for r in c.fetchall()]
        conn.close()

        known = {p["license_plate"] for p in profiles}
        for plate in all_plates:
            if plate not in known:
                profiles.append({
                    "license_plate": plate,
                    "normal_l_per_100km": _get_normal_l_per_100km(plate),
                    "updated_at": None
                })

        return jsonify({"success": True, "data": profiles})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/fuel-log/profiles/<path:plate>", methods=["PUT"])
def api_fuel_log_profile_update(plate):
    """Create or update a vehicle's normal L/100km."""
    try:
        plate = plate.strip().upper()
        data = request.json or {}
        normal = float(data.get("normal_l_per_100km") or 0)
        if normal <= 0:
            return jsonify({"success": False, "message": "normal_l_per_100km must be > 0"}), 400

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT INTO fuel_vehicle_profile (license_plate, normal_l_per_100km, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(license_plate) DO UPDATE SET normal_l_per_100km = ?, updated_at = CURRENT_TIMESTAMP",
            (plate, normal, normal)
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"Normal L/100km for {plate} set to {normal}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/fuel-log/profiles/<path:plate>", methods=["DELETE"])
def api_fuel_log_profile_delete(plate):
    """Remove a vehicle's manual normal L/100km (revert to computed baseline)."""
    try:
        plate = plate.strip().upper()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM fuel_vehicle_profile WHERE license_plate = ?", (plate,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"Normal L/100km for {plate} cleared"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


if __name__ == "__main__":
    init_db()
    start_route_refresh_thread()
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG, use_reloader=False)
