"""
Entry point. Builds the Flask app via app.create_app() (see app/__init__.py)
and registers the remaining routes that haven't been extracted into a
domain blueprint yet (index, the main /api/vehicles list, manual-location
management, geocoding, and the delivery page routes) — see
CODEBASE_ANALYSIS_REPORT.md Section 6.4.1 for the extraction plan this
followed.
"""
from flask import jsonify, render_template, request

from app import create_app, config, state
from app.services.ttas_client import fetch_vehicle_data, normalize_vehicle
from app.services.locations import read_manual_locations, write_manual_locations, parse_location_payload
from app.routes.trips import start_route_refresh_thread

app = create_app()


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
        "source_url": config.TTAS_TRACKING_PAGE_URL,
        "error": error,
    })


@app.route("/api/known-locations")
def api_known_locations():
    return jsonify(state.known_locations)


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

        if name in state.known_locations:
            # Add to existing location
            existing = state.known_locations[name]
            polygons = existing.get("polygons", [])
            polygons.append(new_polygon)

            # Update both known_locations and manual_locs
            updated_loc = {"polygons": polygons, "type": "multi_polygon"}
            state.known_locations[name] = updated_loc
            manual_locs[name] = updated_loc
        else:
            # Create new location
            new_loc = {"polygons": [new_polygon], "type": "multi_polygon"}
            state.known_locations[name] = new_loc
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
        if original_name not in state.known_locations and original_name not in manual_locs:
            return jsonify({"success": False, "message": "Not found"}), 404

        name = parsed["name"]
        new_polygon = parsed["corners"]

        # Handle renaming if needed
        if name != original_name:
            if name in state.known_locations or name in manual_locs:
                return jsonify({"success": False, "message": "Name exists"}), 409

            # Move location to new name
            if original_name in manual_locs:
                manual_locs[name] = manual_locs.pop(original_name)
            if original_name in state.known_locations:
                state.known_locations[name] = state.known_locations.pop(original_name)

        # Update the polygons (replace all polygons with new one for edit mode)
        updated_loc = {"polygons": [new_polygon], "type": "multi_polygon"}
        manual_locs[name] = updated_loc
        state.known_locations[name] = updated_loc
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
        if name not in state.known_locations and name not in manual_locs:
            return jsonify({"success": False, "message": "Not found"}), 404

        state.known_locations.pop(name, None)
        manual_locs.pop(name, None)
        write_manual_locations(manual_locs)

        return jsonify({"success": True, "message": f"Location '{name}' deleted"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/clear-all-locations", methods=["POST"])
def api_clear_all_locations():
    try:
        state.known_locations = {}
        write_manual_locations({})

        return jsonify({"success": True, "message": "All locations cleared"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/locations")
def locations():
    return render_template("locations.html")


@app.route("/delivery/new")
def delivery_plan_builder():
    return render_template("delivery-plan-builder.html", edit_plan_id=None)


@app.route("/delivery/edit/<int:plan_id>")
def edit_delivery_plan(plan_id):
    return render_template("delivery-plan-builder.html", edit_plan_id=plan_id)


@app.route("/delivery/dashboard")
def delivery_dashboard():
    return render_template("delivery-dashboard.html")


@app.route("/api/manual-locations")
def api_manual_locations():
    return jsonify(read_manual_locations())


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


if __name__ == "__main__":
    # Background route polling thread — local development only.
    #
    # Under Gunicorn this is intentionally NOT started because:
    #   - Multiple workers would each spawn their own polling thread,
    #     causing duplicate ORS API calls and cache conflicts.
    #   - The shared route_data_cache would suffer race conditions.
    #
    # Production alternatives:
    #   a) Run Gunicorn with --workers=1 --threads=N if background
    #      polling is essential (single-process, concurrent requests).
    #   b) Use an external scheduler (cron, Celery beat, APScheduler)
    #      that calls POST /api/refresh-routes periodically.
    start_route_refresh_thread()
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG, use_reloader=False)
