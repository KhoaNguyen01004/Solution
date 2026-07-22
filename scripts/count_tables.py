"""Count rows in each table."""
import os, sqlite3
_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "routing_system.db")
conn = sqlite3.connect(_db_path)
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in c.fetchall()]
for t in tables:
    c.execute(f'SELECT COUNT(*) FROM "{t}"')
    cnt = c.fetchone()[0]
    print(f"  {t:30s}: {cnt} rows")

conn.close()
