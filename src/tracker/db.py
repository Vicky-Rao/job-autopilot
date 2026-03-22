"""
SQLite tracker — logs all jobs discovered, reviewed, and applied to.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "jobs.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            description TEXT,
            salary_raw TEXT,
            location TEXT,
            remote INTEGER,
            url TEXT,
            source TEXT,
            funding TEXT,
            domain_tags TEXT,
            score INTEGER,
            filter_reasons TEXT,
            status TEXT DEFAULT 'discovered',
            discovered_at TEXT,
            reviewed_at TEXT,
            applied_at TEXT,
            cover_letter TEXT,
            notes TEXT
        );
    """)
    conn.commit()
    conn.close()


def upsert_job(job_data: dict):
    conn = get_connection()
    conn.execute("""
        INSERT OR IGNORE INTO jobs (
            id, title, company, description, salary_raw, location,
            remote, url, source, funding, domain_tags, score,
            filter_reasons, status, discovered_at
        ) VALUES (
            :id, :title, :company, :description, :salary_raw, :location,
            :remote, :url, :source, :funding, :domain_tags, :score,
            :filter_reasons, :status, :discovered_at
        )
    """, {
        **job_data,
        "domain_tags": json.dumps(job_data.get("domain_tags", [])),
        "filter_reasons": json.dumps(job_data.get("filter_reasons", [])),
        "discovered_at": datetime.now().isoformat(),
        "status": "pending_review"
    })
    conn.commit()
    conn.close()


def get_pending_review() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM jobs WHERE status = 'pending_review' ORDER BY score DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_status(job_id: str, status: str, **kwargs):
    conn = get_connection()
    updates = {"status": status, **kwargs}
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    conn.execute(
        f"UPDATE jobs SET {set_clause} WHERE id = :id",
        {**updates, "id": job_id}
    )
    conn.commit()
    conn.close()


def mark_approved(job_id: str):
    update_status(job_id, "approved", reviewed_at=datetime.now().isoformat())


def mark_rejected(job_id: str, note: str = ""):
    update_status(job_id, "rejected", reviewed_at=datetime.now().isoformat(), notes=note)


def mark_applied(job_id: str, cover_letter: str):
    update_status(
        job_id, "applied",
        applied_at=datetime.now().isoformat(),
        cover_letter=cover_letter
    )


def get_stats() -> dict:
    conn = get_connection()
    stats = {}
    for status in ["pending_review", "approved", "rejected", "applied"]:
        count = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status = ?", (status,)
        ).fetchone()[0]
        stats[status] = count
    conn.close()
    return stats
