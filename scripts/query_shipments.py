"""Extract real shipment data from database."""
import os, sqlite3
_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "routing_system.db")

conn = sqlite3.connect(_db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("=== SHIPMENTS ===")
c.execute("SELECT id, customer_name, reference_number FROM tlp_shipments ORDER BY id")
for r in c.fetchall():
    print(f"  id={r['id']} cust={r['customer_name']} ref={r['reference_number']}")

print("\n=== SHIPMENT ITEMS ===")
c.execute("SELECT DISTINCT shipment_id FROM tlp_shipment_items ORDER BY shipment_id")
ship_ids = [r["shipment_id"] for r in c.fetchall()]
for sid in ship_ids:
    print(f"\n  Shipment {sid}:")
    c.execute("""
        SELECT si.quantity, p.id, p.name, p.length, p.width, p.height,
               p.weight_kg, p.allow_stacking, p.allow_rotation
        FROM tlp_shipment_items si
        JOIN tlp_packages p ON p.id = si.package_id
        WHERE si.shipment_id = ?
        ORDER BY p.allow_stacking, p.length * p.width * p.height DESC
    """, (sid,))
    rows = c.fetchall()
    total = 0
    for r in rows:
        qty = r["quantity"]
        total += qty
        print(f"    qty={qty:2d} id={r['id']:3d} {r['name']:20s} "
              f"{r['length']:5.0f}x{r['width']:5.0f}x{r['height']:5.0f} "
              f"{r['weight_kg']:6.1f}kg stack={r['allow_stacking']} rot={r['allow_rotation']}")
    print(f"    Total packages: {total}")

print("\n=== LOAD PLANS ===")
c.execute("""
    SELECT lp.id, lp.name, lp.vehicle_id, lp.shipment_id, lp.status
    FROM tlp_load_plans lp ORDER BY lp.id
""")
for r in c.fetchall():
    c.execute("SELECT COUNT(*) AS cnt FROM tlp_placements WHERE load_plan_id = ?", (r["id"],))
    pc = c.fetchone()["cnt"]
    print(f"  id={r['id']} name={r['name']} vehicle={r['vehicle_id']} "
          f"shipment={r['shipment_id']} status={r['status']} placements={pc}")

conn.close()
