"""
Reddit 本地爬取站 - 数据库层
"""
import sqlite3
import os
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "reddit_local.db"


def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reddit_id TEXT UNIQUE,
            title TEXT,
            author TEXT,
            selftext TEXT,
            permalink TEXT,
            url TEXT,
            source TEXT DEFAULT '',
            word_count INTEGER DEFAULT 0,
            score INTEGER DEFAULT 0,
            num_comments INTEGER DEFAULT 0,
            post_type TEXT,
            created_utc TEXT,
            scraped_at TEXT,
            status TEXT DEFAULT 'pending',
            has_image INTEGER DEFAULT 0,
            has_video INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);
        CREATE INDEX IF NOT EXISTS idx_posts_reddit_id ON posts(reddit_id);
        CREATE INDEX IF NOT EXISTS idx_posts_score ON posts(score);
        CREATE INDEX IF NOT EXISTS idx_posts_num_comments ON posts(num_comments);
        CREATE INDEX IF NOT EXISTS idx_posts_word_count ON posts(word_count);

        CREATE TABLE IF NOT EXISTS scrape_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT,
            ended_at TEXT,
            target TEXT,
            status TEXT,
            post_count INTEGER DEFAULT 0,
            message TEXT
        );

        CREATE TABLE IF NOT EXISTS scrape_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            interval_minutes INTEGER DEFAULT 60,
            targets TEXT DEFAULT '',
            post_types TEXT DEFAULT 'text,image,video,gallery,link',
            fetch_images INTEGER DEFAULT 1,
            fetch_videos INTEGER DEFAULT 0,
            fetch_comments INTEGER DEFAULT 1,
            limit_per_target INTEGER DEFAULT 100
        );

        INSERT OR IGNORE INTO scrape_config (id) VALUES (1);

        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            selected_sources TEXT DEFAULT '',
            select_mode TEXT DEFAULT 'single'
        );

        INSERT OR IGNORE INTO user_preferences (id) VALUES (1);

        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            source TEXT DEFAULT '',
            title TEXT,
            author TEXT,
            created_utc TEXT,
            word_count INTEGER DEFAULT 0,
            score INTEGER DEFAULT 0,
            num_comments INTEGER DEFAULT 0,
            tags TEXT DEFAULT '',
            created_at TEXT
        );

        INSERT OR IGNORE INTO tags (name, created_at) VALUES ('产品广告', datetime('now'));
        INSERT OR IGNORE INTO tags (name, created_at) VALUES ('产品创意', datetime('now'));
    """)
    conn.commit()
    conn.close()


def get_config():
    conn = get_db()
    row = conn.execute("SELECT * FROM scrape_config WHERE id = 1").fetchone()
    conn.close()
    if row:
        return dict(row)
    return {}


def save_config(config: dict):
    conn = get_db()
    conn.execute("""
        UPDATE scrape_config SET
            interval_minutes = ?,
            targets = ?,
            post_types = ?,
            fetch_images = ?,
            fetch_videos = ?,
            fetch_comments = ?,
            limit_per_target = ?
        WHERE id = 1
    """, (
        config.get("interval_minutes", 60),
        config.get("targets", ""),
        config.get("post_types", "text,image,video,gallery,link"),
        config.get("fetch_images", 1),
        config.get("fetch_videos", 0),
        config.get("fetch_comments", 1),
        config.get("limit_per_target", 100),
    ))
    conn.commit()
    conn.close()


def insert_posts(posts: list):
    """Insert posts, skip duplicates and deleted ones."""
    conn = get_db()
    deleted_ids = set(
        row[0] for row in conn.execute(
            "SELECT reddit_id FROM posts WHERE status = 'deleted'"
        ).fetchall()
    )
    now = datetime.now().isoformat()
    inserted = 0
    for p in posts:
        reddit_id = p.get("id", p.get("reddit_id", ""))
        if reddit_id in deleted_ids:
            continue
        try:
            conn.execute("""
                INSERT INTO posts
                (reddit_id, title, author, selftext, permalink, url, source, word_count, score,
                 num_comments, post_type, created_utc, scraped_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (
                reddit_id,
                p.get("title", ""),
                p.get("author", ""),
                p.get("selftext", ""),
                p.get("permalink", ""),
                p.get("url", ""),
                p.get("source", ""),
                len(p.get("selftext", "")),
                p.get("score", 0),
                p.get("num_comments", 0),
                p.get("post_type", "text"),
                p.get("created_utc", ""),
                now,
            ))
            inserted += 1
        except sqlite3.IntegrityError:
            conn.execute(
                "UPDATE posts SET score = ?, num_comments = ? WHERE reddit_id = ?",
                (p.get("score", 0), p.get("num_comments", 0), reddit_id)
            )
    conn.commit()
    conn.close()
    return inserted


def get_posts_by_status(status: str, page: int = 1, per_page: int = 15,
                        sort_by: str = "scraped_at", sort_order: str = "desc",
                        sources: list = None, search: str = None):
    conn = get_db()
    offset = (page - 1) * per_page
    allowed_sort = {"scraped_at", "score", "num_comments", "created_utc", "word_count"}
    if sort_by not in allowed_sort:
        sort_by = "scraped_at"
    order = "DESC" if sort_order == "desc" else "ASC"

    where = "status = ?"
    params = [status]
    if sources:
        placeholders = ",".join("?" * len(sources))
        where += f" AND source IN ({placeholders})"
        params.extend(sources)
    if search:
        where += " AND title LIKE ?"
        params.append(f"%{search}%")

    rows = conn.execute(
        f"SELECT * FROM posts WHERE {where} ORDER BY {sort_by} {order} LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()
    total = conn.execute(
        f"SELECT COUNT(*) FROM posts WHERE {where}", params
    ).fetchone()[0]
    conn.close()
    return [dict(r) for r in rows], total


def get_all_sources():
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT source FROM posts WHERE source != '' ORDER BY source"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_post_detail(post_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_post_status(post_id: int, new_status: str):
    conn = get_db()
    conn.execute("UPDATE posts SET status = ? WHERE id = ?", (new_status, post_id))
    conn.commit()
    conn.close()


def add_scrape_log(target: str, started_at: str):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO scrape_logs (started_at, target, status) VALUES (?, ?, 'running')",
        (started_at, target)
    )
    log_id = cur.lastrowid
    conn.commit()
    conn.close()
    return log_id


def finish_scrape_log(log_id: int, status: str, post_count: int, message: str = ""):
    conn = get_db()
    conn.execute(
        "UPDATE scrape_logs SET ended_at = ?, status = ?, post_count = ?, message = ? WHERE id = ?",
        (datetime.now().isoformat(), status, post_count, message, log_id)
    )
    conn.commit()
    conn.close()


def get_scrape_logs(page: int = 1, per_page: int = 15):
    conn = get_db()
    offset = (page - 1) * per_page
    rows = conn.execute(
        "SELECT * FROM scrape_logs ORDER BY started_at DESC LIMIT ? OFFSET ?",
        (per_page, offset)
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM scrape_logs").fetchone()[0]
    conn.close()
    return [dict(r) for r in rows], total


def get_selected_sources():
    conn = get_db()
    row = conn.execute("SELECT selected_sources, select_mode FROM user_preferences WHERE id = 1").fetchone()
    conn.close()
    if row:
        sources = [s for s in (row[0] or "").split(",") if s]
        return {"selected_sources": sources, "select_mode": row[1] or "single"}
    return {"selected_sources": [], "select_mode": "single"}


def save_selected_sources(sources: list, select_mode: str = "single"):
    conn = get_db()
    conn.execute("UPDATE user_preferences SET selected_sources = ?, select_mode = ? WHERE id = 1",
                 (",".join(sources), select_mode))
    conn.commit()
    conn.close()


# --- Tags ---

def get_all_tags():
    conn = get_db()
    rows = conn.execute("SELECT * FROM tags ORDER BY created_at").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_tag(name: str):
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO tags (name, created_at) VALUES (?, datetime('now'))", (name,))
    conn.commit()
    row = conn.execute("SELECT * FROM tags WHERE name = ?", (name,)).fetchone()
    conn.close()
    return dict(row) if row else None


# --- Favorites ---

def add_favorite(post_id: int, tags: list):
    conn = get_db()
    post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        return None
    # Ensure tags exist
    for tag in tags:
        conn.execute("INSERT OR IGNORE INTO tags (name, created_at) VALUES (?, datetime('now'))", (tag,))
    conn.execute(
        """INSERT INTO favorites (post_id, source, title, author, created_utc, word_count, score, num_comments, tags, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (post_id, post["source"], post["title"], post["author"], post["created_utc"],
         post["word_count"], post["score"], post["num_comments"], ",".join(tags))
    )
    conn.commit()
    fav_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return fav_id


def get_favorites(page: int = 1, per_page: int = 15, search: str = None):
    conn = get_db()
    offset = (page - 1) * per_page
    where = "1=1"
    params = []
    if search:
        where += " AND title LIKE ?"
        params.append(f"%{search}%")
    rows = conn.execute(
        f"SELECT * FROM favorites WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()
    total = conn.execute(f"SELECT COUNT(*) FROM favorites WHERE {where}", params).fetchone()[0]
    conn.close()
    return [dict(r) for r in rows], total


def delete_favorite(fav_id: int):
    conn = get_db()
    conn.execute("DELETE FROM favorites WHERE id = ?", (fav_id,))
    conn.commit()
    conn.close()


def get_favorites_count():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0]
    conn.close()
    return count
