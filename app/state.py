"""
Shared mutable runtime state.

Not one of the report's named modules — added because app.py's module-level
globals (route_data_cache, KNOWN_LOCATIONS, fleet_session, the oil-fetch
progress tracker, etc.) are read and mutated across the fleet/fuel/oil/trips
route blueprints and the TTAS service layer. Without a shared home for
this state, those modules would need to import it from each other,
creating circular imports. Mutate via module attribute assignment
(``state.route_data_cache = {...}``), which — unlike a plain module-level
variable rebind via `global` — works correctly from any importing module.
"""
import threading

route_data_cache = {}
cache_lock = threading.Lock()
last_manual_update = 0.0

oil_fetch_progress = {}
oil_fetch_lock = threading.Lock()

sync_lock = threading.Lock()

known_locations = {}

# Set once at app startup (create_fleet_session); reassigned by
# ensure_session()/refresh_session() in app.services.ttas_client.
fleet_session = None
