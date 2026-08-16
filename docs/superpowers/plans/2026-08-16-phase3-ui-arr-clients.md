# Phase 3 — UI unifiée + clients *arr — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter un cache SQLite TTL, des clients API lecture-seule pour Sonarr/Radarr/Lidarr/Readarr, et une UI à tabs (Jinja2 + HTMX) affichant queue active et bibliothèque paginée.

**Architecture:** Les clients *arr lisent d'abord le cache SQLite TTL ; si expiré, ils appellent l'API *arr (httpx, 5s timeout) et mettent à jour le cache. Le router UI lit les clients et rend des templates Jinja2 ; HTMX recharge chaque onglet indépendamment via `GET /tab/{arr}?page=N`.

**Tech Stack:** FastAPI, Jinja2, HTMX (CDN), Pico CSS (CDN), SQLite (stdlib), httpx, pydantic-settings, pytest + respx

---

## Fichiers créés/modifiés

| Fichier | Action |
|---|---|
| `app/arr/__init__.py` | Créer (vide) |
| `app/arr/cache.py` | Créer — SQLite TTL (init_db / get / set) |
| `app/arr/sonarr.py` | Créer — client Sonarr (queue / library) |
| `app/arr/radarr.py` | Créer — client Radarr |
| `app/arr/lidarr.py` | Créer — client Lidarr |
| `app/arr/readarr.py` | Créer — client Readarr |
| `app/ui/__init__.py` | Créer (vide) |
| `app/ui/router.py` | Créer — routes GET / et GET /tab/{arr} |
| `app/ui/templates/base.html` | Créer |
| `app/ui/templates/index.html` | Créer |
| `app/ui/templates/_tab.html` | Créer |
| `app/config.py` | Modifier — +9 champs |
| `app/main.py` | Modifier — montage UI router + init DB |
| `pyproject.toml` | Modifier — ajouter `jinja2` |
| `docker-compose.yml` | Modifier — volume `app-data` pour SQLite |
| `.env.example` | Modifier — +9 variables |
| `tests/conftest.py` | Modifier — +8 os.environ |
| `tests/arr/__init__.py` | Créer (vide) |
| `tests/arr/test_cache.py` | Créer |
| `tests/arr/test_sonarr.py` | Créer |
| `tests/arr/test_radarr.py` | Créer |
| `tests/arr/test_lidarr.py` | Créer |
| `tests/arr/test_readarr.py` | Créer |
| `tests/ui/__init__.py` | Créer (vide) |
| `tests/ui/test_router.py` | Créer |

---

### Task 1: Config + conftest + .env.example

**Files:**
- Modify: `app/config.py`
- Modify: `tests/conftest.py`
- Modify: `.env.example`

`Settings()` s'instancie au chargement du module. Les 8 nouvelles variables URL/API key sont requises — si absentes en test, pytest lève `ValidationError` avant d'exécuter quoi que ce soit.

- [ ] **Step 1 : Mettre à jour `app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ntfy_url: str
    ntfy_topic: str
    sonarr_secret: str
    radarr_secret: str
    lidarr_secret: str
    readarr_secret: str
    sonarr_url: str
    sonarr_api_key: str
    radarr_url: str
    radarr_api_key: str
    lidarr_url: str
    lidarr_api_key: str
    readarr_url: str
    readarr_api_key: str
    cache_ttl: int = 30
    db_path: str = "data/cache.db"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
```

- [ ] **Step 2 : Mettre à jour `tests/conftest.py`**

```python
import os

os.environ["NTFY_URL"] = "http://ntfy-test:80"
os.environ["NTFY_TOPIC"] = "test"
os.environ["SONARR_SECRET"] = "test-secret"
os.environ["RADARR_SECRET"] = "test-secret"
os.environ["LIDARR_SECRET"] = "test-secret"
os.environ["READARR_SECRET"] = "test-secret"
os.environ["SONARR_URL"] = "http://sonarr-test:8989"
os.environ["SONARR_API_KEY"] = "test-api-key"
os.environ["RADARR_URL"] = "http://radarr-test:7878"
os.environ["RADARR_API_KEY"] = "test-api-key"
os.environ["LIDARR_URL"] = "http://lidarr-test:8686"
os.environ["LIDARR_API_KEY"] = "test-api-key"
os.environ["READARR_URL"] = "http://readarr-test:8787"
os.environ["READARR_API_KEY"] = "test-api-key"
os.environ["DB_PATH"] = ":memory:"

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client() -> AsyncClient:
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
```

- [ ] **Step 3 : Mettre à jour `.env.example`**

```env
NTFY_URL=http://ntfy:80
NTFY_TOPIC=mediacenter
SONARR_SECRET=changeme
RADARR_SECRET=changeme
LIDARR_SECRET=changeme
READARR_SECRET=changeme
SONARR_URL=http://sonarr:8989
SONARR_API_KEY=changeme
RADARR_URL=http://radarr:7878
RADARR_API_KEY=changeme
LIDARR_URL=http://lidarr:8686
LIDARR_API_KEY=changeme
READARR_URL=http://readarr:8787
READARR_API_KEY=changeme
CACHE_TTL=30
DB_PATH=data/cache.db
```

- [ ] **Step 4 : Vérifier que les tests existants passent**

```bash
.venv/bin/pytest tests/ -v
```

Expected: 29 passed.

- [ ] **Step 5 : Commit**

```bash
git add app/config.py tests/conftest.py .env.example
git commit -m "feat: add arr url/api_key settings for phase 3"
```

---

### Task 2: SQLite cache (TDD)

**Files:**
- Create: `app/arr/__init__.py`
- Create: `app/arr/cache.py`
- Create: `tests/arr/__init__.py`
- Create: `tests/arr/test_cache.py`

- [ ] **Step 1 : Créer les `__init__.py` vides**

```bash
touch app/arr/__init__.py tests/arr/__init__.py
```

- [ ] **Step 2 : Écrire les tests**

Créer `tests/arr/test_cache.py` :

```python
import time
import pytest
from app.arr.cache import get, init_db
from app.arr.cache import set as cache_set


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "cache.db")
    init_db(db_path)
    return db_path


async def test_get_missing_key_returns_none(db):
    assert get(db, "missing") is None


async def test_get_expired_key_returns_none(db):
    cache_set(db, "key", {"v": 1}, ttl=0)
    time.sleep(0.01)
    assert get(db, "key") is None


async def test_get_valid_key_returns_data(db):
    cache_set(db, "key", {"v": 42}, ttl=60)
    assert get(db, "key") == {"v": 42}


async def test_set_list_roundtrip(db):
    cache_set(db, "list", [1, 2, 3], ttl=60)
    assert get(db, "list") == [1, 2, 3]


async def test_set_upsert_overwrites(db):
    cache_set(db, "key", {"v": 1}, ttl=60)
    cache_set(db, "key", {"v": 2}, ttl=60)
    assert get(db, "key") == {"v": 2}
```

- [ ] **Step 3 : Vérifier que les tests échouent**

```bash
.venv/bin/pytest tests/arr/test_cache.py -v
```

Expected: `ImportError: No module named 'app.arr.cache'`

- [ ] **Step 4 : Implémenter `app/arr/cache.py`**

```python
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
```

- [ ] **Step 5 : Vérifier que les tests passent**

```bash
.venv/bin/pytest tests/arr/test_cache.py -v
```

Expected: 5 passed.

- [ ] **Step 6 : Lancer la suite complète**

```bash
.venv/bin/pytest tests/ -v
```

Expected: 34 passed.

- [ ] **Step 7 : Commit**

```bash
git add app/arr/__init__.py app/arr/cache.py tests/arr/__init__.py tests/arr/test_cache.py
git commit -m "feat: add SQLite TTL cache"
```

---

### Task 3: Client Sonarr (TDD)

**Files:**
- Create: `app/arr/sonarr.py`
- Create: `tests/arr/test_sonarr.py`

Les clients retournent `list[dict]` en cas de succès, `None` en cas d'erreur httpx. Le router UI interprète `None` comme "service indisponible".

- [ ] **Step 1 : Écrire les tests**

Créer `tests/arr/test_sonarr.py` :

```python
import httpx
import pytest
import respx

from app.arr import sonarr


@pytest.fixture
def db(tmp_path, monkeypatch):
    from app.arr import cache
    from app.config import settings

    db_path = str(tmp_path / "cache.db")
    monkeypatch.setattr(settings, "db_path", db_path)
    cache.init_db(db_path)
    return db_path


@respx.mock
async def test_queue_hits_api_on_cache_miss(db):
    respx.get("http://sonarr-test:8989/api/v3/queue").mock(
        return_value=httpx.Response(200, json={"records": [{"title": "ep1", "status": "queued"}]})
    )
    result = await sonarr.queue()
    assert result == [{"title": "ep1", "status": "queued"}]
    assert respx.calls.call_count == 1


@respx.mock
async def test_queue_returns_cache_on_hit(db):
    from app.arr import cache
    from app.config import settings

    cache.set(settings.db_path, "sonarr:queue", [{"title": "cached"}], ttl=60)
    result = await sonarr.queue()
    assert result == [{"title": "cached"}]
    assert not respx.calls


@respx.mock
async def test_library_hits_api_on_cache_miss(db):
    respx.get("http://sonarr-test:8989/api/v3/series").mock(
        return_value=httpx.Response(200, json=[{"title": "The Boys", "monitored": True}])
    )
    result = await sonarr.library()
    assert result == [{"title": "The Boys", "monitored": True}]


@respx.mock
async def test_queue_returns_none_on_http_error(db):
    respx.get("http://sonarr-test:8989/api/v3/queue").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    result = await sonarr.queue()
    assert result is None
```

- [ ] **Step 2 : Vérifier que les tests échouent**

```bash
.venv/bin/pytest tests/arr/test_sonarr.py -v
```

Expected: `ImportError: cannot import name 'sonarr' from 'app.arr'`

- [ ] **Step 3 : Implémenter `app/arr/sonarr.py`**

```python
import logging

import httpx

from app.arr import cache
from app.config import settings

logger = logging.getLogger(__name__)


async def queue() -> list[dict] | None:
    key = "sonarr:queue"
    cached = cache.get(settings.db_path, key)
    if cached is not None:
        return cached
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.sonarr_url}/api/v3/queue",
                headers={"X-Api-Key": settings.sonarr_api_key},
                params={"pageSize": 100},
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json().get("records", [])
    except httpx.HTTPError as exc:
        logger.error("sonarr queue failed", extra={"error": str(exc)})
        return None
    cache.set(settings.db_path, key, data, settings.cache_ttl)
    return data


async def library() -> list[dict] | None:
    key = "sonarr:library"
    cached = cache.get(settings.db_path, key)
    if cached is not None:
        return cached
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.sonarr_url}/api/v3/series",
                headers={"X-Api-Key": settings.sonarr_api_key},
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        logger.error("sonarr library failed", extra={"error": str(exc)})
        return None
    cache.set(settings.db_path, key, data, settings.cache_ttl)
    return data
```

- [ ] **Step 4 : Vérifier que les tests passent**

```bash
.venv/bin/pytest tests/arr/test_sonarr.py -v
```

Expected: 4 passed.

- [ ] **Step 5 : Lancer la suite complète**

```bash
.venv/bin/pytest tests/ -v
```

Expected: 38 passed.

- [ ] **Step 6 : Commit**

```bash
git add app/arr/sonarr.py tests/arr/test_sonarr.py
git commit -m "feat: add sonarr API client with SQLite cache"
```

---

### Task 4: Client Radarr (TDD)

**Files:**
- Create: `app/arr/radarr.py`
- Create: `tests/arr/test_radarr.py`

Même pattern que Task 3. Radarr : queue → `GET /api/v3/queue` (champ `records`), library → `GET /api/v3/movie` (liste directe).

- [ ] **Step 1 : Écrire les tests**

Créer `tests/arr/test_radarr.py` :

```python
import httpx
import pytest
import respx

from app.arr import radarr


@pytest.fixture
def db(tmp_path, monkeypatch):
    from app.arr import cache
    from app.config import settings

    db_path = str(tmp_path / "cache.db")
    monkeypatch.setattr(settings, "db_path", db_path)
    cache.init_db(db_path)
    return db_path


@respx.mock
async def test_queue_hits_api_on_cache_miss(db):
    respx.get("http://radarr-test:7878/api/v3/queue").mock(
        return_value=httpx.Response(200, json={"records": [{"title": "movie1", "status": "queued"}]})
    )
    result = await radarr.queue()
    assert result == [{"title": "movie1", "status": "queued"}]
    assert respx.calls.call_count == 1


@respx.mock
async def test_queue_returns_cache_on_hit(db):
    from app.arr import cache
    from app.config import settings

    cache.set(settings.db_path, "radarr:queue", [{"title": "cached"}], ttl=60)
    result = await radarr.queue()
    assert result == [{"title": "cached"}]
    assert not respx.calls


@respx.mock
async def test_library_hits_api_on_cache_miss(db):
    respx.get("http://radarr-test:7878/api/v3/movie").mock(
        return_value=httpx.Response(200, json=[{"title": "Inception", "monitored": True}])
    )
    result = await radarr.library()
    assert result == [{"title": "Inception", "monitored": True}]


@respx.mock
async def test_queue_returns_none_on_http_error(db):
    respx.get("http://radarr-test:7878/api/v3/queue").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    result = await radarr.queue()
    assert result is None
```

- [ ] **Step 2 : Vérifier que les tests échouent**

```bash
.venv/bin/pytest tests/arr/test_radarr.py -v
```

Expected: `ImportError`

- [ ] **Step 3 : Implémenter `app/arr/radarr.py`**

```python
import logging

import httpx

from app.arr import cache
from app.config import settings

logger = logging.getLogger(__name__)


async def queue() -> list[dict] | None:
    key = "radarr:queue"
    cached = cache.get(settings.db_path, key)
    if cached is not None:
        return cached
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.radarr_url}/api/v3/queue",
                headers={"X-Api-Key": settings.radarr_api_key},
                params={"pageSize": 100},
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json().get("records", [])
    except httpx.HTTPError as exc:
        logger.error("radarr queue failed", extra={"error": str(exc)})
        return None
    cache.set(settings.db_path, key, data, settings.cache_ttl)
    return data


async def library() -> list[dict] | None:
    key = "radarr:library"
    cached = cache.get(settings.db_path, key)
    if cached is not None:
        return cached
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.radarr_url}/api/v3/movie",
                headers={"X-Api-Key": settings.radarr_api_key},
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        logger.error("radarr library failed", extra={"error": str(exc)})
        return None
    cache.set(settings.db_path, key, data, settings.cache_ttl)
    return data
```

- [ ] **Step 4 : Vérifier que les tests passent**

```bash
.venv/bin/pytest tests/arr/test_radarr.py -v
```

Expected: 4 passed.

- [ ] **Step 5 : Lancer la suite complète**

```bash
.venv/bin/pytest tests/ -v
```

Expected: 42 passed.

- [ ] **Step 6 : Commit**

```bash
git add app/arr/radarr.py tests/arr/test_radarr.py
git commit -m "feat: add radarr API client with SQLite cache"
```

---

### Task 5: Client Lidarr (TDD)

**Files:**
- Create: `app/arr/lidarr.py`
- Create: `tests/arr/test_lidarr.py`

Lidarr : queue → `GET /api/v3/queue` (champ `records`), library → `GET /api/v3/artist` (liste directe, champ `artistName` au lieu de `title`).

- [ ] **Step 1 : Écrire les tests**

Créer `tests/arr/test_lidarr.py` :

```python
import httpx
import pytest
import respx

from app.arr import lidarr


@pytest.fixture
def db(tmp_path, monkeypatch):
    from app.arr import cache
    from app.config import settings

    db_path = str(tmp_path / "cache.db")
    monkeypatch.setattr(settings, "db_path", db_path)
    cache.init_db(db_path)
    return db_path


@respx.mock
async def test_queue_hits_api_on_cache_miss(db):
    respx.get("http://lidarr-test:8686/api/v3/queue").mock(
        return_value=httpx.Response(200, json={"records": [{"title": "album1", "status": "queued"}]})
    )
    result = await lidarr.queue()
    assert result == [{"title": "album1", "status": "queued"}]
    assert respx.calls.call_count == 1


@respx.mock
async def test_queue_returns_cache_on_hit(db):
    from app.arr import cache
    from app.config import settings

    cache.set(settings.db_path, "lidarr:queue", [{"title": "cached"}], ttl=60)
    result = await lidarr.queue()
    assert result == [{"title": "cached"}]
    assert not respx.calls


@respx.mock
async def test_library_hits_api_on_cache_miss(db):
    respx.get("http://lidarr-test:8686/api/v3/artist").mock(
        return_value=httpx.Response(200, json=[{"artistName": "Radiohead", "monitored": True}])
    )
    result = await lidarr.library()
    assert result == [{"artistName": "Radiohead", "monitored": True}]


@respx.mock
async def test_queue_returns_none_on_http_error(db):
    respx.get("http://lidarr-test:8686/api/v3/queue").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    result = await lidarr.queue()
    assert result is None
```

- [ ] **Step 2 : Vérifier que les tests échouent**

```bash
.venv/bin/pytest tests/arr/test_lidarr.py -v
```

Expected: `ImportError`

- [ ] **Step 3 : Implémenter `app/arr/lidarr.py`**

```python
import logging

import httpx

from app.arr import cache
from app.config import settings

logger = logging.getLogger(__name__)


async def queue() -> list[dict] | None:
    key = "lidarr:queue"
    cached = cache.get(settings.db_path, key)
    if cached is not None:
        return cached
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.lidarr_url}/api/v3/queue",
                headers={"X-Api-Key": settings.lidarr_api_key},
                params={"pageSize": 100},
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json().get("records", [])
    except httpx.HTTPError as exc:
        logger.error("lidarr queue failed", extra={"error": str(exc)})
        return None
    cache.set(settings.db_path, key, data, settings.cache_ttl)
    return data


async def library() -> list[dict] | None:
    key = "lidarr:library"
    cached = cache.get(settings.db_path, key)
    if cached is not None:
        return cached
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.lidarr_url}/api/v3/artist",
                headers={"X-Api-Key": settings.lidarr_api_key},
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        logger.error("lidarr library failed", extra={"error": str(exc)})
        return None
    cache.set(settings.db_path, key, data, settings.cache_ttl)
    return data
```

- [ ] **Step 4 : Vérifier que les tests passent**

```bash
.venv/bin/pytest tests/arr/test_lidarr.py -v
```

Expected: 4 passed.

- [ ] **Step 5 : Lancer la suite complète**

```bash
.venv/bin/pytest tests/ -v
```

Expected: 46 passed.

- [ ] **Step 6 : Commit**

```bash
git add app/arr/lidarr.py tests/arr/test_lidarr.py
git commit -m "feat: add lidarr API client with SQLite cache"
```

---

### Task 6: Client Readarr (TDD)

**Files:**
- Create: `app/arr/readarr.py`
- Create: `tests/arr/test_readarr.py`

Readarr : queue → `GET /api/v3/queue` (champ `records`), library → `GET /api/v3/book` (liste directe).

- [ ] **Step 1 : Écrire les tests**

Créer `tests/arr/test_readarr.py` :

```python
import httpx
import pytest
import respx

from app.arr import readarr


@pytest.fixture
def db(tmp_path, monkeypatch):
    from app.arr import cache
    from app.config import settings

    db_path = str(tmp_path / "cache.db")
    monkeypatch.setattr(settings, "db_path", db_path)
    cache.init_db(db_path)
    return db_path


@respx.mock
async def test_queue_hits_api_on_cache_miss(db):
    respx.get("http://readarr-test:8787/api/v3/queue").mock(
        return_value=httpx.Response(200, json={"records": [{"title": "book1", "status": "queued"}]})
    )
    result = await readarr.queue()
    assert result == [{"title": "book1", "status": "queued"}]
    assert respx.calls.call_count == 1


@respx.mock
async def test_queue_returns_cache_on_hit(db):
    from app.arr import cache
    from app.config import settings

    cache.set(settings.db_path, "readarr:queue", [{"title": "cached"}], ttl=60)
    result = await readarr.queue()
    assert result == [{"title": "cached"}]
    assert not respx.calls


@respx.mock
async def test_library_hits_api_on_cache_miss(db):
    respx.get("http://readarr-test:8787/api/v3/book").mock(
        return_value=httpx.Response(200, json=[{"title": "Dune", "monitored": True}])
    )
    result = await readarr.library()
    assert result == [{"title": "Dune", "monitored": True}]


@respx.mock
async def test_queue_returns_none_on_http_error(db):
    respx.get("http://readarr-test:8787/api/v3/queue").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    result = await readarr.queue()
    assert result is None
```

- [ ] **Step 2 : Vérifier que les tests échouent**

```bash
.venv/bin/pytest tests/arr/test_readarr.py -v
```

Expected: `ImportError`

- [ ] **Step 3 : Implémenter `app/arr/readarr.py`**

```python
import logging

import httpx

from app.arr import cache
from app.config import settings

logger = logging.getLogger(__name__)


async def queue() -> list[dict] | None:
    key = "readarr:queue"
    cached = cache.get(settings.db_path, key)
    if cached is not None:
        return cached
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.readarr_url}/api/v3/queue",
                headers={"X-Api-Key": settings.readarr_api_key},
                params={"pageSize": 100},
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json().get("records", [])
    except httpx.HTTPError as exc:
        logger.error("readarr queue failed", extra={"error": str(exc)})
        return None
    cache.set(settings.db_path, key, data, settings.cache_ttl)
    return data


async def library() -> list[dict] | None:
    key = "readarr:library"
    cached = cache.get(settings.db_path, key)
    if cached is not None:
        return cached
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.readarr_url}/api/v3/book",
                headers={"X-Api-Key": settings.readarr_api_key},
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        logger.error("readarr library failed", extra={"error": str(exc)})
        return None
    cache.set(settings.db_path, key, data, settings.cache_ttl)
    return data
```

- [ ] **Step 4 : Vérifier que les tests passent**

```bash
.venv/bin/pytest tests/arr/test_readarr.py -v
```

Expected: 4 passed.

- [ ] **Step 5 : Lancer la suite complète**

```bash
.venv/bin/pytest tests/ -v
```

Expected: 50 passed.

- [ ] **Step 6 : Commit**

```bash
git add app/arr/readarr.py tests/arr/test_readarr.py
git commit -m "feat: add readarr API client with SQLite cache"
```

---

### Task 7: UI router + templates (TDD)

**Files:**
- Create: `app/ui/__init__.py`
- Create: `app/ui/router.py`
- Create: `app/ui/templates/base.html`
- Create: `app/ui/templates/index.html`
- Create: `app/ui/templates/_tab.html`
- Create: `tests/ui/__init__.py`
- Create: `tests/ui/test_router.py`
- Modify: `pyproject.toml` (ajouter `jinja2`)

Jinja2 doit être dans les dépendances avant que `app/ui/router.py` puisse être importé.

- [ ] **Step 1 : Ajouter `jinja2` à `pyproject.toml`**

```toml
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "httpx>=0.27.0",
    "pydantic-settings>=2.4.0",
    "jinja2>=3.1.0",
]
```

Installer dans le venv :

```bash
.venv/bin/pip install jinja2
```

- [ ] **Step 2 : Créer les `__init__.py` vides**

```bash
touch app/ui/__init__.py tests/ui/__init__.py
```

- [ ] **Step 3 : Écrire les tests**

Créer `tests/ui/test_router.py` :

```python
import pytest
from httpx import AsyncClient


async def test_index_returns_200_with_tabs(client: AsyncClient, monkeypatch):
    monkeypatch.setattr("app.arr.sonarr.queue", lambda: [])
    monkeypatch.setattr("app.arr.sonarr.library", lambda: [])
    response = await client.get("/")
    assert response.status_code == 200
    assert "Séries" in response.text
    assert "Films" in response.text
    assert "Musique" in response.text
    assert "Livres" in response.text


async def test_tab_sonarr_returns_200(client: AsyncClient, monkeypatch):
    monkeypatch.setattr("app.arr.sonarr.queue", lambda: [])
    monkeypatch.setattr("app.arr.sonarr.library", lambda: [{"title": "The Boys", "monitored": True}])
    response = await client.get("/tab/sonarr")
    assert response.status_code == 200
    assert "The Boys" in response.text


async def test_tab_pagination(client: AsyncClient, monkeypatch):
    library = [{"title": f"Series {i}", "monitored": True} for i in range(30)]
    monkeypatch.setattr("app.arr.sonarr.queue", lambda: [])
    monkeypatch.setattr("app.arr.sonarr.library", lambda: library)
    response = await client.get("/tab/sonarr?page=2")
    assert response.status_code == 200
    assert "Series 25" in response.text
    assert "Series 0" not in response.text


async def test_tab_service_unavailable(client: AsyncClient, monkeypatch):
    monkeypatch.setattr("app.arr.sonarr.queue", lambda: None)
    monkeypatch.setattr("app.arr.sonarr.library", lambda: None)
    response = await client.get("/tab/sonarr")
    assert response.status_code == 200
    assert "Service indisponible" in response.text
```

Note : les monkeypatches utilisent des lambdas synchrones. Le router appelle `await client.queue()` — les fonctions *arr sont `async def`. Il faut donc patcher avec des coroutines ou utiliser `AsyncMock`. Utilise plutôt :

```python
async def _empty():
    return []

async def _none():
    return None

monkeypatch.setattr("app.arr.sonarr.queue", _empty)
```

Réécrire `tests/ui/test_router.py` avec des coroutines :

```python
import pytest
from httpx import AsyncClient


async def test_index_returns_200_with_tabs(client: AsyncClient, monkeypatch):
    async def _empty():
        return []

    monkeypatch.setattr("app.arr.sonarr.queue", _empty)
    monkeypatch.setattr("app.arr.sonarr.library", _empty)
    response = await client.get("/")
    assert response.status_code == 200
    assert "Séries" in response.text
    assert "Films" in response.text
    assert "Musique" in response.text
    assert "Livres" in response.text


async def test_tab_sonarr_returns_200(client: AsyncClient, monkeypatch):
    async def _queue():
        return []

    async def _library():
        return [{"title": "The Boys", "monitored": True}]

    monkeypatch.setattr("app.arr.sonarr.queue", _queue)
    monkeypatch.setattr("app.arr.sonarr.library", _library)
    response = await client.get("/tab/sonarr")
    assert response.status_code == 200
    assert "The Boys" in response.text


async def test_tab_pagination(client: AsyncClient, monkeypatch):
    async def _queue():
        return []

    async def _library():
        return [{"title": f"Series {i}", "monitored": True} for i in range(30)]

    monkeypatch.setattr("app.arr.sonarr.queue", _queue)
    monkeypatch.setattr("app.arr.sonarr.library", _library)
    response = await client.get("/tab/sonarr?page=2")
    assert response.status_code == 200
    assert "Series 25" in response.text
    assert "Series 0" not in response.text


async def test_tab_service_unavailable(client: AsyncClient, monkeypatch):
    async def _none():
        return None

    monkeypatch.setattr("app.arr.sonarr.queue", _none)
    monkeypatch.setattr("app.arr.sonarr.library", _none)
    response = await client.get("/tab/sonarr")
    assert response.status_code == 200
    assert "Service indisponible" in response.text
```

- [ ] **Step 4 : Vérifier que les tests échouent**

```bash
.venv/bin/pytest tests/ui/test_router.py -v
```

Expected: `ImportError` ou `404`

- [ ] **Step 5 : Créer `app/ui/router.py`**

```python
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.arr import lidarr, radarr, readarr, sonarr

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

_CLIENTS: dict[str, Any] = {
    "sonarr": sonarr,
    "radarr": radarr,
    "lidarr": lidarr,
    "readarr": readarr,
}

TABS = [
    ("sonarr", "Séries"),
    ("radarr", "Films"),
    ("lidarr", "Musique"),
    ("readarr", "Livres"),
]

PAGE_SIZE = 25


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html", {"request": request, "tabs": TABS}
    )


@router.get("/tab/{arr}", response_class=HTMLResponse)
async def tab(request: Request, arr: str, page: int = 1) -> HTMLResponse:
    if arr not in _CLIENTS:
        return HTMLResponse("Not found", status_code=404)
    client = _CLIENTS[arr]
    all_queue = await client.queue()
    all_library = await client.library()
    error = all_queue is None or all_library is None
    queue_items = all_queue or []
    library_items = all_library or []
    library_page = library_items[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
    has_next = len(library_items) > page * PAGE_SIZE
    return templates.TemplateResponse(
        "_tab.html",
        {
            "request": request,
            "arr": arr,
            "queue": queue_items,
            "library": library_page,
            "page": page,
            "has_next": has_next,
            "error": error,
        },
    )
```

- [ ] **Step 6 : Créer `app/ui/templates/base.html`**

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>UltimateMediaCenter</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
    <script src="https://unpkg.com/htmx.org@2.0.0"></script>
</head>
<body>
    <main class="container">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

- [ ] **Step 7 : Créer `app/ui/templates/index.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>UltimateMediaCenter</h1>
<nav>
    <ul>
        {% for arr, label in tabs %}
        <li>
            <a href="#"
               hx-get="/tab/{{ arr }}"
               hx-target="#tab-content"
               hx-push-url="/?tab={{ arr }}">
                {{ label }}
            </a>
        </li>
        {% endfor %}
    </ul>
</nav>
<div id="tab-content"
     hx-get="/tab/sonarr"
     hx-trigger="load">
    Chargement…
</div>
{% endblock %}
```

- [ ] **Step 8 : Créer `app/ui/templates/_tab.html`**

```html
{% if error %}
<p><strong>Service indisponible.</strong></p>
{% else %}

<section>
    <h2>Queue active</h2>
    {% if queue %}
    <table>
        <thead>
            <tr><th>Titre</th><th>Statut</th></tr>
        </thead>
        <tbody>
            {% for item in queue %}
            <tr>
                <td>{{ item.get("title", "—") }}</td>
                <td>{{ item.get("status", "—") }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <p>Aucun téléchargement en cours.</p>
    {% endif %}
</section>

<section>
    <h2>Bibliothèque</h2>
    {% if library %}
    <table>
        <thead>
            <tr><th>Titre</th><th>Suivi</th></tr>
        </thead>
        <tbody>
            {% for item in library %}
            <tr>
                <td>{{ item.get("title") or item.get("artistName", "—") }}</td>
                <td>{{ "✓" if item.get("monitored") else "✗" }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    <nav>
        {% if page > 1 %}
        <a href="#"
           hx-get="/tab/{{ arr }}?page={{ page - 1 }}"
           hx-target="#tab-content">
            ← Précédent
        </a>
        {% endif %}
        {% if has_next %}
        <a href="#"
           hx-get="/tab/{{ arr }}?page={{ page + 1 }}"
           hx-target="#tab-content">
            Suivant →
        </a>
        {% endif %}
    </nav>
    {% else %}
    <p>Aucun élément.</p>
    {% endif %}
</section>

{% endif %}
```

- [ ] **Step 9 : Vérifier que les tests passent**

```bash
.venv/bin/pytest tests/ui/test_router.py -v
```

Expected: 4 passed.

- [ ] **Step 10 : Lancer la suite complète**

```bash
.venv/bin/pytest tests/ -v
```

Expected: 54 passed.

- [ ] **Step 11 : Commit**

```bash
git add app/ui/ tests/ui/ pyproject.toml
git commit -m "feat: add UI router and Jinja2/HTMX templates"
```

---

### Task 8: Câblage main.py + volume Docker

**Files:**
- Modify: `app/main.py`
- Modify: `docker-compose.yml`

- [ ] **Step 1 : Mettre à jour `app/main.py`**

Utilise le pattern `lifespan` (le décorateur `on_event` est déprécié depuis FastAPI 0.93).

```python
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.arr import cache
from app.config import settings
from app.ui import router as ui_router
from app.webhooks import lidarr, radarr, readarr, sonarr


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    cache.init_db(settings.db_path)
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(sonarr.router)
app.include_router(radarr.router)
app.include_router(lidarr.router)
app.include_router(readarr.router)
app.include_router(ui_router.router)
```

- [ ] **Step 2 : Mettre à jour `docker-compose.yml`**

Ajouter `volumes: - app-data:/app/data` au service `app`, et déclarer le volume :

```yaml
services:
  app:
    build: .
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      - ntfy
    volumes:
      - app-data:/app/data
    restart: unless-stopped

  ntfy:
    image: binwiederhier/ntfy:latest
    command: serve
    environment:
      - NTFY_BASE_URL=http://localhost
    ports:
      - "8080:80"
    volumes:
      - ntfy-data:/var/cache/ntfy
      - ntfy-etc:/etc/ntfy
    restart: unless-stopped

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
    restart: unless-stopped

  radarr:
    image: linuxserver/radarr:latest
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Europe/Paris
    ports:
      - "7878:7878"
    volumes:
      - radarr-config:/config
      - radarr-movies:/movies
      - radarr-downloads:/downloads
    restart: unless-stopped

  lidarr:
    image: linuxserver/lidarr:latest
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Europe/Paris
    ports:
      - "8686:8686"
    volumes:
      - lidarr-config:/config
      - lidarr-music:/music
      - lidarr-downloads:/downloads
    restart: unless-stopped

  readarr:
    image: lscr.io/linuxserver/readarr:develop
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Europe/Paris
    ports:
      - "8787:8787"
    volumes:
      - readarr-config:/config
      - readarr-books:/books
      - readarr-downloads:/downloads
    restart: unless-stopped

volumes:
  app-data:
  ntfy-data:
  ntfy-etc:
  sonarr-config:
  sonarr-tv:
  sonarr-downloads:
  radarr-config:
  radarr-movies:
  radarr-downloads:
  lidarr-config:
  lidarr-music:
  lidarr-downloads:
  readarr-config:
  readarr-books:
  readarr-downloads:
```

- [ ] **Step 3 : Valider la config Docker**

```bash
docker compose config --quiet && echo "YAML valid"
```

Expected: `YAML valid`

- [ ] **Step 4 : Lancer la suite complète**

```bash
.venv/bin/pytest tests/ -v
```

Expected: 54 passed.

- [ ] **Step 5 : Commit**

```bash
git add app/main.py docker-compose.yml
git commit -m "feat: wire UI router, init cache DB on startup, add app-data volume"
```
