"""
Reddit 本地爬取站 - 爬取任务管理器
"""
import subprocess
import threading
import time
import csv
import os
from datetime import datetime
from pathlib import Path

from database import get_config, insert_posts, add_scrape_log, finish_scrape_log

SCRAPER_DIR = Path(__file__).parent / "reddit-universal-scraper"


class ScraperRunner:
    def __init__(self):
        self.running = False
        self.process = None
        self.thread = None
        self.current_target = ""

    @property
    def status(self):
        return {
            "running": self.running,
            "current_target": self.current_target,
        }

    def start(self):
        if self.running:
            return False
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.running = False
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.current_target = ""

    def _run_loop(self):
        """Main scraping loop - iterates targets with configured interval."""
        while self.running:
            config = get_config()
            targets = [t.strip() for t in config.get("targets", "").split(",") if t.strip()]
            if not targets:
                time.sleep(5)
                continue

            for target in targets:
                if not self.running:
                    break
                self._scrape_target(target, config)

            if not self.running:
                break

            # Wait for interval
            interval = config.get("interval_minutes", 60) * 60
            wait_end = time.time() + interval
            while self.running and time.time() < wait_end:
                time.sleep(1)

    def _scrape_target(self, target: str, config: dict):
        self.current_target = target
        started_at = datetime.now().isoformat()
        log_id = add_scrape_log(target, started_at)

        # Build command
        cmd = [
            "python", "main.py", target,
            "--mode", "full",
            "--limit", str(config.get("limit_per_target", 100)),
        ]
        if not config.get("fetch_images", 1) and not config.get("fetch_videos", 0):
            cmd.append("--no-media")
        if not config.get("fetch_comments", 1):
            cmd.append("--no-comments")

        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=str(SCRAPER_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.process.wait()

            # Parse output CSV and import to database
            post_count = self._import_scraped_data(target, config)
            finish_scrape_log(log_id, "completed", post_count)

            # Clean up CSV after successful import
            csv_path = SCRAPER_DIR / "data" / f"r_{target}" / "posts.csv"
            if csv_path.exists():
                csv_path.unlink()

        except Exception as e:
            finish_scrape_log(log_id, "error", 0, str(e))

        self.current_target = ""

    def _import_scraped_data(self, target: str, config: dict) -> int:
        """Read scraped CSV and import into local database."""
        csv_path = SCRAPER_DIR / "data" / f"r_{target}" / "posts.csv"
        if not csv_path.exists():
            return 0

        posts = []
        allowed_types = set(config.get("post_types", "text,image,video,gallery,link").split(","))

        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    post_type = row.get("post_type", "text")
                    if post_type not in allowed_types:
                        continue
                    posts.append({
                        "id": row.get("id", ""),
                        "title": row.get("title", ""),
                        "author": row.get("author", ""),
                        "selftext": row.get("selftext", ""),
                        "permalink": row.get("permalink", ""),
                        "url": row.get("url", ""),
                        "source": target,
                        "score": int(row.get("score", 0)),
                        "num_comments": int(row.get("num_comments", 0)),
                        "post_type": post_type,
                        "created_utc": row.get("created_utc", ""),
                    })
        except Exception:
            return 0

        return insert_posts(posts)


# Singleton instance
scraper_runner = ScraperRunner()
