import sqlite3
import config
SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date TEXT NOT NULL,
    source TEXT NOT NULL,
    n_rows INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS repos (
    repo_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    author TEXT,
    likes INTEGER,
    downloads INTEGER,
    trending_score REAL,
    pipeline_tag TEXT,
    created_at TEXT,
    last_modified TEXT,
    tags TEXT
);
CREATE TABLE IF NOT EXISTS trending_daily (
    run_date TEXT NOT NULL,
    pos INTEGER NOT NULL,
    repo_id TEXT NOT NULL REFERENCES repos(repo_id),
    trending_score REAL,
    likes INTEGER,
    downloads INTEGER,
    PRIMARY KEY (run_date, repo_id)
);
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    fullname TEXT,
    type TEXT,
    num_followers INTEGER,
    num_following INTEGER,
    num_following_orgs INTEGER,
    num_models INTEGER,
    num_datasets INTEGER,
    num_spaces INTEGER,
    last_seen_date TEXT,
    source TEXT,
    n_orgs INTEGER,
    n_robot_orgs INTEGER
);

CREATE TABLE IF NOT EXISTS edges (
    src TEXT NOT NULL,
    dst TEXT NOT NULL,
    kind TEXT NOT NULL,
    first_seen_date TEXT,
    PRIMARY KEY (src, dst, kind)
);

CREATE TABLE IF NOT EXISTS labels (
    repo_id TEXT NOT NULL,
    source TEXT NOT NULL,
    label TEXT,
    is_embodied INTEGER,
    model_used TEXT,
    created_at TEXT,
    PRIMARY KEY (repo_id, source)
);
CREATE TABLE IF NOT EXISTS projects (
    repo_id TEXT PRIMARY KEY,
    rank INTEGER,
    kind TEXT,
    likes INTEGER,
    trending_score REAL,
    github TEXT,
    github_stars INTEGER,
    n_spaces INTEGER,
    spaces TEXT,
    candidates TEXT,
    note TEXT,
    run_date TEXT
);
CREATE TABLE IF NOT EXISTS crawled (
    username TEXT NOT NULL,
    direction TEXT NOT NULL,
    run_date TEXT,
    n_rows INTEGER,
    PRIMARY KEY (username, direction)
);
"""
def connect():
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
def init(conn):
    conn.executescript(SCHEMA)
    conn.commit()
def log_run(conn, run_date, source, n_rows):
    cur = conn.execute(
        "INSERT INTO runs (run_date, source, n_rows) VALUES (?, ?, ?)",
        (run_date, source, n_rows),
    )
    return cur.lastrowid
def upsert_repo(conn, item, kind):
    conn.execute(
        """
        INSERT INTO repos (repo_id, kind, author, likes, downloads,
                           trending_score, pipeline_tag, created_at, last_modified, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(repo_id) DO UPDATE SET
            author=excluded.author,
            likes=excluded.likes,
            downloads=excluded.downloads,
            trending_score=excluded.trending_score,
            pipeline_tag=excluded.pipeline_tag,
            created_at=excluded.created_at,
            last_modified=excluded.last_modified,
            tags=excluded.tags
        """,
        (item["id"], kind, item.get("author"), item.get("likes"),
         item.get("downloads"), item.get("trendingScore"), item.get("pipeline_tag"),
         item.get("createdAt"), item.get("lastModified"),
         ",".join(item.get("tags") or [])),
    )
def upsert_trending(conn, run_date, pos, item):
    conn.execute(
        """
        INSERT INTO trending_daily (run_date, pos, repo_id, trending_score, likes, downloads)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_date, repo_id) DO UPDATE SET
            pos=excluded.pos,
            trending_score=excluded.trending_score,
            likes=excluded.likes,
            downloads=excluded.downloads
        """,
        (run_date, pos, item["id"], item.get("trendingScore"),
         item.get("likes"), item.get("downloads")),
    )
def clear_trending(conn, run_date):
    conn.execute("DELETE FROM trending_daily WHERE run_date = ?", (run_date,))
def embodied_orgs(conn, min_ratio):
    """通过具身占比检验的机构名集合，用来数一个人跨了几家具身机构。"""
    rows = conn.execute(
        "SELECT r.author, COUNT(*) AS n_pool, "
        "  SUM(CASE WHEN l.is_embodied = 1 THEN 1 ELSE 0 END) AS n_emb "
        "FROM repos r JOIN labels l ON l.repo_id = r.repo_id AND l.source = 'keyword' "
        "WHERE r.author IS NOT NULL "
        "GROUP BY r.author "
        "HAVING n_emb >= 1 AND n_emb * 1.0 / n_pool >= ?",
        (min_ratio,),
    ).fetchall()
    return {row[0] for row in rows}
def upsert_user(conn, name, info, run_date, source, n_robot_orgs):
    orgs = info.get("orgs") or []
    conn.execute(
        """
        INSERT INTO users (username, fullname, type, num_followers, num_following,
                           num_following_orgs, num_models, num_datasets, num_spaces,
                           last_seen_date, source, n_orgs, n_robot_orgs)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(username) DO UPDATE SET
            fullname=excluded.fullname,
            num_followers=excluded.num_followers,
            num_following=excluded.num_following,
            num_following_orgs=excluded.num_following_orgs,
            num_models=excluded.num_models,
            num_datasets=excluded.num_datasets,
            num_spaces=excluded.num_spaces,
            last_seen_date=excluded.last_seen_date,
            source=excluded.source,
            n_orgs=excluded.n_orgs,
            n_robot_orgs=excluded.n_robot_orgs
        """,
        (name, info.get("fullname"), info.get("type"), info.get("numFollowers"),
         info.get("numFollowing"), info.get("numFollowingOrgs"), info.get("numModels"),
         info.get("numDatasets"), info.get("numSpaces"), run_date, source,
         len(orgs), n_robot_orgs),
    )

def add_edge(conn, src, dst, kind, run_date):
    conn.execute(
        """
        INSERT INTO edges (src, dst, kind, first_seen_date)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(src, dst, kind) DO UPDATE SET
            first_seen_date=excluded.first_seen_date
        """,
        (src, dst, kind, run_date),
    )
def upsert_project(conn, rank, repo_id, kind, likes, trending_score, github,
                   github_stars, n_spaces, spaces, candidates, note, run_date):
    conn.execute(
        """
        INSERT INTO projects (repo_id, rank, kind, likes, trending_score, github,
                              github_stars, n_spaces, spaces, candidates, note, run_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(repo_id) DO UPDATE SET
            rank=excluded.rank,
            kind=excluded.kind,
            likes=excluded.likes,
            trending_score=excluded.trending_score,
            github=excluded.github,
            github_stars=excluded.github_stars,
            n_spaces=excluded.n_spaces,
            spaces=excluded.spaces,
            candidates=excluded.candidates,
            note=excluded.note,
            run_date=excluded.run_date
        """,
        (repo_id, rank, kind, likes, trending_score, github, github_stars,
         n_spaces, spaces, candidates, note, run_date),
    )
DEG_SQL = """
WITH arc AS (
    SELECT src AS u, 1 AS out_d, 0 AS in_d FROM edges WHERE kind = 'follow'
    UNION ALL
    SELECT dst AS u, 0 AS out_d, 1 AS in_d FROM edges WHERE kind = 'follow'
)
SELECT u, SUM(in_d) AS in_deg, SUM(out_d) AS out_deg, COUNT(*) AS total
FROM arc GROUP BY u
"""


def degrees(conn):
    """度数只在抓过的方向上成立：未抓 following 的节点，出度是低估的。"""
    return conn.execute(DEG_SQL).fetchall()


def crawled_pairs(conn):
    return {(r[0], r[1]) for r in conn.execute(
        "SELECT username, direction FROM crawled")}


def mark_crawled(conn, name, direction, run_date, n_rows):
    conn.execute(
        """
        INSERT INTO crawled (username, direction, run_date, n_rows)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(username, direction) DO UPDATE SET
            run_date=excluded.run_date,
            n_rows=excluded.n_rows
        """,
        (name, direction, run_date, n_rows),
    )
TOP_USERS_SQL = """
SELECT u.username, u.num_followers, u.source, u.n_orgs, u.n_robot_orgs,
  (SELECT COUNT(*) FROM repos r JOIN labels l ON l.repo_id = r.repo_id
     AND l.source = 'keyword'
     WHERE r.author = u.username AND l.is_embodied = 1) AS n_emb,
  (SELECT COALESCE(SUM(r.likes), 0) FROM repos r JOIN labels l
     ON l.repo_id = r.repo_id AND l.source = 'keyword'
     WHERE r.author = u.username AND l.is_embodied = 1) AS emb_likes
FROM users u
WHERE COALESCE(u.num_models, 0) < ?
  AND (n_emb >= 1 OR u.n_robot_orgs >= 2)
ORDER BY u.num_followers DESC
LIMIT ?
"""


def top_users(conn, min_models, limit):
    return conn.execute(TOP_USERS_SQL, (min_models, limit)).fetchall()
def top_orgs(conn, limit):
    return conn.execute(
        "SELECT r.author, COUNT(*) AS n_emb, COALESCE(SUM(r.likes), 0) AS emb_likes "
        "FROM repos r JOIN labels l ON l.repo_id = r.repo_id AND l.source = 'keyword' "
        "WHERE l.is_embodied = 1 AND r.author NOT IN (SELECT username FROM users) "
        "GROUP BY r.author ORDER BY emb_likes DESC LIMIT ?",
        (limit,),
    ).fetchall()


def trending_days(conn):
    return conn.execute(
        "SELECT run_date, COUNT(*) FROM trending_daily "
        "GROUP BY run_date ORDER BY run_date"
    ).fetchall()


def trending_board(conn, run_date, limit):
    return conn.execute(
        "SELECT t.pos, t.repo_id, r.kind, r.author, t.likes, t.trending_score, "
        "  r.downloads, r.pipeline_tag, COALESCE(l.is_embodied, 0) AS is_embodied "
        "FROM trending_daily t "
        "JOIN repos r ON r.repo_id = t.repo_id "
        "LEFT JOIN labels l ON l.repo_id = t.repo_id AND l.source = 'keyword' "
        "WHERE t.run_date = ? ORDER BY t.pos LIMIT ?",
        (run_date, limit),
    ).fetchall()


def project_rows(conn, limit):
    return conn.execute(
        "SELECT rank, repo_id, kind, likes, github, github_stars, n_spaces, spaces, "
        "  candidates, note FROM projects ORDER BY rank LIMIT ?",
        (limit,),
    ).fetchall()


def degree_boards(conn, limit):
    rows = degrees(conn)
    by_in = sorted(rows, key=lambda r: (-r[1], -r[3]))[:limit]
    by_out = sorted(rows, key=lambda r: (-r[2], -r[3]))[:limit]
    by_total = sorted(rows, key=lambda r: (-r[3], -r[1]))[:limit]
    return by_in, by_out, by_total


def summary(conn):
    one = lambda sql, *a: conn.execute(sql, a).fetchone()[0]
    return {
        "repos": one("SELECT COUNT(*) FROM repos"),
        "embodied": one(
            "SELECT COUNT(*) FROM labels WHERE is_embodied = 1 AND source = 'keyword'"),
        "users": one("SELECT COUNT(*) FROM users"),
        "edges": one("SELECT COUNT(*) FROM edges"),
        "nodes": one(
            "SELECT COUNT(*) FROM (SELECT src FROM edges UNION SELECT dst FROM edges)"),
        "crawled": one("SELECT COUNT(*) FROM crawled"),
        "truncated": one("SELECT COUNT(*) FROM crawled WHERE n_rows >= 500"),
        "days": one("SELECT COUNT(DISTINCT run_date) FROM trending_daily"),
        "runs": one("SELECT COUNT(*) FROM runs"),
    }