# Phase 2 — Webhooks Radarr / Lidarr / Readarr Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Étendre le système de webhooks à Radarr, Lidarr et Readarr en extrayant la logique commune dans `app/webhooks/base.py` et en refactorant `sonarr.py` pour l'utiliser.

**Architecture:** Un handler partagé `handle_webhook()` gère la validation du secret, le dispatch par `eventType`, et l'appel ntfy. Chaque *arr garde son propre module avec ses modèles Pydantic et sa fonction de formatage. Les endpoints FastAPI restent concrets (pas de générique) pour que FastAPI puisse introspector les types.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, httpx, pydantic-settings, pytest + pytest-asyncio + respx.

**Spec:** `docs/superpowers/specs/2026-08-15-phase2-webhooks-arr-design.md`

---

## Fichiers créés / modifiés

| Fichier | Action | Rôle |
|---|---|---|
| `app/config.py` | Modifier | + `radarr_secret`, `lidarr_secret`, `readarr_secret` |
| `app/main.py` | Modifier | Montage des 3 nouveaux routers |
| `app/webhooks/base.py` | Créer | `ArrEvent` + `handle_webhook()` |
| `app/webhooks/sonarr.py` | Modifier | `SonarrEvent` hérite `ArrEvent`, appelle `handle_webhook` |
| `app/webhooks/radarr.py` | Créer | Modèles + `_format()` + router |
| `app/webhooks/lidarr.py` | Créer | Modèles + `_format()` + router |
| `app/webhooks/readarr.py` | Créer | Modèles + `_format()` + router |
| `tests/conftest.py` | Modifier | + 3 vars d'env de test |
| `tests/webhooks/test_base.py` | Créer | Tests logique commune |
| `tests/webhooks/test_radarr.py` | Créer | Tests Radarr |
| `tests/webhooks/test_lidarr.py` | Créer | Tests Lidarr |
| `tests/webhooks/test_readarr.py` | Créer | Tests Readarr |
| `.env.example` | Modifier | + 3 nouvelles variables |
| `docker-compose.yml` | Modifier | + services radarr, lidarr, readarr |

---

## Task 1: Config + conftest + .env.example

**Files:**
- Modify: `app/config.py`
- Modify: `tests/conftest.py`
- Modify: `.env.example`

`config.py` doit être mis à jour AVANT les tâches suivantes — `Settings()` s'instancie au chargement du module et lèvera une `ValidationError` si les 3 nouvelles variables sont absentes de l'environnement de test.

- [ ] **Step 1: Mettre à jour app/config.py**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ntfy_url: str
    ntfy_topic: str
    sonarr_secret: str
    radarr_secret: str
    lidarr_secret: str
    readarr_secret: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
```

- [ ] **Step 2: Mettre à jour tests/conftest.py**

```python
import os

os.environ["NTFY_URL"] = "http://ntfy-test:80"
os.environ["NTFY_TOPIC"] = "test"
os.environ["SONARR_SECRET"] = "test-secret"
os.environ["RADARR_SECRET"] = "test-secret"
os.environ["LIDARR_SECRET"] = "test-secret"
os.environ["READARR_SECRET"] = "test-secret"

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

- [ ] **Step 3: Mettre à jour .env.example**

```env
NTFY_URL=http://ntfy:80
NTFY_TOPIC=mediacenter
SONARR_SECRET=changeme
RADARR_SECRET=changeme
LIDARR_SECRET=changeme
READARR_SECRET=changeme
```

- [ ] **Step 4: Vérifier que la suite existante passe toujours**

```bash
.venv/bin/pytest tests/ -v --no-cov
```

Expected: 11 passed (les tests Sonarr + ntfy ne changent pas).

- [ ] **Step 5: Commit**

```bash
git add app/config.py tests/conftest.py .env.example
git commit -m "chore: add Radarr/Lidarr/Readarr secrets to config"
```

---

## Task 2: Handler partagé base.py (TDD)

**Files:**
- Create: `tests/webhooks/test_base.py`
- Create: `app/webhooks/base.py`

`handle_webhook` est testé directement (sans passer par un endpoint HTTP) — on vérifie que `HTTPException` est levée, que `eventType == "Test"` court-circuite ntfy, et que `eventType == "Download"` appelle ntfy avec le retour de `on_download`.

- [ ] **Step 1: Écrire tests/webhooks/test_base.py**

```python
import httpx
import pytest
import respx
from fastapi import HTTPException

from app.webhooks.base import ArrEvent, handle_webhook


class _MinimalEvent(ArrEvent):
    pass


async def test_wrong_secret_raises_403() -> None:
    with pytest.raises(HTTPException) as exc:
        await handle_webhook(
            _MinimalEvent(eventType="Test"),
            received_secret="wrong",
            expected_secret="right",
            on_download=lambda e: ("t", "b"),
        )
    assert exc.value.status_code == 403


async def test_missing_secret_raises_403() -> None:
    with pytest.raises(HTTPException) as exc:
        await handle_webhook(
            _MinimalEvent(eventType="Test"),
            received_secret=None,
            expected_secret="right",
            on_download=lambda e: ("t", "b"),
        )
    assert exc.value.status_code == 403


async def test_test_event_returns_ok_without_calling_ntfy() -> None:
    with respx.mock:
        ntfy_route = respx.post("http://ntfy-test:80/test").mock(
            return_value=httpx.Response(200)
        )
        result = await handle_webhook(
            _MinimalEvent(eventType="Test"),
            received_secret="right",
            expected_secret="right",
            on_download=lambda e: ("t", "b"),
        )
    assert result == {"status": "ok"}
    assert not ntfy_route.called


async def test_download_calls_ntfy_with_formatted_content() -> None:
    with respx.mock:
        ntfy_route = respx.post("http://ntfy-test:80/test").mock(
            return_value=httpx.Response(200)
        )
        result = await handle_webhook(
            _MinimalEvent(eventType="Download"),
            received_secret="right",
            expected_secret="right",
            on_download=lambda e: ("Test Title", "Test Body"),
        )
    assert result == {"status": "ok"}
    assert ntfy_route.called
    assert ntfy_route.calls[0].request.headers["Title"] == "Test Title"
    assert ntfy_route.calls[0].request.content.decode() == "Test Body"


async def test_ntfy_failure_still_returns_ok() -> None:
    with respx.mock:
        respx.post("http://ntfy-test:80/test").mock(
            side_effect=httpx.TimeoutException("timeout")
        )
        result = await handle_webhook(
            _MinimalEvent(eventType="Download"),
            received_secret="right",
            expected_secret="right",
            on_download=lambda e: ("t", "b"),
        )
    assert result == {"status": "ok"}
```

- [ ] **Step 2: Lancer les tests — vérifier qu'ils échouent**

```bash
.venv/bin/pytest tests/webhooks/test_base.py -v --no-cov
```

Expected: `ModuleNotFoundError: No module named 'app.webhooks.base'`

- [ ] **Step 3: Créer app/webhooks/base.py**

```python
from collections.abc import Callable
from typing import Literal, TypeVar

from fastapi import HTTPException, status
from pydantic import BaseModel

from app.notifications import ntfy


class ArrEvent(BaseModel):
    eventType: Literal["Download", "Test"]


T = TypeVar("T", bound=ArrEvent)


async def handle_webhook(
    event: T,
    received_secret: str | None,
    expected_secret: str,
    on_download: Callable[[T], tuple[str, str]],
) -> dict[str, str]:
    if received_secret != expected_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    if event.eventType == "Test":
        return {"status": "ok"}

    title, body = on_download(event)
    await ntfy.send(title, body)
    return {"status": "ok"}
```

- [ ] **Step 4: Lancer les tests — vérifier qu'ils passent**

```bash
.venv/bin/pytest tests/webhooks/test_base.py -v --no-cov
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add app/webhooks/base.py tests/webhooks/test_base.py
git commit -m "feat: shared webhook handler in base.py"
```

---

## Task 3: Refactor sonarr.py

**Files:**
- Modify: `app/webhooks/sonarr.py`
- Test: `tests/webhooks/test_sonarr.py` (non modifié — doit rester vert)

`SonarrEvent` hérite de `ArrEvent` au lieu de `BaseModel`. La logique inline (secret check + dispatch) est remplacée par un appel à `handle_webhook`. Le comportement observable ne change pas.

- [ ] **Step 1: Réécrire app/webhooks/sonarr.py**

```python
from fastapi import APIRouter, Header
from pydantic import BaseModel

from app.config import settings
from app.webhooks.base import ArrEvent, handle_webhook

router = APIRouter()


class SonarrSeries(BaseModel):
    title: str


class SonarrEpisode(BaseModel):
    title: str
    seasonNumber: int
    episodeNumber: int


class SonarrEpisodeFile(BaseModel):
    quality: str


class SonarrEvent(ArrEvent):
    series: SonarrSeries | None = None
    episodes: list[SonarrEpisode] | None = None
    episodeFile: SonarrEpisodeFile | None = None


def _format(event: SonarrEvent) -> tuple[str, str]:
    series_title = event.series.title if event.series else "Unknown"
    ep = event.episodes[0] if event.episodes else None
    ep_title = ep.title if ep else "Unknown"
    season = ep.seasonNumber if ep else 0
    ep_num = ep.episodeNumber if ep else 0
    quality = event.episodeFile.quality if event.episodeFile else "Unknown"
    return f"{series_title} S{season:02d}E{ep_num:02d}", f"{ep_title} · {quality}"


@router.post("/webhook/sonarr")
async def sonarr_webhook(
    event: SonarrEvent,
    x_sonarr_secret: str | None = Header(default=None),
) -> dict[str, str]:
    return await handle_webhook(event, x_sonarr_secret, settings.sonarr_secret, _format)
```

- [ ] **Step 2: Vérifier que les tests Sonarr existants passent**

```bash
.venv/bin/pytest tests/webhooks/test_sonarr.py -v --no-cov
```

Expected: 8 passed. Si un test échoue, le refactor a cassé quelque chose — ne pas continuer.

- [ ] **Step 3: Lancer la suite complète**

```bash
.venv/bin/pytest -v --no-cov
```

Expected: 16 passed (11 existants + 5 base).

- [ ] **Step 4: Commit**

```bash
git add app/webhooks/sonarr.py
git commit -m "refactor: sonarr webhook uses shared handle_webhook"
```

---

## Task 4: Radarr webhook (TDD)

**Files:**
- Create: `tests/webhooks/test_radarr.py`
- Create: `app/webhooks/radarr.py`
- Modify: `app/main.py`

- [ ] **Step 1: Écrire tests/webhooks/test_radarr.py**

```python
import httpx
import respx
from httpx import AsyncClient

VALID_SECRET = "test-secret"

DOWNLOAD_PAYLOAD = {
    "eventType": "Download",
    "movie": {"title": "The Dark Knight", "year": 2008},
    "movieFile": {"quality": "Bluray-1080p"},
}


async def test_download_returns_200(client: AsyncClient) -> None:
    with respx.mock:
        respx.post("http://ntfy-test:80/test").mock(return_value=httpx.Response(200))
        response = await client.post(
            "/webhook/radarr",
            json=DOWNLOAD_PAYLOAD,
            headers={"X-Radarr-Secret": VALID_SECRET},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_download_sends_correct_notification(client: AsyncClient) -> None:
    with respx.mock:
        ntfy_route = respx.post("http://ntfy-test:80/test").mock(
            return_value=httpx.Response(200)
        )
        await client.post(
            "/webhook/radarr",
            json=DOWNLOAD_PAYLOAD,
            headers={"X-Radarr-Secret": VALID_SECRET},
        )
    assert ntfy_route.called
    req = ntfy_route.calls[0].request
    assert req.headers["Title"] == "The Dark Knight (2008)"
    assert req.content.decode() == "Bluray-1080p"


async def test_test_event_returns_ok(client: AsyncClient) -> None:
    response = await client.post(
        "/webhook/radarr",
        json={"eventType": "Test"},
        headers={"X-Radarr-Secret": VALID_SECRET},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_malformed_payload_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/webhook/radarr",
        json={"eventType": "UnknownEvent"},
        headers={"X-Radarr-Secret": VALID_SECRET},
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Lancer les tests — vérifier qu'ils échouent**

```bash
.venv/bin/pytest tests/webhooks/test_radarr.py -v --no-cov
```

Expected: 4 FAILED avec 404 (router vide) ou `ModuleNotFoundError`.

- [ ] **Step 3: Créer app/webhooks/radarr.py**

```python
from fastapi import APIRouter, Header
from pydantic import BaseModel

from app.config import settings
from app.webhooks.base import ArrEvent, handle_webhook

router = APIRouter()


class RadarrMovie(BaseModel):
    title: str
    year: int


class RadarrMovieFile(BaseModel):
    quality: str


class RadarrEvent(ArrEvent):
    movie: RadarrMovie | None = None
    movieFile: RadarrMovieFile | None = None


def _format(event: RadarrEvent) -> tuple[str, str]:
    title = f"{event.movie.title} ({event.movie.year})" if event.movie else "Unknown"
    quality = event.movieFile.quality if event.movieFile else "Unknown"
    return title, quality


@router.post("/webhook/radarr")
async def radarr_webhook(
    event: RadarrEvent,
    x_radarr_secret: str | None = Header(default=None),
) -> dict[str, str]:
    return await handle_webhook(event, x_radarr_secret, settings.radarr_secret, _format)
```

- [ ] **Step 4: Mettre à jour app/main.py**

```python
from fastapi import FastAPI

from app.webhooks import lidarr, radarr, readarr, sonarr

app = FastAPI()
app.include_router(sonarr.router)
app.include_router(radarr.router)
app.include_router(lidarr.router)
app.include_router(readarr.router)
```

Note : `lidarr` et `readarr` ne sont pas encore créés — leurs modules seront créés dans les tâches suivantes. Pour éviter une `ImportError` au Step 5, créer des stubs vides maintenant :

```python
# app/webhooks/lidarr.py  (stub)
from fastapi import APIRouter

router = APIRouter()
```

```python
# app/webhooks/readarr.py  (stub)
from fastapi import APIRouter

router = APIRouter()
```

- [ ] **Step 5: Lancer les tests Radarr — vérifier qu'ils passent**

```bash
.venv/bin/pytest tests/webhooks/test_radarr.py -v --no-cov
```

Expected: 4 passed.

- [ ] **Step 6: Vérifier la non-régression**

```bash
.venv/bin/pytest -v --no-cov
```

Expected: 20 passed.

- [ ] **Step 7: Commit**

```bash
git add app/webhooks/radarr.py app/webhooks/lidarr.py app/webhooks/readarr.py app/main.py tests/webhooks/test_radarr.py
git commit -m "feat: radarr webhook endpoint"
```

---

## Task 5: Lidarr webhook (TDD)

**Files:**
- Create: `tests/webhooks/test_lidarr.py`
- Modify: `app/webhooks/lidarr.py` (remplace le stub)

- [ ] **Step 1: Écrire tests/webhooks/test_lidarr.py**

```python
import httpx
import respx
from httpx import AsyncClient

VALID_SECRET = "test-secret"

DOWNLOAD_PAYLOAD = {
    "eventType": "Download",
    "artist": {"name": "Radiohead"},
    "albums": [{"title": "OK Computer"}],
    "trackFiles": [{"quality": "FLAC"}],
}


async def test_download_returns_200(client: AsyncClient) -> None:
    with respx.mock:
        respx.post("http://ntfy-test:80/test").mock(return_value=httpx.Response(200))
        response = await client.post(
            "/webhook/lidarr",
            json=DOWNLOAD_PAYLOAD,
            headers={"X-Lidarr-Secret": VALID_SECRET},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_download_sends_correct_notification(client: AsyncClient) -> None:
    with respx.mock:
        ntfy_route = respx.post("http://ntfy-test:80/test").mock(
            return_value=httpx.Response(200)
        )
        await client.post(
            "/webhook/lidarr",
            json=DOWNLOAD_PAYLOAD,
            headers={"X-Lidarr-Secret": VALID_SECRET},
        )
    assert ntfy_route.called
    req = ntfy_route.calls[0].request
    assert req.headers["Title"] == "Radiohead — OK Computer"
    assert req.content.decode() == "FLAC"


async def test_uses_first_album_when_multiple(client: AsyncClient) -> None:
    with respx.mock:
        ntfy_route = respx.post("http://ntfy-test:80/test").mock(
            return_value=httpx.Response(200)
        )
        await client.post(
            "/webhook/lidarr",
            json={
                "eventType": "Download",
                "artist": {"name": "Radiohead"},
                "albums": [{"title": "OK Computer"}, {"title": "Kid A"}],
                "trackFiles": [{"quality": "FLAC"}],
            },
            headers={"X-Lidarr-Secret": VALID_SECRET},
        )
    assert ntfy_route.calls[0].request.headers["Title"] == "Radiohead — OK Computer"


async def test_test_event_returns_ok(client: AsyncClient) -> None:
    response = await client.post(
        "/webhook/lidarr",
        json={"eventType": "Test"},
        headers={"X-Lidarr-Secret": VALID_SECRET},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_malformed_payload_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/webhook/lidarr",
        json={"eventType": "UnknownEvent"},
        headers={"X-Lidarr-Secret": VALID_SECRET},
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Lancer les tests — vérifier qu'ils échouent**

```bash
.venv/bin/pytest tests/webhooks/test_lidarr.py -v --no-cov
```

Expected: 5 FAILED avec 404 (stub vide).

- [ ] **Step 3: Implémenter app/webhooks/lidarr.py**

```python
from fastapi import APIRouter, Header
from pydantic import BaseModel

from app.config import settings
from app.webhooks.base import ArrEvent, handle_webhook

router = APIRouter()


class LidarrArtist(BaseModel):
    name: str


class LidarrAlbum(BaseModel):
    title: str


class LidarrTrackFile(BaseModel):
    quality: str


class LidarrEvent(ArrEvent):
    artist: LidarrArtist | None = None
    albums: list[LidarrAlbum] | None = None
    trackFiles: list[LidarrTrackFile] | None = None


def _format(event: LidarrEvent) -> tuple[str, str]:
    artist = event.artist.name if event.artist else "Unknown"
    album = event.albums[0].title if event.albums else "Unknown"
    quality = event.trackFiles[0].quality if event.trackFiles else "Unknown"
    return f"{artist} — {album}", quality


@router.post("/webhook/lidarr")
async def lidarr_webhook(
    event: LidarrEvent,
    x_lidarr_secret: str | None = Header(default=None),
) -> dict[str, str]:
    return await handle_webhook(event, x_lidarr_secret, settings.lidarr_secret, _format)
```

- [ ] **Step 4: Lancer les tests Lidarr — vérifier qu'ils passent**

```bash
.venv/bin/pytest tests/webhooks/test_lidarr.py -v --no-cov
```

Expected: 5 passed.

- [ ] **Step 5: Vérifier la non-régression**

```bash
.venv/bin/pytest -v --no-cov
```

Expected: 25 passed.

- [ ] **Step 6: Commit**

```bash
git add app/webhooks/lidarr.py tests/webhooks/test_lidarr.py
git commit -m "feat: lidarr webhook endpoint"
```

---

## Task 6: Readarr webhook (TDD)

**Files:**
- Create: `tests/webhooks/test_readarr.py`
- Modify: `app/webhooks/readarr.py` (remplace le stub)

- [ ] **Step 1: Écrire tests/webhooks/test_readarr.py**

```python
import httpx
import respx
from httpx import AsyncClient

VALID_SECRET = "test-secret"

DOWNLOAD_PAYLOAD = {
    "eventType": "Download",
    "author": {"name": "Frank Herbert"},
    "books": [{"title": "Dune"}],
    "bookFiles": [{"quality": "EPUB"}],
}


async def test_download_returns_200(client: AsyncClient) -> None:
    with respx.mock:
        respx.post("http://ntfy-test:80/test").mock(return_value=httpx.Response(200))
        response = await client.post(
            "/webhook/readarr",
            json=DOWNLOAD_PAYLOAD,
            headers={"X-Readarr-Secret": VALID_SECRET},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_download_sends_correct_notification(client: AsyncClient) -> None:
    with respx.mock:
        ntfy_route = respx.post("http://ntfy-test:80/test").mock(
            return_value=httpx.Response(200)
        )
        await client.post(
            "/webhook/readarr",
            json=DOWNLOAD_PAYLOAD,
            headers={"X-Readarr-Secret": VALID_SECRET},
        )
    assert ntfy_route.called
    req = ntfy_route.calls[0].request
    assert req.headers["Title"] == "Dune — Frank Herbert"
    assert req.content.decode() == "EPUB"


async def test_test_event_returns_ok(client: AsyncClient) -> None:
    response = await client.post(
        "/webhook/readarr",
        json={"eventType": "Test"},
        headers={"X-Readarr-Secret": VALID_SECRET},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_malformed_payload_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/webhook/readarr",
        json={"eventType": "UnknownEvent"},
        headers={"X-Readarr-Secret": VALID_SECRET},
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Lancer les tests — vérifier qu'ils échouent**

```bash
.venv/bin/pytest tests/webhooks/test_readarr.py -v --no-cov
```

Expected: 4 FAILED avec 404 (stub vide).

- [ ] **Step 3: Implémenter app/webhooks/readarr.py**

```python
from fastapi import APIRouter, Header
from pydantic import BaseModel

from app.config import settings
from app.webhooks.base import ArrEvent, handle_webhook

router = APIRouter()


class ReadarrAuthor(BaseModel):
    name: str


class ReadarrBook(BaseModel):
    title: str


class ReadarrBookFile(BaseModel):
    quality: str


class ReadarrEvent(ArrEvent):
    author: ReadarrAuthor | None = None
    books: list[ReadarrBook] | None = None
    bookFiles: list[ReadarrBookFile] | None = None


def _format(event: ReadarrEvent) -> tuple[str, str]:
    book = event.books[0].title if event.books else "Unknown"
    author = event.author.name if event.author else "Unknown"
    quality = event.bookFiles[0].quality if event.bookFiles else "Unknown"
    return f"{book} — {author}", quality


@router.post("/webhook/readarr")
async def readarr_webhook(
    event: ReadarrEvent,
    x_readarr_secret: str | None = Header(default=None),
) -> dict[str, str]:
    return await handle_webhook(
        event, x_readarr_secret, settings.readarr_secret, _format
    )
```

- [ ] **Step 4: Lancer les tests Readarr — vérifier qu'ils passent**

```bash
.venv/bin/pytest tests/webhooks/test_readarr.py -v --no-cov
```

Expected: 4 passed.

- [ ] **Step 5: Suite complète + couverture**

```bash
.venv/bin/pytest -v
```

Expected: 29 passed, couverture ≥ 95 % sur `app/`.

- [ ] **Step 6: Lint**

```bash
.venv/bin/ruff check app/ tests/
```

Expected: no issues.

- [ ] **Step 7: Commit**

```bash
git add app/webhooks/readarr.py tests/webhooks/test_readarr.py
git commit -m "feat: readarr webhook endpoint"
```

---

## Task 7: Docker Compose

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Ajouter les services dans docker-compose.yml**

Ajouter après le service `sonarr` existant, avant la section `volumes:` :

```yaml
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
    image: linuxserver/readarr:develop
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
```

Ajouter dans la section `volumes:` :

```yaml
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

Note : Readarr utilise le tag `develop` — pas de release stable disponible.

- [ ] **Step 2: Démarrer les nouveaux services**

```bash
docker compose up -d radarr lidarr readarr
```

Expected: 3 containers démarrés.

- [ ] **Step 3: Vérifier que les services répondent**

```bash
sleep 10
curl -s http://localhost:7878 -o /dev/null -w "Radarr: %{http_code}\n"
curl -s http://localhost:8686 -o /dev/null -w "Lidarr: %{http_code}\n"
curl -s http://localhost:8787 -o /dev/null -w "Readarr: %{http_code}\n"
```

Expected: `Radarr: 200`, `Lidarr: 200`, `Readarr: 200`

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml
git commit -m "chore: add Radarr/Lidarr/Readarr services to docker-compose"
```

---

## Critère de sortie (Phase 2)

29 tests passent. Un téléchargement dans chacun des trois *arr déclenche une notification push formatée via ntfy.
