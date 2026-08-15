# Phase 1 — Webhook Sonarr → ntfy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Endpoint FastAPI `/webhook/sonarr` reçoit les events Sonarr `Download` et `Test`, envoie une notification push via ntfy auto-hébergé.

**Architecture:** Router FastAPI `app/webhooks/sonarr.py` valide le secret, parse le payload Pydantic, délègue l'envoi à `app/notifications/ntfy.py` (client httpx async). Config centralisée dans `app/config.py` via pydantic-settings.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, httpx, pydantic-settings, pytest + pytest-asyncio + respx, ruff, Docker Compose, ntfy (binwiederhier/ntfy).

**Spec:** `docs/superpowers/specs/2026-08-15-phase1-webhook-sonarr-design.md`

---

## Fichiers créés / modifiés

| Fichier | Rôle |
|---|---|
| `pyproject.toml` | Dépendances, config pytest/ruff/mypy |
| `.env.example` | Template secrets |
| `app/__init__.py` | Package marker |
| `app/main.py` | App FastAPI + montage router |
| `app/config.py` | Settings pydantic-settings |
| `app/webhooks/__init__.py` | Package marker |
| `app/webhooks/sonarr.py` | Router + modèles Pydantic + parsing |
| `app/notifications/__init__.py` | Package marker |
| `app/notifications/ntfy.py` | Client httpx async ntfy |
| `tests/__init__.py` | Package marker |
| `tests/conftest.py` | Fixtures pytest (env vars, client httpx) |
| `tests/webhooks/__init__.py` | Package marker |
| `tests/webhooks/test_sonarr.py` | Tests endpoint sonarr |
| `tests/notifications/__init__.py` | Package marker |
| `tests/notifications/test_ntfy.py` | Tests client ntfy |
| `Dockerfile` | Image Alpine multi-stage |
| `docker-compose.yml` | Services app + ntfy |

---

## Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `app/__init__.py`, `app/webhooks/__init__.py`, `app/notifications/__init__.py`
- Create: `tests/__init__.py`, `tests/webhooks/__init__.py`, `tests/notifications/__init__.py`

- [ ] **Step 1: Créer pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "ultimatemediacenter"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "httpx>=0.27.0",
    "pydantic-settings>=2.4.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "respx>=0.21.0",
    "pytest-cov>=5.0.0",
    "ruff>=0.6.0",
    "mypy>=1.11.0",
]

[tool.setuptools.packages.find]
where = ["."]
include = ["app*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "--cov=app --cov-report=term-missing"

[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I"]

[tool.mypy]
python_version = "3.11"
strict = true
```

- [ ] **Step 2: Créer .env.example**

```env
NTFY_URL=http://ntfy:80
NTFY_TOPIC=mediacenter
SONARR_SECRET=changeme
```

- [ ] **Step 3: Créer les répertoires et __init__.py vides**

```bash
mkdir -p app/webhooks app/notifications tests/webhooks tests/notifications
touch app/__init__.py app/webhooks/__init__.py app/notifications/__init__.py
touch tests/__init__.py tests/webhooks/__init__.py tests/notifications/__init__.py
```

- [ ] **Step 4: Installer les dépendances**

```bash
pip install -e ".[dev]"
```

Expected: installation sans erreur.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .env.example app/ tests/
git commit -m "chore: project scaffold — pyproject.toml, package structure"
```

---

## Task 2: Config module

**Files:**
- Create: `app/config.py`

- [ ] **Step 1: Créer app/config.py**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ntfy_url: str
    ntfy_topic: str
    sonarr_secret: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
```

- [ ] **Step 2: Créer tests/conftest.py**

Ce fichier doit définir les variables d'environnement AVANT tout import de `app.*`, car `settings = Settings()` est instancié au chargement du module.

```python
import os

os.environ["NTFY_URL"] = "http://ntfy-test:80"
os.environ["NTFY_TOPIC"] = "test"
os.environ["SONARR_SECRET"] = "test-secret"

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
async def client() -> AsyncClient:
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```

L'import de `app.main` est dans la fixture (pas au niveau module) pour garantir que les env vars sont déjà présents quand `Settings()` s'instancie.

- [ ] **Step 3: Vérifier que les settings chargent sans erreur**

```bash
NTFY_URL=http://ntfy:80 NTFY_TOPIC=mc SONARR_SECRET=x python -c "from app.config import settings; print(settings)"
```

Expected: `Settings(ntfy_url='http://ntfy:80', ntfy_topic='mc', sonarr_secret='x')`

- [ ] **Step 4: Commit**

```bash
git add app/config.py tests/conftest.py
git commit -m "feat: config module via pydantic-settings"
```

---

## Task 3: Client ntfy (TDD)

**Files:**
- Create: `tests/notifications/test_ntfy.py`
- Create: `app/notifications/ntfy.py`

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# tests/notifications/test_ntfy.py
import httpx
import respx

from app.notifications.ntfy import send


async def test_send_posts_to_ntfy_with_correct_headers() -> None:
    with respx.mock:
        route = respx.post("http://ntfy-test:80/test").mock(
            return_value=httpx.Response(200)
        )
        await send("The Boys S03E01", "Payback · HDTV-1080p")

    assert route.called
    req = route.calls[0].request
    assert req.headers["Title"] == "The Boys S03E01"
    assert req.content.decode() == "Payback · HDTV-1080p"


async def test_send_does_not_raise_on_timeout() -> None:
    with respx.mock:
        respx.post("http://ntfy-test:80/test").mock(
            side_effect=httpx.TimeoutException("timeout")
        )
        await send("title", "body")  # doit terminer sans exception


async def test_send_does_not_raise_on_http_error() -> None:
    with respx.mock:
        respx.post("http://ntfy-test:80/test").mock(
            return_value=httpx.Response(500)
        )
        await send("title", "body")  # 500 ne doit pas lever d'exception
```

- [ ] **Step 2: Lancer les tests — vérifier qu'ils échouent**

```bash
pytest tests/notifications/test_ntfy.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.notifications.ntfy'`

- [ ] **Step 3: Implémenter app/notifications/ntfy.py**

```python
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def send(title: str, body: str) -> None:
    url = f"{settings.ntfy_url}/{settings.ntfy_topic}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                content=body,
                headers={"Title": title},
                timeout=5.0,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("ntfy send failed", extra={"error": str(exc), "url": url})
```

`raise_for_status()` transforme un 500 en `httpx.HTTPStatusError` (sous-classe de `httpx.HTTPError`), qui est capturée et loguée sans se propager.

- [ ] **Step 4: Lancer les tests — vérifier qu'ils passent**

```bash
pytest tests/notifications/test_ntfy.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add app/notifications/ntfy.py tests/notifications/test_ntfy.py
git commit -m "feat: ntfy async client with error handling"
```

---

## Task 4: Webhook Sonarr (TDD)

**Files:**
- Create: `tests/webhooks/test_sonarr.py`
- Create: `app/webhooks/sonarr.py`
- Create: `app/main.py`

- [ ] **Step 1: Créer app/main.py et un stub app/webhooks/sonarr.py**

`app/main.py` importe `sonarr` dès le chargement — le stub doit exister pour que la fixture `client` puisse instancier l'app. Sans lui, tous les tests échouent en `ImportError` depuis la fixture, pas depuis l'endpoint.

```python
# app/main.py
from fastapi import FastAPI

from app.webhooks import sonarr

app = FastAPI()
app.include_router(sonarr.router)
```

```python
# app/webhooks/sonarr.py  (stub — aucune route définie)
from fastapi import APIRouter

router = APIRouter()
```

- [ ] **Step 2: Écrire tous les tests qui échouent**

```python
# tests/webhooks/test_sonarr.py
import httpx
import pytest
import respx
from httpx import AsyncClient

VALID_SECRET = "test-secret"

DOWNLOAD_PAYLOAD = {
    "eventType": "Download",
    "series": {"title": "The Boys"},
    "episodes": [
        {"title": "Payback", "seasonNumber": 3, "episodeNumber": 1}
    ],
    "episodeFile": {"quality": "HDTV-1080p"},
}


async def test_test_event_returns_ok(client: AsyncClient) -> None:
    response = await client.post(
        "/webhook/sonarr",
        json={"eventType": "Test"},
        headers={"X-Sonarr-Secret": VALID_SECRET},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_test_event_does_not_call_ntfy(client: AsyncClient) -> None:
    with respx.mock:
        ntfy_route = respx.post("http://ntfy-test:80/test").mock(
            return_value=httpx.Response(200)
        )
        await client.post(
            "/webhook/sonarr",
            json={"eventType": "Test"},
            headers={"X-Sonarr-Secret": VALID_SECRET},
        )
    assert not ntfy_route.called


async def test_missing_secret_returns_403(client: AsyncClient) -> None:
    response = await client.post("/webhook/sonarr", json=DOWNLOAD_PAYLOAD)
    assert response.status_code == 403


async def test_wrong_secret_returns_403(client: AsyncClient) -> None:
    response = await client.post(
        "/webhook/sonarr",
        json=DOWNLOAD_PAYLOAD,
        headers={"X-Sonarr-Secret": "wrong-secret"},
    )
    assert response.status_code == 403


async def test_malformed_payload_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/webhook/sonarr",
        json={"eventType": "UnknownEvent"},
        headers={"X-Sonarr-Secret": VALID_SECRET},
    )
    assert response.status_code == 422


async def test_download_returns_200(client: AsyncClient) -> None:
    with respx.mock:
        respx.post("http://ntfy-test:80/test").mock(return_value=httpx.Response(200))
        response = await client.post(
            "/webhook/sonarr",
            json=DOWNLOAD_PAYLOAD,
            headers={"X-Sonarr-Secret": VALID_SECRET},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_download_sends_notification_with_correct_content(
    client: AsyncClient,
) -> None:
    with respx.mock:
        ntfy_route = respx.post("http://ntfy-test:80/test").mock(
            return_value=httpx.Response(200)
        )
        await client.post(
            "/webhook/sonarr",
            json=DOWNLOAD_PAYLOAD,
            headers={"X-Sonarr-Secret": VALID_SECRET},
        )

    assert ntfy_route.called
    req = ntfy_route.calls[0].request
    assert req.headers["Title"] == "The Boys S03E01"
    assert req.content.decode() == "Payback · HDTV-1080p"


async def test_ntfy_failure_still_returns_200(client: AsyncClient) -> None:
    with respx.mock:
        respx.post("http://ntfy-test:80/test").mock(
            side_effect=httpx.TimeoutException("timeout")
        )
        response = await client.post(
            "/webhook/sonarr",
            json=DOWNLOAD_PAYLOAD,
            headers={"X-Sonarr-Secret": VALID_SECRET},
        )
    assert response.status_code == 200
```

- [ ] **Step 3: Lancer les tests — vérifier qu'ils échouent**

```bash
pytest tests/webhooks/test_sonarr.py -v
```

Expected: 8 FAILED — tous retournent 404 (router vide, aucune route enregistrée).

- [ ] **Step 4: Implémenter app/webhooks/sonarr.py**

```python
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from app.config import settings
from app.notifications import ntfy

router = APIRouter()


class SonarrSeries(BaseModel):
    title: str


class SonarrEpisode(BaseModel):
    title: str
    seasonNumber: int
    episodeNumber: int


class SonarrEpisodeFile(BaseModel):
    quality: str


class SonarrEvent(BaseModel):
    eventType: Literal["Download", "Test"]
    series: SonarrSeries | None = None
    episodes: list[SonarrEpisode] | None = None
    episodeFile: SonarrEpisodeFile | None = None


@router.post("/webhook/sonarr")
async def sonarr_webhook(
    event: SonarrEvent,
    x_sonarr_secret: str | None = Header(default=None),
) -> dict[str, str]:
    if x_sonarr_secret != settings.sonarr_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    if event.eventType == "Test":
        return {"status": "ok"}

    series_title = event.series.title if event.series else "Unknown"
    ep = event.episodes[0] if event.episodes else None
    ep_title = ep.title if ep else "Unknown"
    season = ep.seasonNumber if ep else 0
    ep_num = ep.episodeNumber if ep else 0
    quality = event.episodeFile.quality if event.episodeFile else "Unknown"

    title = f"{series_title} S{season:02d}E{ep_num:02d}"
    body = f"{ep_title} · {quality}"

    await ntfy.send(title, body)
    return {"status": "ok"}
```

- [ ] **Step 5: Lancer les tests — vérifier qu'ils passent tous**

```bash
pytest tests/webhooks/test_sonarr.py -v
```

Expected: 8 passed.

- [ ] **Step 6: Lancer la suite complète + couverture**

```bash
pytest --cov=app --cov-report=term-missing -v
```

Expected: tous passent, couverture ≥ 80 % sur `app/`.

- [ ] **Step 7: Lint**

```bash
ruff check app/ tests/
```

Expected: no issues.

- [ ] **Step 8: Commit**

```bash
git add app/webhooks/sonarr.py app/main.py tests/webhooks/test_sonarr.py
git commit -m "feat: sonarr webhook endpoint — Download + Test events"
```

---

## Task 5: Dockerfile

**Files:**
- Create: `Dockerfile`

- [ ] **Step 1: Créer Dockerfile**

```dockerfile
# Stage 1 — install dependencies
FROM python:3.11-alpine AS builder
WORKDIR /build
COPY pyproject.toml .
# Stub app package so pip install . can resolve the project
RUN mkdir app && touch app/__init__.py
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Stage 2 — runtime image
FROM python:3.11-alpine
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages \
                    /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY app/ app/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Construire l'image localement**

```bash
docker build -t umc-app:dev .
```

Expected: build sans erreur.

- [ ] **Step 3: Vérifier la taille**

```bash
docker image inspect umc-app:dev --format='{{.Size}}' | numfmt --to=iec
```

Expected: < 150 Mo (objectif ADR 0003).

- [ ] **Step 4: Commit**

```bash
git add Dockerfile
git commit -m "chore: Alpine multi-stage Dockerfile"
```

---

## Task 6: Docker Compose

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Créer docker-compose.yml**

```yaml
services:
  app:
    build: .
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      - ntfy
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

volumes:
  ntfy-data:
  ntfy-etc:
```

Note : ntfy exposé sur le port host `8080` pour éviter le conflit avec d'éventuels services locaux sur `80`. L'app contacte ntfy via le réseau Docker interne (`http://ntfy:80`).

- [ ] **Step 2: Créer le fichier .env depuis .env.example**

```bash
cp .env.example .env
# Remplacer SONARR_SECRET par une vraie valeur
```

⚠️ Ne jamais committer `.env`. Vérifier que `.gitignore` contient `.env`.

- [ ] **Step 3: Créer .gitignore si absent**

```bash
cat > .gitignore << 'EOF'
.env
__pycache__/
*.pyc
.mypy_cache/
.ruff_cache/
.pytest_cache/
htmlcov/
.coverage
EOF
```

- [ ] **Step 4: Démarrer la stack**

```bash
docker compose up --build -d
```

Expected: 2 services démarrés (`app`, `ntfy`).

- [ ] **Step 5: Smoke test — event Test**

```bash
curl -s -X POST http://localhost:8000/webhook/sonarr \
  -H "Content-Type: application/json" \
  -H "X-Sonarr-Secret: changeme" \
  -d '{"eventType": "Test"}' | jq .
```

Expected: `{"status": "ok"}`

- [ ] **Step 6: Smoke test — event Download**

```bash
curl -s -X POST http://localhost:8000/webhook/sonarr \
  -H "Content-Type: application/json" \
  -H "X-Sonarr-Secret: changeme" \
  -d '{
    "eventType": "Download",
    "series": {"title": "The Boys"},
    "episodes": [{"title": "Payback", "seasonNumber": 3, "episodeNumber": 1}],
    "episodeFile": {"quality": "HDTV-1080p"}
  }' | jq .
```

Expected: `{"status": "ok"}` + notification visible dans ntfy sur `http://localhost:8080`.

- [ ] **Step 7: Commit**

```bash
git add docker-compose.yml .gitignore
git commit -m "chore: docker-compose — app + ntfy services"
```

---

## Critère de sortie (Phase 1)

Une sortie d'épisode dans Sonarr configuré pour envoyer vers `http://<pi>:8000/webhook/sonarr` avec le header `X-Sonarr-Secret` déclenche une notification push sur le téléphone via ntfy.

## Hors périmètre

- Radarr / Lidarr / Readarr (Phase 2)
- Déduplication events rejoués (Phase 2)
- UI (Phase 3)
- Auth OAuth (Phase 6)
