# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Reddit 本地爬取站 — a local web app wrapping `reddit-universal-scraper` to scrape, manage, and triage Reddit posts through a workflow pipeline (pending → to_sync → synced / deleted).

## Running the Project

```bash
# Install dependencies (both the app and the scraper)
pip install -r requirements.txt
pip install -r reddit-universal-scraper/requirements.txt

# Start the server (port 8080)
python app.py
# Access at http://localhost:8080
```

## Architecture

- **Backend:** FastAPI (`app.py`) — REST API + static file serving, runs on port 8080
- **Database:** SQLite via stdlib `sqlite3` (`database.py`) — stored at `data/reddit_local.db`, WAL mode
- **Scraper:** `scraper_runner.py` — daemon thread that spawns `python main.py <target>` subprocesses inside `reddit-universal-scraper/`, then imports output CSVs into SQLite
- **Frontend:** Single vanilla HTML/CSS/JS file (`static/index.html`) — no build step, no framework

## Key Data Flow

1. User configures targets in the UI → saved to `scrape_config` table
2. ScraperRunner spawns subprocess: `reddit-universal-scraper/main.py <target> --mode full --limit N`
3. Scraper writes to `reddit-universal-scraper/data/r_<target>/posts.csv`
4. ScraperRunner reads that CSV, filters by post type, imports into `posts` table (skips deleted reddit_ids)
5. Frontend fetches posts via `/api/posts` with status/sort/source filters

## Database Tables

- `posts` — main content table (status: pending/to_sync/synced/deleted, soft-delete semantics)
- `scrape_config` — singleton row with interval, targets, type filters, media options
- `scrape_logs` — history of scrape runs with timing and counts
- `user_preferences` — persisted UI state (selected sources, select mode)

## API Patterns

All endpoints under `/api/`. Posts use status-based querying with pagination (`page` param, 20 per page). Sorting via `sort_by` and `sort_order` params. Source filtering via comma-separated `sources` param. Status transitions via `POST /api/posts/{id}/sync|delete|publish`.

## Important Conventions

- Database migrations are done manually via `ALTER TABLE` + updating the `init_db()` schema
- The scraper is treated as a black box — only its CLI interface and CSV output are used
- Frontend is a single file; all state management is in JS variables, UI updates via DOM manipulation
- User preferences (source filter selection, single/multi mode) persist in the database
