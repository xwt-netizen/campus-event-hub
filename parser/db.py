import sqlite3
import json
from datetime import datetime


class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url TEXT UNIQUE NOT NULL,
                source_name TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT,
                publish_date TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                organizer TEXT,
                date TEXT,
                start_time TEXT,
                end_time TEXT,
                location TEXT,
                has_ticket INTEGER DEFAULT 0,
                ticket_info TEXT,
                volunteer_hours REAL,
                recruit_deadline TEXT,
                description TEXT,
                source_name TEXT NOT NULL,
                source_url TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (article_id) REFERENCES articles(id)
            );
            CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);
            CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);
            CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(source_url);
        """)
        conn.commit()
        conn.close()

    def article_exists(self, source_url):
        conn = self._get_conn()
        row = conn.execute("SELECT id FROM articles WHERE source_url = ?", (source_url,)).fetchone()
        conn.close()
        return row is not None

    def insert_article(self, source_url, source_name, title, content, publish_date):
        conn = self._get_conn()
        cur = conn.execute(
            "INSERT OR IGNORE INTO articles (source_url, source_name, title, content, publish_date) VALUES (?, ?, ?, ?, ?)",
            (source_url, source_name, title, content, publish_date),
        )
        conn.commit()
        article_id = cur.lastrowid
        conn.close()
        return article_id

    def insert_event(self, article_id, ev):
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO events
            (article_id, category, title, organizer, date, start_time, end_time,
             location, has_ticket, ticket_info, volunteer_hours, recruit_deadline,
             description, source_name, source_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                article_id,
                ev.get("category", "other"),
                ev.get("title", ""),
                ev.get("organizer", ""),
                ev.get("date"),
                ev.get("start_time"),
                ev.get("end_time"),
                ev.get("location", ""),
                1 if ev.get("has_ticket") else 0,
                ev.get("ticket_info", ""),
                ev.get("volunteer_hours"),
                ev.get("recruit_deadline"),
                ev.get("description", ""),
                ev.get("source_name", ""),
                ev.get("source_url", ""),
            ),
        )
        conn.commit()
        conn.close()

    def get_all_events(self):
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM events ORDER BY date DESC, start_time DESC"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_upcoming_events(self, limit=200):
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM events WHERE date >= date('now','-1 day') ORDER BY date ASC, start_time ASC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_stats(self):
        conn = self._get_conn()
        row = conn.execute(
            "SELECT category, COUNT(*) as cnt FROM events GROUP BY category"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) as n FROM events").fetchone()
        conn.close()
        stats = {r["category"]: r["cnt"] for r in row}
        stats["total"] = total["n"] if total else 0
        return stats
