import time

import config
import db
from hfapi import fetch_or_none, save_raw, today

LIST_CAP = 500


def name_of(item):
    """列表项可能是纯用户名字符串，也可能是带 user 字段的字典，两种都要接住。"""
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return None
    return item.get("user") or item.get("username") or item.get("name")


def crawl_one(conn, name, direction, run_date, done):
    if (name, direction) in done:
        return "跳过"
    items = fetch_or_none(f"/api/users/{name}/{direction}")
    if items is None:
        return "404"
    save_raw(f"edges_{name}_{direction}", items)
    n = 0
    for item in items:
        other = name_of(item)
        if not other or other == name:
            continue
        if direction == "following":
            db.add_edge(conn, name, other, "follow", run_date)
        else:
            db.add_edge(conn, other, name, "follow", run_date)
        n += 1
    db.mark_crawled(conn, name, direction, run_date, n)
    done.add((name, direction))
    return f"{n} 截断!" if n >= LIST_CAP else n


def pick_hubs(conn, seed_set):
    """候选：非种子、且与种子有两条以上边的节点。"""
    rows = db.degrees(conn)
    cands = [r[0] for r in rows
             if r[0] not in seed_set and (r[1] >= 2 or r[2] >= 2)]
    cands.sort(key=lambda n: -max(dict((r[0], (r[1], r[2])) for r in rows)[n]))
    return cands


def hub_gate(name):
    """返回 None 表示可以展开，否则返回跳过原因。这里多花一个请求换数据完整。"""
    info = fetch_or_none(f"/api/users/{name}/overview")
    if info is None:
        return "overview 404"
    n_followers = info.get("numFollowers") or 0
    n_following = info.get("numFollowing") or 0
    if n_followers >= LIST_CAP or n_following >= LIST_CAP:
        return f"粉丝 {n_followers} / 关注 {n_following}，超 {LIST_CAP} 会截断"
    if n_followers < 10:
        return f"粉丝只有 {n_followers}，像互关注册号"
    return None


def run_round(conn, names, run_date, done, failures):
    for name in names:
        parts = []
        for direction in ("following", "followers"):
            try:
                r = crawl_one(conn, name, direction, run_date, done)
            except Exception as e:
                r = None
                failures.append((name, direction, type(e).__name__))
            parts.append(f"{direction}={r}")
            time.sleep(config.SLEEP)
        print(f"  {name}: " + " ".join(parts))
        conn.commit()


def main():
    run_date = today()
    conn = db.connect()
    db.init(conn)
    done = db.crawled_pairs(conn)
    failures = []

    seeds = [row[0] for row in
             db.top_users(conn, config.BULK_UPLOADER_MIN_MODELS, config.TOP_V)]
    print(f"一跳种子 {len(seeds)} 个：{seeds}")
    run_round(conn, seeds, run_date, done, failures)

    seed_set = set(seeds)
    hubs = []
    for name in pick_hubs(conn, seed_set):
        if len(hubs) >= config.HOP2:
            break
        reason = hub_gate(name)
        if reason:
            print(f"  跳过枢纽 {name}: {reason}")
            continue
        hubs.append(name)
    print(f"二跳枢纽 {len(hubs)} 个：{hubs}")
    run_round(conn, hubs, run_date, done, failures)

    n_edges = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    n_nodes = conn.execute(
        "SELECT COUNT(*) FROM (SELECT src FROM edges UNION SELECT dst FROM edges)"
    ).fetchone()[0]
    n_trunc = conn.execute(
        "SELECT COUNT(*) FROM crawled WHERE n_rows >= ?", (LIST_CAP,)).fetchone()[0]
    if failures:
        save_raw("failures_edges", failures)
    print(f"edges={n_edges} 节点={n_nodes} 已抓取列表={len(done)} "
          f"其中截断={n_trunc} 失败={len(failures)}")
    conn.close()


if __name__ == "__main__":
    main()