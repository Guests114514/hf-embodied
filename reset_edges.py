import db

conn = db.connect()
n_edges = conn.execute("DELETE FROM edges").rowcount
n_crawled = conn.execute("DELETE FROM crawled").rowcount
conn.commit()
print(f"清空 edges {n_edges} 行、crawled {n_crawled} 行")
conn.close()