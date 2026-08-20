import sqlite3

from app.library import db


def test_init_db_creates_tables(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "library_folders" in tables
    assert "smb_shares" in tables


def test_init_db_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    db.init_db(db_path)  # ne doit pas lever
