import glob
import json
import os

import config
import db

PATTERNS = ("pool*.json", "models_trending*.json")


def main():
    conn = db.connect()
    db.init(conn)
    if "tags" not in [row[1] for row in conn.execute("PRAGMA table_info(repos)")]:
        conn.execute("ALTER TABLE repos ADD COLUMN tags TEXT")
        print("已给 repos 加 tags 列")

    tags_by_repo = {}
    n_files = 0
    for pattern in PATTERNS:
        for path in sorted(glob.glob(os.path.join(config.RAW_DIR, pattern))):
            n_files += 1
            with open(path, encoding="utf-8") as f:
                items = json.load(f)
            for item in items:
                repo_id = item.get("id")
                tags = ",".join(item.get("tags") or [])
                if repo_id and tags:
                    tags_by_repo[repo_id] = tags

    n_upd = 0
    for repo_id, tags in tags_by_repo.items():
        n_upd += conn.execute(
            "UPDATE repos SET tags = ? WHERE repo_id = ?", (tags, repo_id)
        ).rowcount
    conn.commit()

    have = conn.execute(
        "SELECT COUNT(*) FROM repos WHERE tags IS NOT NULL AND tags != ''").fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM repos").fetchone()[0]
    print(f"读 {n_files} 个 raw 文件，更新 {n_upd} 行；有 tags 的仓库 {have}/{total}")
    conn.close()


if __name__ == "__main__":
    main()