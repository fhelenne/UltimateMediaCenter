import asyncio
import logging
import os
import sqlite3
import time

from app.config import SHARES_MOUNT

logger = logging.getLogger(__name__)


async def _mount(slug: str, server: str, share: str, username: str, password: str) -> bool:
    target = f"{SHARES_MOUNT}/{slug}"
    try:
        os.makedirs(target, exist_ok=True)
    except OSError as exc:
        logger.error("smb mount target mkdir failed", extra={"slug": slug, "error": str(exc)})
        return False
    try:
        # Mot de passe passé via la variable d'env PASSWD de mount.cifs, pas
        # via -o password=... : évite l'injection d'options CIFS si le mot de
        # passe contient une virgule, et évite la fuite en clair dans argv
        # (visible via ps par tout utilisateur de l'hôte le temps du mount).
        mount_env = {**os.environ, "PASSWD": password}
        process = await asyncio.create_subprocess_exec(
            "mount", "-t", "cifs", f"//{server}/{share}", target,
            "-o", f"username={username},uid=1000,gid=1000",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env=mount_env,
        )
        _, stderr = await process.communicate()
    except OSError as exc:
        logger.error("smb mount failed to start", extra={"slug": slug, "error": str(exc)})
        return False
    if process.returncode != 0:
        logger.error(
            "smb mount exited non-zero",
            extra={"slug": slug, "returncode": process.returncode, "stderr": stderr.decode(errors="replace")},
        )
        return False
    return True


async def _umount(slug: str) -> bool:
    target = f"{SHARES_MOUNT}/{slug}"
    try:
        process = await asyncio.create_subprocess_exec(
            "umount", target,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
    except OSError as exc:
        logger.error("smb umount failed to start", extra={"slug": slug, "error": str(exc)})
        return False
    if process.returncode != 0:
        logger.error(
            "smb umount exited non-zero",
            extra={"slug": slug, "returncode": process.returncode, "stderr": stderr.decode(errors="replace")},
        )
        return False
    return True


def list_shares(db_path: str) -> list[dict]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, slug, server, share, username, mounted, created_at FROM smb_shares"
        ).fetchall()
    return [dict(row) for row in rows]


async def add_share(db_path: str, slug: str, server: str, share: str, username: str, password: str) -> dict | None:
    if not await _mount(slug, server, share, username, password):
        return None
    created_at = time.time()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO smb_shares (slug, server, share, username, password, mounted, created_at)
               VALUES (?, ?, ?, ?, ?, 1, ?)""",
            (slug, server, share, username, password, created_at),
        )
        share_id = cursor.lastrowid
    return {
        "id": share_id,
        "slug": slug,
        "server": server,
        "share": share,
        "username": username,
        "mounted": 1,
        "created_at": created_at,
    }


async def remove_share(db_path: str, share_id: int) -> bool | None:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT slug FROM smb_shares WHERE id = ?", (share_id,)).fetchone()
        if row is None:
            return False
        slug = row["slug"]
        referenced = conn.execute(
            "SELECT 1 FROM library_folders WHERE path LIKE ? OR path LIKE ? LIMIT 1",
            (f"%/shares/{slug}", f"%/shares/{slug}/%"),
        ).fetchone()
    if referenced is not None:
        return None
    if not await _umount(slug):
        return False
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM smb_shares WHERE id = ?", (share_id,))
    return True


async def remount_all(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT slug, server, share, username, password FROM smb_shares WHERE mounted = 1"
        ).fetchall()
    for row in rows:
        success = await _mount(row["slug"], row["server"], row["share"], row["username"], row["password"])
        if not success:
            logger.error("smb remount at startup failed", extra={"slug": row["slug"]})
