from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import config
import db

app = FastAPI(title="HF embodied survey")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
def trending_page(request: Request, day: str | None = None):
    conn = db.connect()
    days = db.trending_days(conn)
    run_date = day if day in [d[0] for d in days] else (days[-1][0] if days else None)
    board = db.trending_board(conn, run_date, 100) if run_date else []
    n_emb = sum(row[8] for row in board)
    s = db.summary(conn)
    conn.close()
    return templates.TemplateResponse(request, "trending.html", {
        "days": days, "run_date": run_date, "board": board,
        "n_emb": n_emb, "summary": s})


@app.get("/users", response_class=HTMLResponse)
def users_page(request: Request):
    conn = db.connect()
    people = db.top_users(conn, config.BULK_UPLOADER_MIN_MODELS, config.TOP_V)
    orgs = db.top_orgs(conn, 10)
    by_in, by_out, by_total = db.degree_boards(conn, 12)
    s = db.summary(conn)
    conn.close()
    return templates.TemplateResponse(request, "users.html", {
        "people": people, "orgs": orgs, "by_in": by_in, "by_out": by_out,
        "by_total": by_total, "s": s})


@app.get("/projects", response_class=HTMLResponse)
def projects_page(request: Request):
    conn = db.connect()
    rows = db.project_rows(conn, config.PROJECT_POOL)
    conn.close()
    return templates.TemplateResponse(request, "projects.html", {"rows": rows})


@app.get("/notes", response_class=HTMLResponse)
def notes_page(request: Request):
    text = Path("README.md").read_text(encoding="utf-8") if Path("README.md").exists() else ""
    return templates.TemplateResponse(request, "notes.html", {"text": text})