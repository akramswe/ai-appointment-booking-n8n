"""SQLite persistence for appointments and unsent confirmation drafts."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def database_path() -> Path:
    return Path(os.getenv("DATABASE_PATH", "./data/bookings.sqlite3"))


@contextmanager
def connection():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                customer_email TEXT NOT NULL,
                service TEXT NOT NULL,
                day TEXT NOT NULL,
                time TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(day, time)
            );
            CREATE TABLE IF NOT EXISTS outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                appointment_id INTEGER NOT NULL,
                recipient TEXT NOT NULL,
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                FOREIGN KEY(appointment_id) REFERENCES appointments(id)
            );
        """)
