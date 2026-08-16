import json
import sqlite3
import time


def init_db(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS arr_cache (
                key        TEXT PRIMARY KEY,
                data       TEXT NOT NULL,
                expires_at REAL NOT NULL
            )
            """
        )


def get(db_path: str, key: str) -> dict | list | None:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT data, expires_at FROM arr_cache WHERE key = ?", (key,)
        ).fetchone()
    if row is None:
        return None
    data, expires_at = row
    if time.time() > expires_at:
        return None
    return json.loads(data)


def set(db_path: str, key: str, data: dict | list, ttl: int) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO arr_cache (key, data, expires_at) VALUES (?, ?, ?)",
            (key, json.dumps(data), time.time() + ttl),
        )
