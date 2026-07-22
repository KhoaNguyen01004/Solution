"""Debug vehicle data."""
import sys, os, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "routing_system.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

c = conn.cursor()
c.execute("""
    SELECT v.id AS vehicle_id, v.plate_number, v.vehicle_type,
           cc.id AS cc_id, cc.name AS container_name,
           cc.cargo_length_mm, cc.cargo_width_mm, cc.cargo_height_mm, cc.payload_kg
    FROM vehicles v
    INNER JOIN container_configs cc ON cc.id = v.container_config_id
    ORDER BY v.plate_number
""")
vrows = c.fetchall()
conn.close()

print(f"Total vehicles: {len(vrows)}\n")
for vr in vrows:
    v = dict(vr)
    print(f"V{v['vehicle_id']:>3}: {v['plate_number']:>12} | {v['container_name']:>15} | "
          f"L={v['cargo_length_mm']:>5} W={v['cargo_width_mm']:>4} H={v['cargo_height_mm']:>4} "
          f"Payload={v['payload_kg']:>6}kg | Volume={v['cargo_length_mm']*v['cargo_width_mm']*v['cargo_height_mm']/1e9:.1f}m3")
