import time

import config
import db
from hfapi import fetch_or_none, save_raw, today


def org_stats(conn):
    """池内作者里没进 users 表的是机构号，带上具身仓库数与具身 likes。"""
    return conn.execute(
        "SELECT r.author, COUNT(*) AS n_pool, "
        "  SUM(CASE WHEN l.is_embodied = 1 THEN 1 ELSE 0 END) AS n_embodied, "
        "  COALESCE(SUM(CASE WHEN l.is_embodied = 1 THEN r.likes ELSE 0 END), 0) AS emb_likes "
        "FROM repos r JOIN labels l ON l.repo_id = r.repo_id AND l.source = 'keyword' "
        "WHERE r.author IS NOT NULL AND r.author NOT IN (SELECT username FROM users) "
        "GROUP BY r.author ORDER BY n_embodied DESC, emb_likes DESC LIMIT 40"
    ).fetchall()


def org_check(n_pool, n_embodied, emb_likes):
    if n_embodied < config.MIN_ORG_EMBODIED:
        return False, f"具身仓库 {n_embodied} < {config.MIN_ORG_EMBODIED}"
    ratio = n_embodied / n_pool
    if ratio < config.MIN_ORG_RATIO:
        return False, f"具身占比 {n_embodied}/{n_pool} = {ratio:.0%} 偏低"
    if emb_likes < config.MIN_ORG_EMBLIKES:
        return False, f"具身 likes 合计 {emb_likes} < {config.MIN_ORG_EMBLIKES}（像投稿账号）"
    return True, f"具身 {n_embodied}/{n_pool} = {ratio:.0%}，likes {emb_likes}"


def main():
    run_date = today()
    conn = db.connect()
    db.init(conn)

    n_del = conn.execute("DELETE FROM users WHERE source LIKE 'member:%'").rowcount
    conn.commit()
    print(f"清掉旧判据的 member 账号 {n_del} 行")

    robot_orgs = db.embodied_orgs(conn, config.MIN_ORG_RATIO)
    print(f"通过占比检验的具身机构共 {len(robot_orgs)} 家")

    failures = []
    expanded = []
    for author, n_pool, n_embodied, emb_likes in org_stats(conn):
        if len(expanded) >= config.MAX_ORGS:
            break
        ok, why = org_check(n_pool, n_embodied, emb_likes)
        if not ok:
            print(f"  跳过 {author}: {why}")
            continue
        try:
            members = fetch_or_none(f"/api/organizations/{author}/members") or []
        except Exception as e:
            failures.append((author, type(e).__name__))
            continue
        time.sleep(config.SLEEP)
        if not members:
            print(f"  跳过 {author}: 合格但拿不到成员列表")
            continue
        if len(members) > config.MAX_MEMBERS_PER_ORG:
            print(f"  跳过 {author}: {why}，但成员 {len(members)} 人 > {config.MAX_MEMBERS_PER_ORG}")
            continue

        save_raw(f"members_{author}", members)
        print(f"  展开 {author}: {why}，成员 {len(members)} 人")
        found = 0
        for m in members:
            name = m.get("user")
            if not name:
                continue
            try:
                info = fetch_or_none(f"/api/users/{name}/overview")
            except Exception as e:
                failures.append((name, type(e).__name__))
                continue
            if info is not None:
                their_orgs = [o.get("name") for o in (info.get("orgs") or [])]
                n_robot = len([o for o in their_orgs
                               if o in robot_orgs and o != author])
                db.upsert_user(conn, name, info, run_date, f"member:{author}", n_robot)
                found += 1
            time.sleep(config.SLEEP)
        conn.commit()
        expanded.append((author, found))

    if failures:
        save_raw("failures_members", failures)
    print(f"展开 {len(expanded)} 家：{expanded} | 失败 {len(failures)}")
    conn.close()


if __name__ == "__main__":
    main()