import config
import db
from hfapi import fetch, save_raw, today


def main():
    params = {"sort": "trendingScore", "direction": -1,
              "limit": config.SNAPSHOT_LIMIT, "full": "true"}
    data = fetch("/api/models", params)
    run_date = today()
    save_raw(f"models_trending_{run_date}", data)

    conn = db.connect()
    db.init(conn)
    db.clear_trending(conn, run_date)
    for item in data:
        db.upsert_repo(conn, item, "model")
    for pos, item in enumerate(data, start=1):
        db.upsert_trending(conn, run_date, pos, item)
    run_id = db.log_run(conn, run_date, "models_trending", len(data))
    conn.commit()

    n_repos = conn.execute("SELECT COUNT(*) FROM repos").fetchone()[0]
    n_today = conn.execute(
        "SELECT COUNT(*) FROM trending_daily WHERE run_date = ?", (run_date,)
    ).fetchone()[0]
    n_dates = conn.execute("SELECT COUNT(DISTINCT run_date) FROM trending_daily").fetchone()[0]
    print(f"run_id={run_id} {run_date} 抓到 {len(data)} 条 | "
          f"repos={n_repos} 今日榜单={n_today} 已有天数={n_dates}")
    conn.close()


if __name__ == "__main__":
    main()