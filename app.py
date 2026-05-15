"""
Reddit 本地爬取站 - FastAPI 后端
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from typing import List, Optional

import database
from scraper_runner import scraper_runner

app = FastAPI(title="Reddit 本地爬取站")

# Static files
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)


class ConfigModel(BaseModel):
    interval_minutes: int = 60
    targets: str = ""
    post_types: str = "text,image,video,gallery,link"
    fetch_images: int = 1
    fetch_videos: int = 0
    fetch_comments: int = 1
    limit_per_target: int = 100


@app.on_event("startup")
def startup():
    database.init_db()


# --- Config ---
@app.get("/api/config")
def get_config():
    return database.get_config()


@app.post("/api/config")
def save_config(config: ConfigModel):
    database.save_config(config.dict())
    return {"ok": True}


# --- Scraper control ---
@app.post("/api/scrape/start")
def start_scrape():
    ok = scraper_runner.start()
    if not ok:
        raise HTTPException(400, "Already running")
    return {"ok": True}


@app.post("/api/scrape/stop")
def stop_scrape():
    scraper_runner.stop()
    return {"ok": True}


@app.get("/api/scrape/status")
def scrape_status():
    return scraper_runner.status


# --- Posts ---
@app.get("/api/posts")
def get_posts(status: str = "pending", page: int = 1,
              sort_by: str = "scraped_at", sort_order: str = "desc",
              sources: Optional[str] = None, search: Optional[str] = None):
    source_list = [s for s in sources.split(",") if s] if sources else None
    posts, total = database.get_posts_by_status(status, page, sort_by=sort_by,
                                                 sort_order=sort_order, sources=source_list,
                                                 search=search)
    return {"posts": posts, "total": total, "page": page, "per_page": 20}


@app.get("/api/sources")
def get_sources():
    return database.get_all_sources()


@app.get("/api/preferences/sources")
def get_preferred_sources():
    return database.get_selected_sources()


class SourcePreferences(BaseModel):
    selected_sources: List[str] = []
    select_mode: str = "single"


@app.post("/api/preferences/sources")
def save_preferred_sources(prefs: SourcePreferences):
    database.save_selected_sources(prefs.selected_sources, prefs.select_mode)
    return {"ok": True}


@app.get("/api/posts/{post_id}")
def get_post(post_id: int):
    post = database.get_post_detail(post_id)
    if not post:
        raise HTTPException(404, "Not found")
    return post


@app.post("/api/posts/{post_id}/sync")
def sync_post(post_id: int):
    database.update_post_status(post_id, "to_sync")
    return {"ok": True}


@app.post("/api/posts/{post_id}/delete")
def delete_post(post_id: int):
    database.update_post_status(post_id, "deleted")
    return {"ok": True}


@app.post("/api/posts/{post_id}/publish")
def publish_post(post_id: int):
    database.update_post_status(post_id, "synced")
    return {"ok": True}


# --- Logs ---
@app.get("/api/logs")
def get_logs(page: int = 1):
    logs, total = database.get_scrape_logs(page)
    return {"logs": logs, "total": total, "page": page}


# --- Tags & Favorites ---

class FavoriteRequest(BaseModel):
    post_id: int
    tags: List[str] = []


@app.get("/api/tags")
def get_tags():
    return {"tags": database.get_all_tags()}


@app.post("/api/tags")
def create_tag(data: dict):
    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(400, "Tag name required")
    tag = database.create_tag(name)
    return {"tag": tag}


@app.get("/api/favorites")
def get_favorites(page: int = 1, search: Optional[str] = None):
    favs, total = database.get_favorites(page, search=search)
    return {"favorites": favs, "total": total, "page": page}


@app.post("/api/favorites")
def add_favorite(req: FavoriteRequest):
    fav_id = database.add_favorite(req.post_id, req.tags)
    if not fav_id:
        raise HTTPException(404, "Post not found")
    return {"ok": True, "id": fav_id}


@app.delete("/api/favorites/{fav_id}")
def delete_favorite(fav_id: int):
    database.delete_favorite(fav_id)
    return {"ok": True}


@app.get("/api/favorites/count")
def favorites_count():
    return {"count": database.get_favorites_count()}


# --- Static files ---
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn
    import webbrowser
    import threading
    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:8080")).start()
    uvicorn.run(app, host="0.0.0.0", port=8080)
