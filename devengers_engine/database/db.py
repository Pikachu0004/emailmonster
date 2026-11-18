import os
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from devengers_engine.config import settings


def get_db_connection() -> sqlite3.Connection:
    """Creates a thread-safe connection to SQLite with WAL enabled and row factory."""
    db_path = settings.db_file_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for high reliability & concurrency
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    """Initializes the database schema if tables do not exist."""
    conn = get_db_connection()
    try:
        with conn:
            # 1. Contacts Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    first_name TEXT NOT NULL,
                    extra_data TEXT DEFAULT '{}',
                    source_file TEXT DEFAULT '',
                    status TEXT DEFAULT 'ACTIVE',
                    created_at TEXT NOT NULL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_contacts_id ON contacts(id);")

            # 2. Campaigns Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    template_name TEXT NOT NULL,
                    custom_body TEXT DEFAULT '',
                    template_vars TEXT DEFAULT '{}',
                    status TEXT DEFAULT 'DRAFT',
                    total_queued INTEGER DEFAULT 0,
                    sent_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    skipped_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            # 3. Send Logs Table (Comprehensive audit & deduplication engine)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS send_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER,
                    contact_id INTEGER,
                    recipient_email TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message_id TEXT,
                    error_message TEXT,
                    sent_at TEXT NOT NULL,
                    date_sent TEXT NOT NULL,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
                    FOREIGN KEY (contact_id) REFERENCES contacts(id)
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_send_logs_recipient ON send_logs(recipient_email);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_send_logs_date_sent ON send_logs(date_sent);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_send_logs_campaign ON send_logs(campaign_id);")

            # 4. Suppression / Unsubscribe List
            conn.execute("""
                CREATE TABLE IF NOT EXISTS unsubscribes (
                    email TEXT PRIMARY KEY,
                    reason TEXT DEFAULT 'user_request',
                    unsubscribed_at TEXT NOT NULL
                );
            """)
    finally:
        conn.close()


def get_today_iso_date() -> str:
    """Returns today's date in YYYY-MM-DD UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def get_current_timestamp() -> str:
    """Returns ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()
