"""
Live trip routing for the main fleet map: route geometry, phase advancement,
cancellation, and the background route-refresh loop.

Extracted from app.py (Section 6.4.1, Phase 12).

Scope narrowed 2026-07-31. This module used to own two pages — Trip Management
(`/manage-trips`) and Trip History (`/trip-history`) — which were the original
dispatch UI. The delivery dashboard superseded them rather than reusing them,
leaving two implementations of the same job; the pages and the eight endpoints
only they called were removed in favour of the dashboard. See docs/CHANGELOG.md.

What remains serves `static/js/map.js` on the main map page: `/api/route-data`
for the drawn route lines, `/api/advance-trip` and `/api/cancel-trip` for the
per-vehicle controls, plus `/api/refresh-routes` (the documented external
scheduler hook) and the background refresher behind it.

Note that nothing can create a `vehicle_trips` row any more — `/api/set-destination`
went with the Trip Management page — so the surviving read/advance/cancel paths
operate on a table that is currently empty and can only be populated directly.
"""
import json
import re
import sqlite3
import threading
import time
import traceback

from flask import Blueprint, jsonify, request

from app import config, state
from app.utils.geo import is_point_in_location, clean_text
from app.services.ttas_client import fetch_vehicle_data, normalize_vehicle
from app.services.routing import get_routing_profile, get_route_coords

bp = Blueprint("trips", __name__)


@bp.route("/api/route-data")
def get_route_data():
    with state.cache_lock:
        return jsonify(list(state.route_data_cache.values()))


@bp.route("/api/refresh-routes", methods=["POST"])
def api_refresh_routes():
    success = do_refresh_route_data()
    if success:
        return jsonify({"success": True, "route_data": list(state.route_data_cache.values())})
    return jsonify({"success": False, "message": "Failed to refresh"}), 500


@bp.route("/api/advance-trip", methods=["POST"])
def api_advance_trip():
    """Force advance trip phase or complete trip."""
    conn = None
    try:
        data = request.json or {}
        trip_id = data.get("trip_id")
        action = data.get("action", "advance")  # 'advance' or 'complete'

        if not trip_id:
            return jsonify({"success": False, "message": "Missing trip_id"}), 400

        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute('SELECT * FROM vehicle_trips WHERE id = ?', (trip_id,))
        trip = c.fetchone()
        if not trip:
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
            # Closed before do_refresh_route_data(), which opens its own
            # connection and writes: leaving this one open across it would
            # have two writers on the same file from one request. The finally
            # is the guarantee, this is the scoping.
            conn.close()
            conn = None

            state.last_manual_update = time.time()
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
                conn = None

                state.last_manual_update = time.time()
                do_refresh_route_data()

                return jsonify({"success": True, "message": "Trip force-completed (no more stops)"})
            else:
                c.execute('''
                    UPDATE vehicle_trips SET phase = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
                ''', (next_phase, trip_id))
                conn.commit()
                conn.close()
                conn = None

                state.last_manual_update = time.time()
                do_refresh_route_data()

                return jsonify({"success": True, "message": f"Trip advanced to phase {next_phase}"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn is not None:
            conn.close()


@bp.route("/api/cancel-trip", methods=["POST"])
def api_cancel_trip():
    """Cancel an active or queued trip."""
    conn = None
    try:
        data = request.json or {}
        trip_id = data.get("trip_id")
        reason = (data.get("reason") or "Manual cancellation").strip()

        if not trip_id:
            return jsonify({"success": False, "message": "Missing trip_id"}), 400

        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Get current status before updating
        c.execute('SELECT vehicle_id, status FROM vehicle_trips WHERE id = ?', (trip_id,))
        trip_before = c.fetchone()
        if not trip_before:
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
        conn = None

        state.last_manual_update = time.time()
        do_refresh_route_data()

        return jsonify({"success": True, "message": "Trip canceled"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn is not None:
            conn.close()


# --------------------------
# Route Refresh Functions
# --------------------------
def do_refresh_route_data():
    _call_start = time.time()
    conn = None
    try:
        raw_vehicles, _, _ = fetch_vehicle_data()
        vehicles = [normalize_vehicle(v) for v in raw_vehicles]

        conn = sqlite3.connect(config.DB_PATH)
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

                    # One transaction per trip: the driver-name update and the
                    # geofence advance either both land or neither does.
                    #
                    # This block used to open an explicit `conn.execute('BEGIN')`
                    # here, which could not work (2026-08-06 audit). Two ways:
                    #
                    #   1. Python's sqlite3 opens a transaction implicitly
                    #      before the driver_name UPDATE below, so an explicit
                    #      BEGIN after it raised "cannot start a transaction
                    #      within a transaction";
                    #   2. when no vehicle had arrived — the normal case —
                    #      neither commit branch ran, so the transaction stayed
                    #      open and the *next* iteration's BEGIN raised the
                    #      same error.
                    #
                    # The per-trip `except` below swallowed both, so geofence
                    # auto-advance silently stopped happening for every trip
                    # after the first. It also left an uncommitted write
                    # holding a RESERVED lock across the ORS calls further down
                    # this function, which is one concrete source of
                    # "database is locked".
                    #
                    # Every other write path in this file (api_advance_trip,
                    # api_cancel_trip) uses the implicit transaction and a
                    # plain commit. This now matches them.
                    try:
                        # Update driver_name on trip
                        if driver_name and driver_name != active_trip.get('driver_name', ''):
                            c.execute('UPDATE vehicle_trips SET driver_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (driver_name, trip_id))

                        # Check geofence for current target
                        target_lat, target_lng, target_name, target_type = get_target_for_phase(db_phase)

                        if target_name and target_lat and target_lng:
                            target_location = state.known_locations.get(target_name)
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
                                else:
                                    # Advance to next phase
                                    c.execute('''
                                        UPDATE vehicle_trips SET phase = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
                                    ''', (next_phase, trip_id))
                                    print(f"Vehicle {vehicle_id} arrived at '{target_name}' (phase {db_phase}), advancing to phase {next_phase}")

                        # Single exit point. The completion branch used to
                        # commit and `continue` purely to dodge a second commit
                        # below; with one commit per iteration both branches
                        # converge here and the `continue` is unnecessary.
                        conn.commit()
                    except Exception:
                        conn.rollback()
                        raise

                except Exception as e:
                    print(f"Error processing active trip {active_trip.get('id', 'unknown')}: {e}")
                    traceback.print_exc()
        except Exception as e:
            print(f"Error checking active trips: {e}")
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
                    traceback.print_exc()
        except Exception as e:
            print(f"Error fetching trips: {e}")

        conn.close()
        conn = None

        with state.cache_lock:
            if _call_start >= state.last_manual_update:
                state.route_data_cache = new_route_data
            else:
                pass  # stale data from bg thread, skip
        return True
    except Exception as e:
        print(f"Error refreshing routes: {e}")
        traceback.print_exc()
        return False
    finally:
        # This runs on the background refresh thread every
        # ROUTE_REFRESH_INTERVAL seconds, forever. A connection leaked on the
        # error path here is leaked once per cycle, not once per request.
        if conn is not None:
            conn.close()


def refresh_route_data():
    while True:
        do_refresh_route_data()
        time.sleep(config.ROUTE_REFRESH_INTERVAL)


def start_route_refresh_thread():
    thread = threading.Thread(target=refresh_route_data, daemon=True)
    thread.start()
