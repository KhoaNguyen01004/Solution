import sqlite3
import logging

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS drivers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT DEFAULT '',
    license_number TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS delivery_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_name TEXT NOT NULL,
    plan_date DATE NOT NULL,
    description TEXT DEFAULT '',
    status TEXT DEFAULT 'draft',
    imported_at TIMESTAMP,
    created_by TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vehicle_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL REFERENCES delivery_plans(id) ON DELETE CASCADE,
    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
    driver_id INTEGER REFERENCES drivers(id),
    sequence INTEGER NOT NULL DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS delivery_plan_stops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_assignment_id INTEGER NOT NULL REFERENCES vehicle_assignments(id) ON DELETE CASCADE,
    planned_sequence INTEGER NOT NULL DEFAULT 0,
    station_code TEXT DEFAULT '',
    station_name TEXT DEFAULT '',
    address TEXT DEFAULT '',
    lat REAL,
    lng REAL,
    manager_name TEXT DEFAULT '',
    manager_phone TEXT DEFAULT '',
    product_description TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stop_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stop_id INTEGER NOT NULL REFERENCES delivery_plan_stops(id) ON DELETE CASCADE,
    execution_sequence INTEGER NOT NULL DEFAULT 0,
    status TEXT DEFAULT 'planned',
    skip_reason TEXT DEFAULT '',
    cancel_reason TEXT DEFAULT '',
    actual_arrival_at TIMESTAMP,
    actual_departure_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS delivery_stop_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stop_id INTEGER NOT NULL REFERENCES delivery_plan_stops(id) ON DELETE CASCADE,
    category TEXT NOT NULL DEFAULT 'extra',
    filename TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    original_filename TEXT DEFAULT '',
    gps_lat REAL,
    gps_lng REAL,
    captured_at TIMESTAMP,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uploaded_by TEXT DEFAULT ''
);
"""

INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_vehicle_assignments_plan ON vehicle_assignments(plan_id);
CREATE INDEX IF NOT EXISTS idx_vehicle_assignments_vehicle ON vehicle_assignments(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_delivery_plan_stops_assignment ON delivery_plan_stops(vehicle_assignment_id);
CREATE INDEX IF NOT EXISTS idx_stop_executions_stop ON stop_executions(stop_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_stop_executions_unique ON stop_executions(stop_id);
CREATE INDEX IF NOT EXISTS idx_delivery_stop_images_stop ON delivery_stop_images(stop_id);
"""


def init_delivery_tables(db_path: str):
    conn = sqlite3.connect(db_path)
    try:
        c = conn.cursor()

        for stmt in SCHEMA_SQL.split(";"):
            stmt = stmt.strip()
            if stmt:
                c.execute(stmt)

        for stmt in INDEXES_SQL.split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    c.execute(stmt)
                except Exception as e:
                    logger.warning("Index: %s", e)

        conn.commit()
        logger.info("Delivery tables initialized.")
    finally:
        conn.close()
