import collections
import re
import time

import requests

import config
import db
from hfapi import fetch, fetch_text, save_raw, save_text, today

GITHUB_RE = re.compile(r"github\.com/([A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+)")
PREFIX = {"model": "", "dataset": "datasets/", "space": "spaces/"}


def readme_text(kind, repo_id):
    """返回 (正文, 说明)。拿不到正文也要留下原因，网页上要显示为什么这行是空的。"""
    prefix = PREFIX[kind]
    for branch in ("main", "master"):
        text = fetch_text(f"/{prefix}{repo_id}/raw/{branch}/README.md")
        if text:
            return text, ""
    return "", "README 匿名不可读"


def pick_github(text):
    """README 里的 github.com 链接取出现次数最多的那个，而不是第一个。

    卡片里第一个链接常常是 shields 徽章或作者主页，出现次数最多的才是项目本体仓库。
    """
    slugs = []
    for raw in GITHUB_RE.findall(text):
        slug = raw.rstrip("/").removesuffix(".git")
        if slug.count("/") == 1:
            slugs.append(slug)
    counter = collections.Counter(slugs)
    best = counter.most_common(1)[0][0] if counter else None
    return counter, best


def gh_stars(slug):
    if not slug:
        return None
    resp = requests.get(f"https://api.github.com/repos/{slug}",
                        headers=config.HEADERS, timeout=30)
    if resp.status_code != 200:
        return None
    return resp.json().get("stargazers_count")


def space_ids(detail):
    out = []
    for item in detail.get("spaces") or []:
        name = item if isinstance(item, str) else (item.get("id") or item.get("name"))
        if name:
            out.append(name)
    return out


def main():
    run_date = today()
    conn = db.connect()
    db.init(conn)

    rows = conn.execute(
        "SELECT r.repo_id, r.kind, r.likes, r.trending_score "
        "FROM repos r JOIN labels l ON l.repo_id = r.repo_id AND l.source = 'keyword' "
        "WHERE l.is_embodied = 1 "
        "ORDER BY COALESCE(r.likes, 0) DESC LIMIT ?",
        (config.PROJECT_POOL,),
    ).fetchall()
    print(f"具身候选仓库 {len(rows)} 个，按 likes 取前 {config.PROJECT_POOL}")

    for rank, (repo_id, kind, likes, trending_score) in enumerate(rows, start=1):
        note = ""
        counter = collections.Counter()
        slug = stars = None
        spaces = []
        try:
            detail = fetch(f"/api/{kind}s/{repo_id}")
            save_raw(f"detail_{repo_id.replace('/', '_')}", detail)
            if detail.get("gated"):
                note = f"受限仓库 gated={detail.get('gated')}"
            text, why = readme_text(kind, repo_id)
            if text:
                save_text(f"readme_{repo_id.replace('/', '_')}", text)
                counter, slug = pick_github(text)
                if not slug:
                    note = "README 里没有 github.com 链接"
            elif not note:
                note = why
            stars = gh_stars(slug)
            spaces = space_ids(detail)
        except Exception as e:
            note = f"抓取失败 {type(e).__name__}: {e}"

        db.upsert_project(conn, rank, repo_id, kind, likes, trending_score, slug,
                          stars, len(spaces), ",".join(spaces[:3]),
                          ";".join(f"{s}:{n}" for s, n in counter.most_common(3)),
                          note, run_date)
        print(f"  {rank:2d} {repo_id} likes={likes} gh={slug or '-'} "
              f"stars={stars} spaces={len(spaces)} {note}")
        if counter:
            print(f"      候选 {counter.most_common(3)}")
        conn.commit()
        time.sleep(config.SLEEP)

    n = conn.execute("SELECT COUNT(*) FROM projects WHERE github IS NOT NULL").fetchone()[0]
    print(f"projects 表 {len(rows)} 行，其中带 GitHub 链接 {n} 行")
    conn.close()


if __name__ == "__main__":
    main()