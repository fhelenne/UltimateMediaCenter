import sqlite3


def init_db(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS library_folders (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                arr            TEXT NOT NULL,
                path           TEXT NOT NULL,
                root_folder_id TEXT,
                created_at     REAL NOT NULL,
                UNIQUE(arr, path)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS smb_shares (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                slug       TEXT NOT NULL UNIQUE,
                server     TEXT NOT NULL,
                share      TEXT NOT NULL,
                username   TEXT NOT NULL,
                password   TEXT NOT NULL,
                mounted    INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL
            )
            """
        )
