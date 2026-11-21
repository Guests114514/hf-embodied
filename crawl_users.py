import time

import config
import db
from hfapi import fetch, fetch_or_none, save_raw, today


def collect_candidates(conn, run_date):
    queries = [
        ("/api/models", {"pipeline_tag": "robotics", "full": "true",
                         "sort": "trendingScore", "direction": "-1", "limit": "100"}, "model"),
        ("/api/datasets", {"search": "robot manipulation", "sort": "likes",
                           "direction": "-1", "limit": "100"}, "dataset"),
        ("/api/spaces", {"search": "robotics", "full": "true", "limit": "100"}, "space"),
    ]
    for kw in config.KEYWORDS:
        queries.append(("/api/models", {"search": kw, "full": "true", "sort": "likes",
                                        "direction": "-1", "limit": "50"}, "model"))

    likes_by_author = {}
    for i, (path, params, kind) in enumerate(queries):
        data = fetch(path, params)
        save_raw(f"pool{i:02d}_{kind}", data)
        for item in data:
            author = item.get("author")
            if not author:
                continue
            likes_by_author[author] = likes_by_author.get(author, 0) + (item.get("likes") or 0)
            db.upsert_repo(conn, item, kind)
        time.sleep(config.SLEEP)
    conn.commit()
    return likes_by_author


def split_authors(conn, run_date, likes_by_author, failures, robot_orgs):
    users, orgs = [], []
    for i, name in enumerate(sorted(likes_by_author), start=1):
        try:
            info = fetch_or_none(f"/api/users/{name}/overview")
        except Exception as e:
            failures.append((name, type(e).__name__))
            continue
        if info is None:
            orgs.append(name)
        else:
            users.append(name)
            their_orgs = [o.get("name") for o in (info.get("orgs") or [])]
            n_robot = len([o for o in their_orgs if o in robot_orgs])
            db.upsert_user(conn, name, info, run_date, "author", n_robot)
        if i % 25 == 0:
            conn.commit()
            print(f"  split 已处理 {i} 个作者，累计失败 {len(failures)}")
        time.sleep(config.SLEEP)
    conn.commit()
    return users, orgs


def main():
    run_date = today()
    conn = db.connect()
    db.init(conn)
    failures = []

    likes_by_author = collect_candidates(conn, run_date)
    robot_orgs = db.embodied_orgs(conn, config.MIN_ORG_RATIO)
    users, orgs = split_authors(conn, run_date, likes_by_author, failures, robot_orgs)
    conn.commit()

    if failures:
        save_raw("failures", failures)
        print(f"有 {len(failures)} 个账号没抓到，清单在 raw/failures.json")
    n_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    n_repos = conn.execute("SELECT COUNT(*) FROM repos").fetchone()[0]
    print(f"{run_date}: 候选作者 {len(likes_by_author)} | 个人账号 {len(users)} "
          f"| 机构号 {len(orgs)}（成员展开交给 crawl_members.py）"
          f"|| users={n_users} repos={n_repos}")
    conn.close()


if __name__ == "__main__":
    main()