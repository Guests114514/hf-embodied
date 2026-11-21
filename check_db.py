import sqlite3

import db

conn = sqlite3.connect(":memory:")
db.init(conn)
for table in ("runs", "repos", "trending_daily", "users", "edges", "labels"):
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    print(f"{table}({len(cols)}): {cols}")
conn.close()