import sqlite3

import db

conn = sqlite3.connect(":memory:")
db.init(conn)
tables = [row[0] for row in conn.execute(
    "SELECT name FROM sqlite_master WHERE type = 'table' "
    "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
for table in tables:
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    print(f"{table}({len(cols)}): {cols}")
conn.close()