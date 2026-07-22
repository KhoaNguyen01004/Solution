"""Query the local database for real shipment data."""
import os, sqlite3
_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "routing_system.db")

conn = sqlite3.connect(_db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("=== TABLES ===")
c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
for r in c.fetchall():
    print(f"  {r['name']}")

print("\n=== VEHICLES WITH CONTAINERS ===")
c.execute("""
    SELECT v.id, v.plate_number, v.vehicle_type,
           cc.name AS cc_name,
           cc.cargo_length_mm, cc.cargo_width_mm, cc.cargo_height_mm, cc.payload_kg
    FROM vehicles v
    JOIN container_configs cc ON cc.id = v.container_config_id
    ORDER BY v.id
""")
for r in c.fetchall():
    print(f"  id={r['id']} plate={r['plate_number']} type={r['vehicle_type']}")
    print(f"    container={r['cc_name']} {r['cargo_length_mm']}x{r['cargo_width_mm']}x{r['cargo_height_mm']} payload={r['payload_kg']}kg")

print("\n=== PACKAGES (first 20) ===")
c.execute("SELECT * FROM tlp_packages ORDER BY id LIMIT 20")
cols = [d[0] for d in c.description]
for r in c.fetchall():
    d = dict(r)
    print(f"  id={d['id']:4d} name={d['name']:20s} {d['length']:5.0f}x{d['width']:5.0f}x{d['height']:5.0f} "
          f"{d['weight_kg']:6.1f}kg stackable={d['allow_stacking']} rotation={d['allow_rotation']}")

print("\n=== TOTAL PACKAGES ===")
c.execute("SELECT COUNT(*) FROM tlp_packages")
print(f"  {c.fetchone()[0]}")

print("\n=== SHIPMENTS ===")
c.execute("""
    SELECT s.id, s.customer_name, s.reference_number,
           COUNT(si.id) AS item_count,
           SUM(si.quantity) AS total_qty
    FROM tlp_shipments s
    LEFT JOIN tlp_shipment_items si ON si.shipment_id = s.id
    GROUP BY s.id
    ORDER BY s.id DESC
    LIMIT 10
""")
for r in c.fetchall():
    print(f"  id={r['id']} customer={r['customer_name']} ref={r['reference_number']} "
          f"items={r['item_count']} total_qty={r['total_qty']}")

print("\n=== SHIPMENT ITEMS (largest shipment) ===")
c.execute("SELECT MAX(id) FROM tlp_shipments")
max_id = c.fetchone()[0]
if max_id:
    c.execute("""
        SELECT p.id, p.name, p.length, p.width, p.height, p.weight_kg,
               p.allow_stacking, p.allow_rotation, si.quantity
        FROM tlp_shipment_items si
        JOIN packages p ON p.id = si.package_id
        WHERE si.shipment_id = ?
        ORDER BY p.allow_stacking, p.length * p.width * p.height DESC
    """, (max_id,))
    rows = c.fetchall()
    print(f"  Shipment {max_id}: {len(rows)} distinct package types")
    total_qty = 0
    for r in rows:
        qty = r['quantity']
        total_qty += qty
        print(f"    qty={qty:3d} id={r['id']:4d} {r['name']:20s} "
              f"{r['length']:5.0f}x{r['width']:5.0f}x{r['height']:5.0f} "
              f"{r['weight_kg']:6.1f}kg stack={r['allow_stacking']} rot={r['allow_rotation']}")
    print(f"  Total packages: {total_qty}")

print("\n=== LOAD PLANS ===")
c.execute("""
    SELECT lp.id, lp.name, lp.vehicle_id, lp.shipment_id, lp.status,
           COUNT(pl.id) AS placement_count
    FROM tlp_load_plans lp
    LEFT JOIN tlp_placements pl ON pl.load_plan_id = lp.id
    GROUP BY lp.id
    ORDER BY lp.id DESC
    LIMIT 5
""")
for r in c.fetchall():
    print(f"  id={r['id']} name={r['name']} vehicle={r['vehicle_id']} "
          f"shipment={r['shipment_id']} status={r['status']} placements={r['placement_count']}")

conn.close()
