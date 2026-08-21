import sqlite3
import time

from app.config import settings
from app.library import folders as library_folders
from app.library import shares as library_shares

ENV_PATH = ".env"

_EXCLUDED_ENV_KEYS = {"SESSION_SECRET", "USB_MOUNT", "HOST_LIBRARY_ROOT", "SHARES_MOUNT"}

_ENV_KEYS = [
    "NTFY_URL", "NTFY_TOPIC",
    "SONARR_URL", "SONARR_API_KEY", "SONARR_SECRET",
    "RADARR_URL", "RADARR_API_KEY", "RADARR_SECRET",
    "LIDARR_URL", "LIDARR_API_KEY", "LIDARR_SECRET",
    "READARR_URL", "READARR_API_KEY", "READARR_SECRET",
    "JELLYFIN_URL", "JELLYFIN_API_KEY", "JELLYFIN_PUBLIC_URL",
]

_ARRS = ["sonarr", "radarr", "lidarr", "readarr"]


def build_export(db_path: str) -> dict:
    env = {key: getattr(settings, key.lower()) for key in _ENV_KEYS if key not in _EXCLUDED_ENV_KEYS}

    folders = []
    for arr in _ARRS:
        for f in library_folders.list_folders(db_path, arr):
            folders.append({"arr": f["arr"], "path": f["path"]})

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        shares = [
            {
                "slug": r["slug"],
                "server": r["server"],
                "share": r["share"],
                "username": r["username"],
                "password": r["password"],
            }
            for r in conn.execute(
                "SELECT slug, server, share, username, password FROM smb_shares"
            ).fetchall()
        ]

    return {
        "version": 1,
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "env": env,
        "library_folders": folders,
        "smb_shares": shares,
    }


def _write_env(env: dict) -> None:
    try:
        with open(ENV_PATH) as f:
            existing = f.read().splitlines()
    except FileNotFoundError:
        existing = []

    lines = []
    written_keys = set()
    for line in existing:
        if "=" in line and not line.strip().startswith("#"):
            key = line.split("=", 1)[0]
            if key in env and key not in _EXCLUDED_ENV_KEYS:
                lines.append(f"{key}={env[key]}")
                written_keys.add(key)
                continue
        lines.append(line)

    for key, value in env.items():
        if key not in written_keys and key not in _EXCLUDED_ENV_KEYS:
            lines.append(f"{key}={value}")

    # ENV_PATH is bind-mounted from the host in docker-compose.yml so the
    # import survives a container restart — os.replace (atomic rename)
    # returns EBUSY on a bind-mounted file, so we write in place instead.
    with open(ENV_PATH, "w") as f:
        f.write("\n".join(lines) + "\n")


async def apply_import(db_path: str, data: dict) -> dict:
    if data.get("version") != 1:
        return {
            "env_written": False,
            "folders_restored": 0,
            "shares_restored": 0,
            "errors": ["version d'export non supportée"],
        }

    errors: list[str] = []

    env = {k: v for k, v in data.get("env", {}).items() if k not in _EXCLUDED_ENV_KEYS}
    try:
        _write_env(env)
        env_written = True
    except OSError as exc:
        env_written = False
        errors.append(f"écriture .env échouée: {exc}")

    # La spec impose de vider library_folders/smb_shares avant restauration
    # (import = remplacement complet, pas fusion).
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM library_folders")
        conn.execute("DELETE FROM smb_shares")

    folders_restored = 0
    for entry in data.get("library_folders", []):
        try:
            result = await library_folders.add_folder(db_path, entry["arr"], entry["path"])
        except (sqlite3.IntegrityError, KeyError) as exc:
            errors.append(f"dossier non restauré: {entry} ({exc})")
            continue
        if result is None:
            errors.append(f"dossier non restauré: {entry['arr']} {entry['path']}")
        else:
            folders_restored += 1

    shares_restored = 0
    for entry in data.get("smb_shares", []):
        try:
            result = await library_shares.add_share(
                db_path, entry["slug"], entry["server"], entry["share"], entry["username"], entry["password"]
            )
        except (sqlite3.IntegrityError, KeyError) as exc:
            errors.append(f"partage non restauré: {entry} ({exc})")
            continue
        if result is None:
            errors.append(f"partage non restauré: {entry['slug']}")
        else:
            shares_restored += 1

    return {
        "env_written": env_written,
        "folders_restored": folders_restored,
        "shares_restored": shares_restored,
        "errors": errors,
    }
