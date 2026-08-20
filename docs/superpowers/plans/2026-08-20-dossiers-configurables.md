# Dossiers de bibliothèque configurables — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permettre d'ajouter/retirer des dossiers de bibliothèque (locaux,
n'importe où sur l'hôte, ou partages SMB) depuis l'UI pour chaque onglet
(Séries/Films/Musique/Livres), et d'exporter/réimporter toute la config
pilotée par l'app.

**Architecture:** Un dossier hôte large (`HOST_LIBRARY_ROOT`) est monté en
lecture-écriture dans `app` + les 4 *arr + jellyfin. Le container `app`
devient le seul composant privilégié (`CAP_SYS_ADMIN`, `cifs-utils`) pour
monter des partages SMB dans `SHARES_MOUNT` avec propagation `shared` —
visible ensuite, sans privilège, par les autres containers qui montent le
même chemin hôte. Chaque dossier ajouté est enregistré comme root-folder
via l'API déjà exposée par le *arr concerné (pas de réimplémentation de
leur gestion de bibliothèque).

**Tech Stack:** FastAPI, SQLite (sqlite3 stdlib, pattern `app/arr/cache.py`),
httpx (pattern `app/arr/*.py`), `asyncio.create_subprocess_exec` (pattern
`app/ebooks/ebooks.py`), Jinja2 + HTMX (pattern `app/ui/templates/`).

**Spec:** `docs/superpowers/specs/2026-08-20-dossiers-configurables-design.md`
**ADR:** `.ai/adr/0005-dossiers-configurables-ui.md`

## Global Constraints
- Naming : pas de DTO/Interface/ValueObject/Repository/Manager/Adapter —
  noms métier (`folders.py`, `shares.py`, `rootfolder.py`).
- TDD : test rouge avant l'implémentation sur chaque tâche.
- La table `users` (compte admin) n'est jamais lue ni écrite par l'export
  ou l'import — aucune tâche de ce plan n'y touche.
- `SESSION_SECRET`, `USB_MOUNT`, `HOST_LIBRARY_ROOT`, `SHARES_MOUNT` sont
  exclus de l'export/import (propres à la machine).
- Mots de passe SMB stockés en clair en DB — cohérent avec le reste du
  projet (`.env` déjà en clair), pas de chiffrement dans ce plan.
- Portée du plan : les 4 *arr (Sonarr/Radarr/Lidarr/Readarr) uniquement.
  Jellyfin garde sa configuration manuelle existante (déjà documentée dans
  le README) — synchroniser ses bibliothèques n'est pas traité ici, YAGNI
  tant que ce n'est pas demandé.
- Sonarr/Radarr : API `v3`. Lidarr/Readarr : API `v1` (cf. commit
  `682f643` — ces deux-là ne sont jamais passées en v3).

---

### Task 1: Schéma DB + settings

**Files:**
- Create: `app/library/__init__.py`
- Create: `app/library/db.py`
- Modify: `app/config.py`
- Test: `tests/library/__init__.py` (vide), `tests/library/test_db.py`

**Interfaces:**
- Produces: `app/library/db.py::init_db(db_path: str) -> None` — crée les
  tables `library_folders` et `smb_shares` si absentes (idempotent, même
  pattern que `app/arr/cache.py::init_db`).
- Produces: `Settings.host_library_root: str` (défaut `/library-root`),
  `Settings.shares_mount: str` (défaut `/library-root/shares`).

- [ ] **Step 1: Write the failing test**

```python
# tests/library/test_db.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/library/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.library'`

- [ ] **Step 3: Create `app/library/__init__.py`** (fichier vide) et
  `tests/library/__init__.py` (fichier vide).

- [ ] **Step 4: Write `app/library/db.py`**

```python
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
```

- [ ] **Step 5: Add settings fields**

In `app/config.py`, add to the `Settings` class body (after
`calibre_library_path`):

```python
    host_library_root: str = "/library-root"
    shares_mount: str = "/library-root/shares"
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/library/test_db.py -v`
Expected: PASS (2 tests)

- [ ] **Step 7: Commit**

```bash
git add app/library/__init__.py app/library/db.py app/config.py tests/library/
git commit -m "feat: add library_folders/smb_shares schema"
```

---

### Task 2: Client API root-folder par *arr

**Files:**
- Create: `app/library/rootfolder.py`
- Test: `tests/library/test_rootfolder.py`

**Interfaces:**
- Consumes: `app.config.settings` (mêmes champs `*_url`/`*_api_key` que
  `app/arr/*.py`).
- Produces: `add_root_folder(arr: str, path: str) -> str | None` (renvoie
  l'id du root folder créé côté *arr, `None` si échec).
- Produces: `remove_root_folder(arr: str, root_folder_id: str) -> bool`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/library/test_rootfolder.py
import httpx
import pytest
import respx

from app.library import rootfolder


@pytest.mark.parametrize(
    "arr,base_url,api_version",
    [
        ("sonarr", "http://sonarr-test:8989", "v3"),
        ("radarr", "http://radarr-test:7878", "v3"),
        ("lidarr", "http://lidarr-test:8686", "v1"),
        ("readarr", "http://readarr-test:8787", "v1"),
    ],
)
@respx.mock
async def test_add_root_folder_returns_id(arr, base_url, api_version):
    respx.post(f"{base_url}/api/{api_version}/rootfolder").mock(
        return_value=httpx.Response(201, json={"id": 7, "path": "/library-root/x"})
    )
    result = await rootfolder.add_root_folder(arr, "/library-root/x")
    assert result == "7"


@respx.mock
async def test_add_root_folder_returns_none_on_http_error():
    respx.post("http://sonarr-test:8989/api/v3/rootfolder").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    result = await rootfolder.add_root_folder("sonarr", "/library-root/x")
    assert result is None


@respx.mock
async def test_remove_root_folder_true_on_success():
    respx.delete("http://sonarr-test:8989/api/v3/rootfolder/7").mock(
        return_value=httpx.Response(200)
    )
    result = await rootfolder.remove_root_folder("sonarr", "7")
    assert result is True


@respx.mock
async def test_remove_root_folder_false_on_http_error():
    respx.delete("http://lidarr-test:8686/api/v1/rootfolder/3").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    result = await rootfolder.remove_root_folder("lidarr", "3")
    assert result is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/library/test_rootfolder.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `app/library/rootfolder.py`**

```python
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_API_VERSION = {
    "sonarr": "v3",
    "radarr": "v3",
    "lidarr": "v1",
    "readarr": "v1",
}

_URL = {
    "sonarr": lambda: settings.sonarr_url,
    "radarr": lambda: settings.radarr_url,
    "lidarr": lambda: settings.lidarr_url,
    "readarr": lambda: settings.readarr_url,
}

_API_KEY = {
    "sonarr": lambda: settings.sonarr_api_key,
    "radarr": lambda: settings.radarr_api_key,
    "lidarr": lambda: settings.lidarr_api_key,
    "readarr": lambda: settings.readarr_api_key,
}


async def add_root_folder(arr: str, path: str) -> str | None:
    base_url = _URL[arr]()
    api_version = _API_VERSION[arr]
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/api/{api_version}/rootfolder",
                headers={"X-Api-Key": _API_KEY[arr]()},
                json={"path": path},
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        logger.error(f"{arr} add_root_folder failed", extra={"error": str(exc), "path": path})
        return None
    return str(data["id"])


async def remove_root_folder(arr: str, root_folder_id: str) -> bool:
    base_url = _URL[arr]()
    api_version = _API_VERSION[arr]
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{base_url}/api/{api_version}/rootfolder/{root_folder_id}",
                headers={"X-Api-Key": _API_KEY[arr]()},
                timeout=5.0,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error(
            f"{arr} remove_root_folder failed",
            extra={"error": str(exc), "root_folder_id": root_folder_id},
        )
        return False
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/library/test_rootfolder.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add app/library/rootfolder.py tests/library/test_rootfolder.py
git commit -m "feat: add per-arr root-folder API client (v3 sonarr/radarr, v1 lidarr/readarr)"
```

---

### Task 3: CRUD dossiers (`app/library/folders.py`)

**Files:**
- Create: `app/library/folders.py`
- Test: `tests/library/test_folders.py`

**Interfaces:**
- Consumes: `app.library.rootfolder.add_root_folder`,
  `app.library.rootfolder.remove_root_folder` (Task 2).
- Produces: `list_folders(db_path: str, arr: str) -> list[dict]` (chaque
  dict : `id, arr, path, root_folder_id, created_at`).
- Produces: `add_folder(db_path: str, arr: str, path: str) -> dict | None`
  (`None` si l'enregistrement côté *arr échoue — rien n'est inséré).
- Produces: `remove_folder(db_path: str, folder_id: int) -> bool`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/library/test_folders.py
from unittest.mock import AsyncMock, patch

import pytest

from app.library import db, folders


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    db.init_db(path)
    return path


async def test_add_folder_inserts_row_on_success(db_path):
    with patch("app.library.rootfolder.add_root_folder", AsyncMock(return_value="42")):
        result = await folders.add_folder(db_path, "sonarr", "/library-root/tv")
    assert result["arr"] == "sonarr"
    assert result["path"] == "/library-root/tv"
    assert result["root_folder_id"] == "42"
    assert len(folders.list_folders(db_path, "sonarr")) == 1


async def test_add_folder_returns_none_and_inserts_nothing_on_api_failure(db_path):
    with patch("app.library.rootfolder.add_root_folder", AsyncMock(return_value=None)):
        result = await folders.add_folder(db_path, "sonarr", "/library-root/tv")
    assert result is None
    assert folders.list_folders(db_path, "sonarr") == []


async def test_list_folders_filters_by_arr(db_path):
    with patch("app.library.rootfolder.add_root_folder", AsyncMock(return_value="1")):
        await folders.add_folder(db_path, "sonarr", "/library-root/tv")
        await folders.add_folder(db_path, "radarr", "/library-root/movies")
    assert len(folders.list_folders(db_path, "sonarr")) == 1
    assert len(folders.list_folders(db_path, "radarr")) == 1


async def test_remove_folder_calls_api_and_deletes_row(db_path):
    with patch("app.library.rootfolder.add_root_folder", AsyncMock(return_value="42")):
        added = await folders.add_folder(db_path, "sonarr", "/library-root/tv")
    with patch("app.library.rootfolder.remove_root_folder", AsyncMock(return_value=True)) as mock_remove:
        result = await folders.remove_folder(db_path, added["id"])
    mock_remove.assert_awaited_once_with("sonarr", "42")
    assert result is True
    assert folders.list_folders(db_path, "sonarr") == []


async def test_remove_folder_returns_false_for_unknown_id(db_path):
    result = await folders.remove_folder(db_path, 999)
    assert result is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/library/test_folders.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `app/library/folders.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/library/test_folders.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add app/library/folders.py tests/library/test_folders.py
git commit -m "feat: add library folder CRUD backed by arr root-folder API"
```

---

### Task 4: CRUD partages SMB (`app/library/shares.py`)

**Files:**
- Create: `app/library/shares.py`
- Test: `tests/library/test_shares.py`

**Interfaces:**
- Consumes: `app.config.settings.shares_mount`.
- Produces: `list_shares(db_path: str) -> list[dict]` (masque `password`,
  champ absent du dict retourné).
- Produces: `add_share(db_path, slug, server, share, username, password) ->
  dict | None` (`None` si le mount échoue).
- Produces: `remove_share(db_path, share_id) -> bool | None` (`None` si le
  partage est encore référencé par une ligne `library_folders` — refus).
- Produces: `remount_all(db_path) -> None` (best-effort, pour le démarrage).

- [ ] **Step 1: Write the failing tests**

```python
# tests/library/test_shares.py
from unittest.mock import AsyncMock, patch

import pytest

from app.library import db, folders, shares


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    db.init_db(path)
    return path


async def test_add_share_inserts_row_on_mount_success(db_path):
    with patch("app.library.shares._mount", AsyncMock(return_value=True)):
        result = await shares.add_share(db_path, "movies-nas", "192.168.1.10", "movies", "user", "pass")
    assert result["slug"] == "movies-nas"
    assert "password" not in result
    assert len(shares.list_shares(db_path)) == 1
    assert "password" not in shares.list_shares(db_path)[0]


async def test_add_share_returns_none_and_inserts_nothing_on_mount_failure(db_path):
    with patch("app.library.shares._mount", AsyncMock(return_value=False)):
        result = await shares.add_share(db_path, "movies-nas", "192.168.1.10", "movies", "user", "pass")
    assert result is None
    assert shares.list_shares(db_path) == []


async def test_remove_share_unmounts_and_deletes_row(db_path):
    with patch("app.library.shares._mount", AsyncMock(return_value=True)):
        added = await shares.add_share(db_path, "movies-nas", "192.168.1.10", "movies", "user", "pass")
    with patch("app.library.shares._umount", AsyncMock(return_value=True)) as mock_umount:
        result = await shares.remove_share(db_path, added["id"])
    mock_umount.assert_awaited_once()
    assert result is True
    assert shares.list_shares(db_path) == []


async def test_remove_share_refused_when_referenced_by_folder(db_path):
    with patch("app.library.shares._mount", AsyncMock(return_value=True)):
        share = await shares.add_share(db_path, "movies-nas", "192.168.1.10", "movies", "user", "pass")
    with patch("app.library.rootfolder.add_root_folder", AsyncMock(return_value="1")):
        await folders.add_folder(db_path, "radarr", f"/library-root/shares/{share['slug']}")
    result = await shares.remove_share(db_path, share["id"])
    assert result is None
    assert len(shares.list_shares(db_path)) == 1


async def test_remount_all_remounts_every_mounted_share(db_path):
    with patch("app.library.shares._mount", AsyncMock(return_value=True)):
        await shares.add_share(db_path, "movies-nas", "192.168.1.10", "movies", "user", "pass")
        await shares.add_share(db_path, "music-nas", "192.168.1.10", "music", "user", "pass")
    with patch("app.library.shares._mount", AsyncMock(return_value=True)) as mock_mount:
        await shares.remount_all(db_path)
    assert mock_mount.await_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/library/test_shares.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write `app/library/shares.py`**

```python
import asyncio
import logging
import sqlite3
import time

from app.config import settings

logger = logging.getLogger(__name__)


async def _mount(slug: str, server: str, share: str, username: str, password: str) -> bool:
    target = f"{settings.shares_mount}/{slug}"
    try:
        process = await asyncio.create_subprocess_exec(
            "mkdir", "-p", target,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()
        process = await asyncio.create_subprocess_exec(
            "mount", "-t", "cifs", f"//{server}/{share}", target,
            "-o", f"username={username},password={password},uid=1000,gid=1000",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
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
    target = f"{settings.shares_mount}/{slug}"
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


def _row_without_password(row: sqlite3.Row) -> dict:
    data = dict(row)
    data.pop("password", None)
    return data


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
            "SELECT 1 FROM library_folders WHERE path LIKE ? LIMIT 1",
            (f"%/shares/{slug}/%",),
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/library/test_shares.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add app/library/shares.py tests/library/test_shares.py
git commit -m "feat: add SMB share CRUD with cifs mount/umount"
```

---

### Task 5: Démarrage — remontage des partages

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_main_lifespan.py` (nouveau fichier — aucun test de
  lifespan n'existe encore ; `tests/conftest.py::db_path` explique déjà
  pourquoi : `ASGITransport` ne déclenche jamais le lifespan, donc ce test
  appelle la fonction `lifespan`-adjacente directement, pas via le client
  HTTP)

**Interfaces:**
- Consumes: `app.library.db.init_db` (Task 1), `app.library.shares.remount_all` (Task 4).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_main_lifespan.py
from unittest.mock import AsyncMock, patch

from app.config import settings
from app.library import db as library_db


async def test_lifespan_inits_library_db_and_remounts_shares(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(settings, "db_path", db_path)

    with patch("app.library.shares.remount_all", AsyncMock()) as mock_remount:
        from app.main import lifespan, app

        async with lifespan(app):
            pass

    mock_remount.assert_awaited_once_with(db_path)
    library_db.init_db(db_path)  # doit être idempotent, ne doit pas lever
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_main_lifespan.py -v`
Expected: FAIL — `AssertionError` (remount_all pas appelé, car pas encore
câblé dans le lifespan)

- [ ] **Step 3: Wire into `app/main.py`**

Add import near the other `app.*` imports:

```python
from app.library import db as library_db
from app.library import shares as library_shares
```

In `lifespan`, after `password = auth.bootstrap_admin(...)` block and
before `yield`:

```python
    library_db.init_db(settings.db_path)
    await library_shares.remount_all(settings.db_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_main_lifespan.py -v`
Expected: PASS

- [ ] **Step 5: Run full suite to check no regression**

Run: `.venv/bin/python -m pytest -q`
Expected: all passing (previous count + new tests)

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_main_lifespan.py
git commit -m "feat: init library schema and remount SMB shares at startup"
```

---

### Task 6: Docker — montages larges + privilège SMB

**Files:**
- Modify: `docker-compose.yml`
- Modify: `Dockerfile`

**Interfaces:**
- Consumes: nouvelles variables `.env` `HOST_LIBRARY_ROOT`, `SHARES_MOUNT`
  (Task 9 les fera générer par `install.sh` — ce Task 6 les consomme via
  `${...}` comme le reste du compose fait déjà pour `USB_MOUNT`).

- [ ] **Step 1: Add `cifs-utils` and drop `USER app` in `Dockerfile`**

The `app` container is the only privileged one in the stack (ADR 0005) —
`cap_add: SYS_ADMIN` in compose only takes effect if the process can
actually call `mount`, which `mount.cifs` needs root for. Replace:

```diff
 # Stage 2 — runtime image
 FROM python:3.11-alpine
-RUN adduser -D app
+RUN adduser -D app && apk add --no-cache cifs-utils
 WORKDIR /app
 COPY --from=builder /usr/local/lib/python3.11/site-packages \
                     /usr/local/lib/python3.11/site-packages
 COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
 COPY app/ app/
 RUN mkdir -p /app/data && chown -R app:app /app
-USER app
 EXPOSE 8000
```

- [ ] **Step 2: Add mounts + capability to `docker-compose.yml`**

In the `app` service, add after `volumes:` existing entries (`app-data`,
`books-library`):

```diff
   app:
     build: .
     env_file: .env
     depends_on:
       - ntfy
+    cap_add:
+      - SYS_ADMIN
     volumes:
       - app-data:/app/data
       - books-library:/books
+      - type: bind
+        source: ${HOST_LIBRARY_ROOT}
+        target: /library-root
+      - type: bind
+        source: ${SHARES_MOUNT}
+        target: /library-root/shares
+        bind:
+          propagation: shared
     restart: unless-stopped
```

Then add the same `/library-root` and `/library-root/shares` bind mounts
(no `cap_add`, no `propagation: shared` needed — they only need to *see*
what `app` mounts) to `sonarr`, `radarr`, `lidarr`, `readarr`, `jellyfin`.
Example for `sonarr` (repeat identically for the other four, respecting
each service's existing `volumes:` list):

```diff
   sonarr:
     image: linuxserver/sonarr:latest
     environment:
       - PUID=1000
       - PGID=1000
       - TZ=Europe/Paris
     ports:
       - "8989:8989"
     volumes:
       - sonarr-config:/config
       - sonarr-tv:/tv
       - sonarr-downloads:/downloads
+      - type: bind
+        source: ${HOST_LIBRARY_ROOT}
+        target: /library-root
+      - type: bind
+        source: ${SHARES_MOUNT}
+        target: /library-root/shares
     restart: unless-stopped
```

- [ ] **Step 3: Verify compose syntax**

Run: `HOST_LIBRARY_ROOT=/tmp SHARES_MOUNT=/tmp USB_MOUNT=/tmp docker
compose config -q`
Expected: exits 0, no error.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile docker-compose.yml
git commit -m "feat: mount HOST_LIBRARY_ROOT + SHARES_MOUNT, app runs privileged for SMB"
```

---

### Task 7: Endpoints UI + templates

**Files:**
- Modify: `app/ui/router.py`
- Create: `app/ui/templates/_library.html`
- Modify: `app/ui/templates/_tab.html`
- Test: `tests/ui/test_library_router.py`

**Interfaces:**
- Consumes: `app.library.folders.{list_folders,add_folder,remove_folder}`,
  `app.library.shares.{list_shares,add_share,remove_share}` (Tasks 3-4).
- Consumes: `app.auth.router.require_login` (existing pattern, same as
  every other route in `app/ui/router.py`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/ui/test_library_router.py
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
async def logged_in_client(client):
    from app.auth import auth
    from app.config import settings

    auth.create_user(settings.db_path, "admin", "changeme", must_change_password=False)
    resp = await client.post("/auth/login", data={"username": "admin", "password": "changeme"})
    assert resp.status_code == 303
    return client


async def test_library_list_requires_login(client):
    resp = await client.get("/library/sonarr")
    assert resp.status_code in (303, 204)


async def test_library_list_renders_folders(logged_in_client):
    with patch("app.library.folders.list_folders", return_value=[
        {"id": 1, "arr": "sonarr", "path": "/library-root/tv", "root_folder_id": "1", "created_at": 0}
    ]):
        resp = await logged_in_client.get("/library/sonarr")
    assert resp.status_code == 200
    assert "/library-root/tv" in resp.text


async def test_add_folder_success(logged_in_client):
    with patch("app.library.folders.add_folder", AsyncMock(return_value={"id": 1})):
        resp = await logged_in_client.post("/library/sonarr/folders", data={"path": "/library-root/tv2"})
    assert resp.status_code == 200


async def test_add_folder_failure_shows_error(logged_in_client):
    with patch("app.library.folders.add_folder", AsyncMock(return_value=None)):
        resp = await logged_in_client.post("/library/sonarr/folders", data={"path": "/library-root/tv2"})
    assert resp.status_code == 200
    assert "erreur" in resp.text.lower()


async def test_remove_folder(logged_in_client):
    with patch("app.library.folders.remove_folder", AsyncMock(return_value=True)):
        resp = await logged_in_client.delete("/library/sonarr/folders/1")
    assert resp.status_code == 200


async def test_shares_list_and_add_and_remove(logged_in_client):
    with patch("app.library.shares.list_shares", return_value=[]):
        resp = await logged_in_client.get("/library/shares")
    assert resp.status_code == 200

    with patch("app.library.shares.add_share", AsyncMock(return_value={"id": 1, "slug": "nas"})):
        resp = await logged_in_client.post(
            "/library/shares",
            data={"slug": "nas", "server": "192.168.1.10", "share": "movies", "username": "u", "password": "p"},
        )
    assert resp.status_code == 200

    with patch("app.library.shares.remove_share", AsyncMock(return_value=True)):
        resp = await logged_in_client.delete("/library/shares/1")
    assert resp.status_code == 200

    with patch("app.library.shares.remove_share", AsyncMock(return_value=None)):
        resp = await logged_in_client.delete("/library/shares/1")
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/ui/test_library_router.py -v`
Expected: FAIL — 404s (routes don't exist yet)

- [ ] **Step 3: Add routes to `app/ui/router.py`**

Add these imports at the top (alongside existing `from app.arr import ...`):

```python
from app.library import folders as library_folders
from app.library import shares as library_shares
```

Add these routes at the end of the file:

```python
@router.get("/library/{arr}", response_class=HTMLResponse)
async def library_list(
    request: Request, arr: str, user: dict = Depends(require_login)
) -> HTMLResponse:
    if arr not in _CLIENTS:
        return HTMLResponse("Not found", status_code=404)
    items = library_folders.list_folders(settings.db_path, arr)
    return templates.TemplateResponse(
        request, "_library.html", {"arr": arr, "folders": items, "error": False}
    )


@router.post("/library/{arr}/folders", response_class=HTMLResponse)
async def library_add_folder(
    request: Request, arr: str, path: str = Form(...), user: dict = Depends(require_login)
) -> HTMLResponse:
    if arr not in _CLIENTS:
        return HTMLResponse("Not found", status_code=404)
    result = await library_folders.add_folder(settings.db_path, arr, path)
    items = library_folders.list_folders(settings.db_path, arr)
    return templates.TemplateResponse(
        request, "_library.html", {"arr": arr, "folders": items, "error": result is None}
    )


@router.delete("/library/{arr}/folders/{folder_id}", response_class=HTMLResponse)
async def library_remove_folder(
    request: Request, arr: str, folder_id: int, user: dict = Depends(require_login)
) -> HTMLResponse:
    if arr not in _CLIENTS:
        return HTMLResponse("Not found", status_code=404)
    await library_folders.remove_folder(settings.db_path, folder_id)
    items = library_folders.list_folders(settings.db_path, arr)
    return templates.TemplateResponse(
        request, "_library.html", {"arr": arr, "folders": items, "error": False}
    )


@router.get("/library/shares", response_class=HTMLResponse)
async def shares_list(request: Request, user: dict = Depends(require_login)) -> HTMLResponse:
    items = library_shares.list_shares(settings.db_path)
    return templates.TemplateResponse(
        request, "_shares.html", {"shares": items, "error": False}
    )


@router.post("/library/shares", response_class=HTMLResponse)
async def shares_add(
    request: Request,
    slug: str = Form(...),
    server: str = Form(...),
    share: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    user: dict = Depends(require_login),
) -> HTMLResponse:
    result = await library_shares.add_share(settings.db_path, slug, server, share, username, password)
    items = library_shares.list_shares(settings.db_path)
    return templates.TemplateResponse(
        request, "_shares.html", {"shares": items, "error": result is None}
    )


@router.delete("/library/shares/{share_id}", response_class=HTMLResponse)
async def shares_remove(
    request: Request, share_id: int, user: dict = Depends(require_login)
) -> HTMLResponse:
    result = await library_shares.remove_share(settings.db_path, share_id)
    if result is None:
        return HTMLResponse("Partage encore utilisé par un dossier", status_code=400)
    items = library_shares.list_shares(settings.db_path)
    return templates.TemplateResponse(
        request, "_shares.html", {"shares": items, "error": False}
    )
```

- [ ] **Step 4: Create `app/ui/templates/_library.html`**

```html
<div id="library-{{ arr }}">
  {% if error %}<p class="error">Erreur lors de l'opération sur le dossier.</p>{% endif %}
  <ul>
    {% for f in folders %}
    <li>
      {{ f.path }}
      <button hx-delete="/library/{{ arr }}/folders/{{ f.id }}" hx-target="#library-{{ arr }}" hx-swap="outerHTML">
        Retirer
      </button>
    </li>
    {% endfor %}
  </ul>
  <form hx-post="/library/{{ arr }}/folders" hx-target="#library-{{ arr }}" hx-swap="outerHTML">
    <input type="text" name="path" placeholder="/library-root/..." required>
    <button type="submit">Ajouter</button>
  </form>
</div>
```

- [ ] **Step 5: Create `app/ui/templates/_shares.html`**

```html
<div id="shares-list">
  {% if error %}<p class="error">Erreur lors de l'opération sur le partage.</p>{% endif %}
  <ul>
    {% for s in shares %}
    <li>
      {{ s.slug }} ({{ s.server }}/{{ s.share }})
      <button hx-delete="/library/shares/{{ s.id }}" hx-target="#shares-list" hx-swap="outerHTML">
        Retirer
      </button>
    </li>
    {% endfor %}
  </ul>
  <form hx-post="/library/shares" hx-target="#shares-list" hx-swap="outerHTML">
    <input type="text" name="slug" placeholder="nom" required>
    <input type="text" name="server" placeholder="serveur" required>
    <input type="text" name="share" placeholder="partage" required>
    <input type="text" name="username" placeholder="utilisateur" required>
    <input type="password" name="password" placeholder="mot de passe" required>
    <button type="submit">Monter</button>
  </form>
</div>
```

- [ ] **Step 6: Wire into `app/ui/templates/_tab.html`**

Add at the end of the file (after the existing library table), so each
tab shows its own folder manager, HTMX-loaded on tab open:

```html
<div hx-get="/library/{{ arr }}" hx-trigger="load" hx-swap="outerHTML"></div>
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/ui/test_library_router.py -v`
Expected: PASS (8 tests)

- [ ] **Step 8: Run full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all passing

- [ ] **Step 9: Commit**

```bash
git add app/ui/router.py app/ui/templates/_library.html app/ui/templates/_shares.html app/ui/templates/_tab.html tests/ui/test_library_router.py
git commit -m "feat: add folder/share management UI per tab"
```

---

### Task 8: Export / Import de configuration

**Files:**
- Create: `app/settings/__init__.py`
- Create: `app/settings/router.py`
- Create: `app/settings/export_import.py`
- Modify: `app/main.py` (`app.include_router(settings_router.router)`)
- Test: `tests/settings/test_export_import.py`

**Interfaces:**
- Consumes: `app.library.folders.list_folders` (all 4 arrs),
  `app.library.shares.list_shares` (with password — export needs the raw
  value, unlike the UI-facing `list_shares`, so `export_import.py` reads
  `smb_shares` directly via sqlite3, not through `shares.list_shares`).
- Produces: `build_export(db_path: str) -> dict` (the JSON-serializable
  structure from the spec).
- Produces: `async def apply_import(db_path: str, data: dict) ->
  dict` (returns `{"env_written": bool, "folders_restored": int,
  "shares_restored": int, "errors": list[str]}`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/settings/test_export_import.py
import json
import sqlite3
import time
from unittest.mock import AsyncMock, patch

import pytest

from app.library import db as library_db
from app.settings import export_import


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    library_db.init_db(path)
    return path


def test_build_export_includes_env_and_excludes_machine_local_and_users(db_path):
    data = export_import.build_export(db_path)
    assert data["version"] == 1
    assert "SONARR_API_KEY" in data["env"]
    assert "SESSION_SECRET" not in data["env"]
    assert "USB_MOUNT" not in data["env"]
    assert "HOST_LIBRARY_ROOT" not in data["env"]
    assert "SHARES_MOUNT" not in data["env"]
    assert data["library_folders"] == []
    assert data["smb_shares"] == []


def test_build_export_includes_folders_and_shares_with_password(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO library_folders (arr, path, root_folder_id, created_at) VALUES (?, ?, ?, ?)",
            ("sonarr", "/library-root/tv", "1", time.time()),
        )
        conn.execute(
            "INSERT INTO smb_shares (slug, server, share, username, password, mounted, created_at) VALUES (?, ?, ?, ?, ?, 1, ?)",
            ("nas", "192.168.1.10", "movies", "u", "p", time.time()),
        )
    data = export_import.build_export(db_path)
    assert data["library_folders"] == [{"arr": "sonarr", "path": "/library-root/tv"}]
    assert data["smb_shares"] == [
        {"slug": "nas", "server": "192.168.1.10", "share": "movies", "username": "u", "password": "p"}
    ]


async def test_apply_import_rejects_unknown_version(db_path):
    result = await export_import.apply_import(db_path, {"version": 99})
    assert result["errors"] == ["version d'export non supportée"]
    assert result["env_written"] is False


async def test_apply_import_writes_env_and_restores_folders_and_shares(db_path, tmp_path, monkeypatch):
    from app.config import settings

    env_path = tmp_path / ".env"
    env_path.write_text("SONARR_API_KEY=old\nSESSION_SECRET=keep-me\n")
    monkeypatch.setattr(export_import, "ENV_PATH", str(env_path))

    payload = {
        "version": 1,
        "env": {"SONARR_API_KEY": "new-key"},
        "library_folders": [{"arr": "sonarr", "path": "/library-root/tv"}],
        "smb_shares": [{"slug": "nas", "server": "s", "share": "sh", "username": "u", "password": "p"}],
    }
    with patch("app.library.folders.add_folder", AsyncMock(return_value={"id": 1})), \
         patch("app.library.shares.add_share", AsyncMock(return_value={"id": 1})):
        result = await export_import.apply_import(db_path, payload)

    assert result["env_written"] is True
    assert result["folders_restored"] == 1
    assert result["shares_restored"] == 1
    assert result["errors"] == []
    content = env_path.read_text()
    assert "SONARR_API_KEY=new-key" in content
    assert "SESSION_SECRET=keep-me" in content  # jamais touché
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/settings/test_export_import.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create `app/settings/__init__.py`** (vide) et
  `tests/settings/__init__.py` (vide).

- [ ] **Step 4: Write `app/settings/export_import.py`**

```python
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
    env = {key: getattr(settings, key.lower()) for key in _ENV_KEYS}

    folders = []
    for arr in _ARRS:
        for f in library_folders.list_folders(db_path, arr):
            folders.append({"arr": f["arr"], "path": f["path"]})

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        shares = [
            {"slug": r["slug"], "server": r["server"], "share": r["share"], "username": r["username"], "password": r["password"]}
            for r in conn.execute("SELECT slug, server, share, username, password FROM smb_shares").fetchall()
        ]

    return {
        "version": 1,
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "env": env,
        "library_folders": folders,
        "smb_shares": shares,
    }


def _write_env(env: dict) -> None:
    lines = []
    try:
        with open(ENV_PATH) as f:
            existing = f.read().splitlines()
    except FileNotFoundError:
        existing = []

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

    tmp_path = f"{ENV_PATH}.tmp"
    with open(tmp_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    import os
    os.replace(tmp_path, ENV_PATH)


async def apply_import(db_path: str, data: dict) -> dict:
    errors: list[str] = []
    if data.get("version") != 1:
        return {"env_written": False, "folders_restored": 0, "shares_restored": 0, "errors": ["version d'export non supportée"]}

    env = {k: v for k, v in data.get("env", {}).items() if k not in _EXCLUDED_ENV_KEYS}
    _write_env(env)

    folders_restored = 0
    for entry in data.get("library_folders", []):
        result = await library_folders.add_folder(db_path, entry["arr"], entry["path"])
        if result is None:
            errors.append(f"dossier non restauré: {entry['arr']} {entry['path']}")
        else:
            folders_restored += 1

    shares_restored = 0
    for entry in data.get("smb_shares", []):
        result = await library_shares.add_share(
            db_path, entry["slug"], entry["server"], entry["share"], entry["username"], entry["password"]
        )
        if result is None:
            errors.append(f"partage non restauré: {entry['slug']}")
        else:
            shares_restored += 1

    return {
        "env_written": True,
        "folders_restored": folders_restored,
        "shares_restored": shares_restored,
        "errors": errors,
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/settings/test_export_import.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Write `app/settings/router.py`**

```python
import json
import os

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response

from app.auth.router import require_login
from app.config import settings
from app.settings import export_import

router = APIRouter()


@router.get("/settings/export")
async def export_config(user: dict = Depends(require_login)) -> Response:
    data = export_import.build_export(settings.db_path)
    return Response(
        content=json.dumps(data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=umc-config-export.json"},
    )


@router.post("/settings/import")
async def import_config(user: dict = Depends(require_login), file: UploadFile = File(...)) -> JSONResponse:
    raw = await file.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return JSONResponse({"errors": ["fichier JSON invalide"]}, status_code=400)

    result = await export_import.apply_import(settings.db_path, data)
    if result["errors"] and not result["env_written"]:
        return JSONResponse(result, status_code=400)

    response = JSONResponse(result)

    async def _restart() -> None:
        os._exit(0)

    import asyncio
    asyncio.get_event_loop().call_later(1, lambda: os._exit(0))
    return response
```

Note d'implémentation : le redémarrage (`os._exit(0)`) est différé d'une
seconde via `call_later` pour laisser la réponse HTTP partir avant que le
process ne s'arrête — `restart: unless-stopped` (déjà en place dans
`docker-compose.yml` pour `app`) relance le container avec le nouvel
`.env`.

- [ ] **Step 7: Wire router into `app/main.py`**

```diff
+from app.settings import router as settings_router
```

```diff
 app.include_router(ui_router.router)
+app.include_router(settings_router.router)
```

- [ ] **Step 8: Run full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all passing

- [ ] **Step 9: Commit**

```bash
git add app/settings/ app/main.py tests/settings/
git commit -m "feat: add config export/import endpoints"
```

---

### Task 9: `install.sh` — prompt `HOST_LIBRARY_ROOT`

**Files:**
- Modify: `install.sh`
- Modify: `.env.example`

**Interfaces:**
- Consumes: rien de nouveau — même pattern que le prompt USB existant
  dans `generate_env()`.

- [ ] **Step 1: Add to `.env.example`**

```diff
 USB_MOUNT=
+HOST_LIBRARY_ROOT=
+SHARES_MOUNT=
```

- [ ] **Step 2: Add prompt in `install.sh::generate_env`**

After the existing `usb_mount` prompt block (before the `local
sonarr_api_key ...` line), add:

```bash
  local host_library_root
  read -r -p "Dossier racine pour les bibliothèques ajoutées depuis l'UI (défaut : \$HOME) : " host_library_root < /dev/tty
  host_library_root="${host_library_root:-$HOME}"
```

Then add these two substitutions to the existing `sed` command (alongside
`s#^USB_MOUNT=.*#...#`):

```diff
     -e "s#^USB_MOUNT=.*#USB_MOUNT=${usb_mount}#" \
+    -e "s#^HOST_LIBRARY_ROOT=.*#HOST_LIBRARY_ROOT=${host_library_root}#" \
+    -e "s#^SHARES_MOUNT=.*#SHARES_MOUNT=${TARGET_DIR}/shares#" \
```

`SHARES_MOUNT` reste un sous-dossier de `TARGET_DIR` (pas une saisie
utilisateur) — c'est un dossier technique pour les mounts CIFS gérés par
l'app, pas un choix de l'utilisateur.

- [ ] **Step 3: Create the shares directory in `generate_env`**

After `mkdir -p "${usb_mount}/tv" ...` line, add:

```diff
   mkdir -p "${usb_mount}/tv" "${usb_mount}/movies" "${usb_mount}/music" "${usb_mount}/books-library"
+  mkdir -p "${TARGET_DIR}/shares"
```

- [ ] **Step 4: Verify shellcheck clean**

Run: `docker run --rm -v "$(pwd):/mnt" -w /mnt koalaman/shellcheck:stable install.sh`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add install.sh .env.example
git commit -m "feat: install.sh prompts for HOST_LIBRARY_ROOT"
```

---

### Task 10: Documentation

**Files:**
- Modify: `.ai/02-ARCHITECTURE.md`
- Modify: `.ai/05-DEPLOYMENT.md`
- Modify: `docs/user/guide.md`

- [ ] **Step 1: `.ai/02-ARCHITECTURE.md`**

Add a new numbered component after "5. Authentification":

```markdown
### 6. Gestion des dossiers de bibliothèque
Le container `app` est privilégié (`CAP_SYS_ADMIN`) pour monter des
partages SMB ajoutés depuis l'UI (`mount -t cifs`, propagation `shared`
vers l'hôte). Les dossiers ajoutés (locaux ou SMB) sont enregistrés comme
root folders via l'API déjà exposée par chaque *arr — voir ADR 0005.
```

- [ ] **Step 2: `.ai/05-DEPLOYMENT.md`**

Add to the environment variables section (find the existing `USB_MOUNT`
documentation and add alongside it):

```markdown
- `HOST_LIBRARY_ROOT` : dossier hôte large monté dans `app` + les *arr +
  Jellyfin, sert de racine pour tout dossier ajouté depuis l'UI.
- `SHARES_MOUNT` : dossier technique où l'app monte les partages SMB
  ajoutés depuis l'UI (`mount -t cifs`), monté avec propagation `shared`.
```

- [ ] **Step 3: `docs/user/guide.md`**

Add two new sections (after the existing re-match section):

```markdown
## Ajouter un dossier ou un partage réseau

Sur chaque onglet, un formulaire en bas de page permet d'ajouter un
dossier (chemin sous ta racine bibliothèque) ou un partage réseau SMB
(serveur, partage, identifiants). Une fois ajouté, il apparaît directement
dans le *arr concerné comme un nouveau dossier surveillé.

## Exporter / importer la configuration

`/settings/export` télécharge un fichier JSON avec toute ta configuration
(clés API, dossiers, partages réseau — identifiants inclus en clair,
à conserver en lieu sûr). `/settings/import` restaure ce fichier sur une
autre installation ; l'application redémarre automatiquement à la fin de
l'import.
```

- [ ] **Step 4: Commit**

```bash
git add .ai/02-ARCHITECTURE.md .ai/05-DEPLOYMENT.md docs/user/guide.md
git commit -m "docs: document configurable library folders and config export/import"
```

---

## Self-Review Notes (already applied above)
- Spec coverage : montage large local (Task 6), SMB géré par l'app (Task
  4+6), enregistrement root-folder (Task 2-3), export/import hors `users`
  et hors secrets machine-locale (Task 8), `install.sh` (Task 9), docs
  (Task 10) — couvert.
- Jellyfin volontairement hors périmètre (cf. Global Constraints) — pas de
  tâche orpheline le référençant.
- Types cohérents : `add_folder`/`add_share` renvoient `dict | None`
  partout où consommés (Task 7, Task 8) ; `remove_share` renvoie `bool |
  None` et Task 7 gère bien les trois cas (`True`/`False`/`None`).
