"""Print vehicle info with capacity index."""
import sys, os, sqlite3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "routing_system.db"))
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

print("=== ALL VEHICLES (by plate) ===")
for vr in vrows:
    vd = dict(vr)
    vol = vd["cargo_length_mm"] * vd["cargo_width_mm"] * vd["cargo_height_mm"]
    cap = vol * max(vd["payload_kg"], 1)
    print(f"  V{vd['vehicle_id']:3d} {vd['plate_number']:>8s} "
          f"{vd['cargo_length_mm']}x{vd['cargo_width_mm']}x{vd['cargo_height_mm']}mm "
          f"cap_idx={cap:.2e}")

sorted_v = sorted(vrows, key=lambda vr: -(
    vr["cargo_length_mm"] * vr["cargo_width_mm"] * vr["cargo_height_mm"]
    * max(vr["payload_kg"], 1)
))

print("\n=== VEHICLES SORTED BY CAPACITY (largest first) ===")
for vr in sorted_v:
    vd = dict(vr)
    vol = vd["cargo_length_mm"] * vd["cargo_width_mm"] * vd["cargo_height_mm"]
    cap = vol * max(vd["payload_kg"], 1)
    print(f"  V{vd['vehicle_id']:3d} {vd['plate_number']:>8s} "
          f"{vd['cargo_length_mm']}x{vd['cargo_width_mm']}x{vd['cargo_height_mm']}mm "
          f"cap_idx={cap:.2e}")
