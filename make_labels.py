import sqlite3

import config
import db
from hfapi import today

HARD_TAGS = ["robotics", "arxiv:cs.ro"]
SOFT_TERMS = ["embodied", "robot", "manipulat", "locomot", "teleop", "dexterous",
              "vla", "gr00t", "groot", "imitation", "sim2real", "lerobot",
              "world-model", "worldmodel", "world model", "humanoid", "navigation"]
MIN_SOFT = 2


def hit_count(text, terms):
    count = 0
    for term in terms:
        if term in text:
            count += 1
    return count


def main():
    conn = db.connect()
    db.init(conn)

    rows = conn.execute(
        "SELECT repo_id, pipeline_tag, tags FROM repos"
    ).fetchall()

    for repo_id, pipeline_tag, tags in rows:
        text = f"{(tags or '')},{(repo_id or '').lower()},{(pipeline_tag or '').lower()}"
        hard = any(term in text for term in HARD_TAGS)
        soft = hit_count(text, SOFT_TERMS)
        is_embodied = 1 if (hard or soft >= MIN_SOFT) else 0
        label = "hard" if hard else f"soft{soft}"
        conn.execute(
            "INSERT INTO labels (repo_id, source, label, is_embodied, model_used, created_at) "
            "VALUES (?, 'keyword', ?, ?, NULL, ?) "
            "ON CONFLICT(repo_id, source) DO UPDATE SET "
            "label=excluded.label, is_embodied=excluded.is_embodied, "
            "created_at=excluded.created_at",
            (repo_id, label, is_embodied, today()),
        )
    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM labels WHERE source='keyword'").fetchone()[0]
    yes = conn.execute(
        "SELECT COUNT(*) FROM labels WHERE source='keyword' AND is_embodied=1"
    ).fetchone()[0]
    print(f"标注 {total} 个仓库，判为具身 {yes} 个（{yes / max(total, 1):.0%}）")

    print("=== 具身仓库数最多的作者前 25（这是下一步该用的排序）===")
    for row in conn.execute(
        "SELECT r.author, COUNT(*) AS n_embodied, COALESCE(SUM(r.likes), 0) AS emb_likes "
        "FROM repos r JOIN labels l ON l.repo_id = r.repo_id AND l.source = 'keyword' "
        "WHERE l.is_embodied = 1 GROUP BY r.author ORDER BY n_embodied DESC, emb_likes DESC "
        "LIMIT 25"
    ):
        print(row)

    print("=== 被判为非具身但池内 likes 最高的前 10（检查有没有误杀）===")
    for row in conn.execute(
        "SELECT r.repo_id, r.author, r.likes, l.label FROM repos r "
        "JOIN labels l ON l.repo_id = r.repo_id AND l.source = 'keyword' "
        "WHERE l.is_embodied = 0 ORDER BY r.likes DESC LIMIT 10"
    ):
        print(row)
    conn.close()


if __name__ == "__main__":
    main()