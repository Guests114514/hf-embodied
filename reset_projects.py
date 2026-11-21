import db

conn = db.connect()
n = conn.execute("DROP TABLE IF EXISTS projects").rowcount
conn.commit()
print("已删除 projects 表，下次 crawl_projects 会按新 SCHEMA 重建")
conn.close()