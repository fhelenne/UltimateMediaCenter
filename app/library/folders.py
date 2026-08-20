import sqlite3
import time

from app.library import rootfolder


def list_folders(db_path: str, arr: str) -> list[dict]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, arr, path, root_folder_id, created_at FROM library_folders WHERE arr = ?",
            (arr,),
        ).fetchall()
    return [dict(row) for row in rows]


async def add_folder(db_path: str, arr: str, path: str) -> dict | None:
    root_folder_id = await rootfolder.add_root_folder(arr, path)
    if root_folder_id is None:
        return None
    created_at = time.time()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO library_folders (arr, path, root_folder_id, created_at) VALUES (?, ?, ?, ?)",
            (arr, path, root_folder_id, created_at),
        )
        folder_id = cursor.lastrowid
    return {
        "id": folder_id,
        "arr": arr,
        "path": path,
        "root_folder_id": root_folder_id,
        "created_at": created_at,
    }


async def remove_folder(db_path: str, folder_id: int) -> bool:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT arr, root_folder_id FROM library_folders WHERE id = ?", (folder_id,)
        ).fetchone()
    if row is None:
        return False
    success = await rootfolder.remove_root_folder(row["arr"], row["root_folder_id"])
    if not success:
        return False
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM library_folders WHERE id = ?", (folder_id,))
    return True
