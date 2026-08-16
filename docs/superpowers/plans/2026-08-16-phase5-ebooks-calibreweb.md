# Phase 5a — Ebooks Pipeline + Calibre-web Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire ebook scan/enrich into the Readarr webhook and stand up Calibre-web + Caddy so a Kobo device can sync via `/kobo/*`/`/opds/*` without exposing Calibre-web's own UI.

**Architecture:** New `app/ebooks/` module shells out to `calibredb add` + `fetch-ebook-metadata`. `handle_webhook` in `app/webhooks/base.py` gains an optional post-auth async hook; `app/webhooks/readarr.py` wires that hook to the ebooks module using the book file path from the Readarr payload. Docker Compose gains `calibre-web` and `caddy` services and a shared `books-library` volume; a new `Caddyfile` blocks `/web` and routes `/kobo/*` + `/opds/*` to calibre-web, everything else to `app`.

**Tech Stack:** Python 3.13, FastAPI, pytest + pytest-asyncio + respx, `asyncio.create_subprocess_exec`, Docker Compose, Caddy.

**Spec:** `docs/superpowers/specs/2026-08-16-phase5-ebooks-calibreweb-design.md`

## Global Constraints

- Calibre-web's own web UI (`/web`) must never be reachable — enforced in the Caddyfile, not left to calibre-web's own auth (spec: Gestion des erreurs)
- `scan_and_enrich` failures are logged and swallowed, never raised — a broken book must not break the webhook's 200/ntfy response (spec: Gestion des erreurs)
- No retry logic for failed scans — next Readarr Download event or manual re-run is the recovery path (spec: Gestion des erreurs)
- No pytest coverage for Caddyfile/docker-compose — infra config verified manually / documented in deployment guide (spec: Tests)

---

### Task 1: `app/ebooks` module — scan_and_enrich

**Files:**
- Create: `app/ebooks/__init__.py`
- Create: `app/ebooks/ebooks.py`
- Modify: `app/config.py` — add `calibre_library_path: str` setting
- Modify: `tests/conftest.py` — add `os.environ["CALIBRE_LIBRARY_PATH"] = "/test/library"`
- Create: `tests/ebooks/__init__.py`
- Create: `tests/ebooks/test_ebooks.py`

**Interfaces:**
- Produces: `async def scan_and_enrich(path: str) -> None` in `app/ebooks/ebooks.py` — runs `calibredb add --library-path <settings.calibre_library_path> <path>` then `fetch-ebook-metadata <path>`, both via `asyncio.create_subprocess_exec`; logs and returns (no raise) on any non-zero exit or `OSError`.

- [ ] **Step 1: Add `calibre_library_path` setting**

In `app/config.py`, add to `Settings`:

```python
    calibre_library_path: str = "data/calibre-library"
```

- [ ] **Step 2: Set test env var**

In `tests/conftest.py`, add near the other `os.environ` lines:

```python
os.environ["CALIBRE_LIBRARY_PATH"] = "/test/library"
```

- [ ] **Step 3: Write the failing tests**

Create `tests/ebooks/__init__.py` (empty file).

Create `tests/ebooks/test_ebooks.py`:

```python
from unittest.mock import AsyncMock, patch

from app.ebooks.ebooks import scan_and_enrich


def _mock_process(returncode: int = 0):
    process = AsyncMock()
    process.communicate = AsyncMock(return_value=(b"", b""))
    process.returncode = returncode
    return process


async def test_success_runs_calibredb_then_fetch_metadata():
    calls = []

    async def _fake_exec(*args, **kwargs):
        calls.append(args)
        return _mock_process(0)

    with patch("asyncio.create_subprocess_exec", side_effect=_fake_exec):
        await scan_and_enrich("/test/library/incoming/Dune.epub")

    assert len(calls) == 2
    assert calls[0][0] == "calibredb"
    assert "add" in calls[0]
    assert "--library-path" in calls[0]
    assert "/test/library" in calls[0]
    assert "/test/library/incoming/Dune.epub" in calls[0]
    assert calls[1][0] == "fetch-ebook-metadata"
    assert "/test/library/incoming/Dune.epub" in calls[1]


async def test_calibredb_failure_is_logged_not_raised(caplog):
    async def _fake_exec(*args, **kwargs):
        return _mock_process(1)

    with patch("asyncio.create_subprocess_exec", side_effect=_fake_exec):
        await scan_and_enrich("/test/library/incoming/Dune.epub")

    assert "calibredb" in caplog.text.lower()


async def test_fetch_metadata_failure_is_logged_not_raised(caplog):
    call_count = 0

    async def _fake_exec(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return _mock_process(0 if call_count == 1 else 1)

    with patch("asyncio.create_subprocess_exec", side_effect=_fake_exec):
        await scan_and_enrich("/test/library/incoming/Dune.epub")

    assert "fetch-ebook-metadata" in caplog.text.lower()


async def test_subprocess_oserror_is_logged_not_raised(caplog):
    async def _fake_exec(*args, **kwargs):
        raise OSError("calibredb not found")

    with patch("asyncio.create_subprocess_exec", side_effect=_fake_exec):
        await scan_and_enrich("/test/library/incoming/Dune.epub")

    assert "calibredb not found" in caplog.text
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/ebooks/test_ebooks.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.ebooks'`

- [ ] **Step 5: Implement `app/ebooks/ebooks.py`**

Create `app/ebooks/__init__.py` (empty file).

Create `app/ebooks/ebooks.py`:

```python
import asyncio
import logging

from app.config import settings

logger = logging.getLogger(__name__)


async def _run(*args: str) -> bool:
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
    except OSError as exc:
        logger.error("ebook subprocess failed to start", extra={"cmd": args[0], "error": str(exc)})
        return False
    if process.returncode != 0:
        logger.error(
            "ebook subprocess exited non-zero",
            extra={"cmd": args[0], "returncode": process.returncode, "stderr": stderr.decode(errors="replace")},
        )
        return False
    return True


async def scan_and_enrich(path: str) -> None:
    if not await _run("calibredb", "add", "--library-path", settings.calibre_library_path, path):
        return
    await _run("fetch-ebook-metadata", path)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/ebooks/test_ebooks.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Commit**

```bash
git add app/ebooks app/config.py tests/ebooks tests/conftest.py
git commit -m "feat: add ebooks scan_and_enrich module"
```

---

### Task 2: `handle_webhook` post-auth hook

**Files:**
- Modify: `app/webhooks/base.py`
- Modify: `tests/webhooks/test_base.py`

**Interfaces:**
- Consumes: nothing new
- Produces: `handle_webhook(event, received_secret, expected_secret, on_download, on_download_extra: Callable[[T], Awaitable[None]] | None = None)` — when `on_download_extra` is given, it's awaited (best-effort: exceptions logged, never raised) immediately after the Test/secret check passes and before `on_download`/ntfy.

- [ ] **Step 1: Write the failing tests**

In `tests/webhooks/test_base.py`, add:

```python
async def test_on_download_extra_called_on_download():
    calls = []

    async def _extra(event):
        calls.append(event)

    with respx.mock:
        respx.post("http://ntfy-test:80/test").mock(return_value=httpx.Response(200))
        await handle_webhook(
            _Event(eventType="Download"), SECRET, SECRET, _fmt, on_download_extra=_extra
        )
    assert len(calls) == 1


async def test_on_download_extra_not_called_on_test_event():
    calls = []

    async def _extra(event):
        calls.append(event)

    await handle_webhook(
        _Event(eventType="Test"), SECRET, SECRET, _fmt, on_download_extra=_extra
    )
    assert calls == []


async def test_on_download_extra_not_called_on_wrong_secret():
    calls = []

    async def _extra(event):
        calls.append(event)

    with pytest.raises(HTTPException):
        await handle_webhook(
            _Event(eventType="Download"), "wrong", SECRET, _fmt, on_download_extra=_extra
        )
    assert calls == []


async def test_on_download_extra_error_does_not_fail_webhook(monkeypatch):
    async def _extra(event):
        raise RuntimeError("boom")

    with respx.mock:
        respx.post("http://ntfy-test:80/test").mock(return_value=httpx.Response(200))
        result = await handle_webhook(
            _Event(eventType="Download"), SECRET, SECRET, _fmt, on_download_extra=_extra
        )
    assert result == {"status": "ok"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/webhooks/test_base.py -v`
Expected: FAIL with `TypeError: handle_webhook() got an unexpected keyword argument 'on_download_extra'`

- [ ] **Step 3: Implement the hook in `app/webhooks/base.py`**

Replace the `handle_webhook` function with:

```python
async def handle_webhook(
    event: T,
    received_secret: str | None,
    expected_secret: str,
    on_download: Callable[[T], tuple[str, str]],
    on_download_extra: Callable[[T], "Awaitable[None]"] | None = None,
) -> dict[str, str]:
    if received_secret != expected_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    if event.eventType == "Test":
        return {"status": "ok"}
    if on_download_extra is not None:
        try:
            await on_download_extra(event)
        except Exception as exc:  # noqa: BLE001 - best-effort side effect
            logger.error("on_download_extra failed in handle_webhook", extra={"error": str(exc)})
    title, body = on_download(event)
    try:
        await ntfy.send(title, body)
    except httpx.HTTPError as exc:
        logger.error("ntfy send failed in handle_webhook", extra={"error": str(exc)})
    return {"status": "ok"}
```

Add `Awaitable` to the imports at the top of the file:

```python
from collections.abc import Awaitable, Callable
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/webhooks/test_base.py -v`
Expected: PASS (all tests including the 4 new ones)

- [ ] **Step 5: Commit**

```bash
git add app/webhooks/base.py tests/webhooks/test_base.py
git commit -m "feat: add optional post-auth hook to handle_webhook"
```

---

### Task 3: Wire ebooks scan into the Readarr webhook

**Files:**
- Modify: `app/webhooks/readarr.py`
- Modify: `tests/webhooks/test_readarr.py`

**Interfaces:**
- Consumes: `scan_and_enrich(path: str) -> None` from Task 1, `handle_webhook(..., on_download_extra=...)` from Task 2
- Produces: nothing new for other tasks

- [ ] **Step 1: Write the failing test**

In `tests/webhooks/test_readarr.py`, update `DOWNLOAD_PAYLOAD` to include `path`:

```python
DOWNLOAD_PAYLOAD = {
    "eventType": "Download",
    "author": {"name": "Frank Herbert"},
    "books": [{"title": "Dune"}],
    "bookFiles": [{"quality": "EPUB", "path": "/test/library/incoming/Dune.epub"}],
}
```

Add a new test:

```python
async def test_download_triggers_ebook_scan(client: AsyncClient, monkeypatch) -> None:
    calls = []

    async def _fake_scan(path):
        calls.append(path)

    monkeypatch.setattr("app.webhooks.readarr.ebooks.scan_and_enrich", _fake_scan)
    with respx.mock:
        respx.post("http://ntfy-test:80/test").mock(return_value=httpx.Response(200))
        await client.post(
            "/webhook/readarr",
            json=DOWNLOAD_PAYLOAD,
            headers={"X-Readarr-Secret": VALID_SECRET},
        )
    assert calls == ["/test/library/incoming/Dune.epub"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/webhooks/test_readarr.py -v -k ebook_scan`
Expected: FAIL (`app.webhooks.readarr` has no attribute `ebooks`, or `TypeError` for missing `path`)

- [ ] **Step 3: Wire the hook in `app/webhooks/readarr.py`**

```python
from fastapi import APIRouter, Header
from pydantic import BaseModel

from app.config import settings
from app.ebooks import ebooks
from app.webhooks.base import ArrEvent, handle_webhook

router = APIRouter()


class ReadarrAuthor(BaseModel):
    name: str


class ReadarrBook(BaseModel):
    title: str


class ReadarrBookFile(BaseModel):
    quality: str
    path: str


class ReadarrEvent(ArrEvent):
    author: ReadarrAuthor | None = None
    books: list[ReadarrBook] | None = None
    bookFiles: list[ReadarrBookFile] | None = None


def _format(event: ReadarrEvent) -> tuple[str, str]:
    book = event.books[0].title if event.books else "Unknown"
    author = event.author.name if event.author else "Unknown"
    quality = event.bookFiles[0].quality if event.bookFiles else "Unknown"
    return f"{book} — {author}", quality


async def _scan(event: ReadarrEvent) -> None:
    if event.bookFiles:
        await ebooks.scan_and_enrich(event.bookFiles[0].path)


@router.post("/webhook/readarr")
async def readarr_webhook(
    event: ReadarrEvent,
    x_readarr_secret: str | None = Header(default=None),
) -> dict[str, str]:
    return await handle_webhook(
        event, x_readarr_secret, settings.readarr_secret, _format, on_download_extra=_scan
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/webhooks/test_readarr.py -v`
Expected: PASS (all tests, including updated `test_download_sends_correct_notification` which still checks the same title/body)

- [ ] **Step 5: Run full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add app/webhooks/readarr.py tests/webhooks/test_readarr.py
git commit -m "feat: trigger ebook scan on readarr download webhook"
```

---

### Task 4: Docker Compose — calibre-web, caddy, shared library volume

**Files:**
- Modify: `docker-compose.yml`
- Create: `Caddyfile`
- Modify: `.env.example`
- Modify: `.ai/05-DEPLOYMENT.md`

**Interfaces:**
- Consumes: nothing (infra-only task, no app code)
- Produces: `books-library` shared volume path `/books` (consumed by `app`, `readarr`, `calibre-web`); this is documentation-only for now — `CALIBRE_LIBRARY_PATH` in `.env`/`.env.example` should be set to the in-container path `/books` to match.

- [ ] **Step 1: Add `calibre-web` and `caddy` services to `docker-compose.yml`**

Add a `books-library` volume, mount it into `app` (read-write) and `readarr` (read-write, alongside its existing `readarr-books` volume — the shared library and Readarr's own working dir are distinct: `books-library` is the finished library `calibredb` manages, `readarr-books` is Readarr's own download/organize dir feeding into it), and into `calibre-web` (read-only). Add `caddy` in front, published on the host's public port; remove the direct host port publish from `app` since Caddy now fronts it.

```yaml
  app:
    build: .
    env_file: .env
    depends_on:
      - ntfy
    volumes:
      - app-data:/app/data
      - books-library:/books
    restart: unless-stopped

  calibre-web:
    image: lscr.io/linuxserver/calibre-web:latest
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Europe/Paris
      - DOCKER_MODS=linuxserver/mods:universal-calibre
    volumes:
      - calibre-web-config:/config
      - books-library:/books:ro
    restart: unless-stopped

  caddy:
    image: caddy:2-alpine
    ports:
      - "8000:80"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy-data:/data
    depends_on:
      - app
      - calibre-web
    restart: unless-stopped
```

Update the `volumes:` top-level block to add `books-library`, `calibre-web-config`, `caddy-data`.

Note: remove `ports: - "8000:8000"` from the `app` service (Caddy now owns port 8000 on the host and proxies to `app` internally on its default port).

- [ ] **Step 2: Write `Caddyfile`**

```
:80 {
	handle /kobo/* {
		reverse_proxy calibre-web:8083
	}
	handle /opds/* {
		reverse_proxy calibre-web:8083
	}
	handle /web/* {
		respond 404
	}
	handle {
		reverse_proxy app:8000
	}
}
```

- [ ] **Step 3: Add `CALIBRE_LIBRARY_PATH` to `.env.example`**

```
CALIBRE_LIBRARY_PATH=/books
```

- [ ] **Step 4: Update `.ai/05-DEPLOYMENT.md`**

In the "Docker Compose (squelette)" section, add `calibre-web` and `caddy` to the services list, and add a line noting the shared `books-library` volume feeding both `app`'s ebook scan and `calibre-web`'s read-only index. In the "Mise à jour"/verification area, add:

```
## Vérification pont Calibre-web
- Après `docker compose up -d`, vérifier que `/web` répond 404 via Caddy
  (`curl -I http://<host>:8000/web/` doit renvoyer 404, jamais l'UI Calibre-web)
- Vérifier `/opds/` répond (catalogue OPDS accessible)
```

- [ ] **Step 5: Verify compose config parses**

Run: `docker compose config -q`
Expected: no output, exit code 0 (validates YAML + service references without starting anything)

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml Caddyfile .env.example .ai/05-DEPLOYMENT.md
git commit -m "feat: add calibre-web and caddy services with shared library volume"
```

---

### Task 5: Mark Phase 5a done in dev plan

**Files:**
- Modify: `.ai/DEVELOPMENT_PLAN.md`

**Interfaces:**
- Consumes: nothing
- Produces: nothing

- [ ] **Step 1: Run full suite with coverage**

Run: `.venv/bin/python -m pytest -q --cov=app`
Expected: all tests PASS, coverage at or above 94%

- [ ] **Step 2: Update checkboxes**

In `.ai/DEVELOPMENT_PLAN.md`, under `## Phase 5 — Intégration lecture`, check off the two items this plan covers:

```markdown
## Phase 5 — Intégration lecture
- [ ] Intégration Jellyfin dans l'UI (lien direct ou embed du player)
- [x] Pipeline ebooks : `calibredb add` + `fetch-ebook-metadata` pour scan,
      enrichissement et organisation (indépendant de Calibre-web)
- [x] Calibre-web déployé en pont protocole seul — `/kobo/*` + `/opds/*`
      exposés via reverse proxy, `/web` bloqué (ADR 0004)
- [ ] Documentation de la configuration liseuse (changement d'URL de sync côté
      appareil — action manuelle, hors script d'installation)
```

(The Jellyfin-in-UI and reader-config-doc items stay unchecked — separate sub-project / final user docs, out of this plan's scope.)

- [ ] **Step 3: Commit**

```bash
git add .ai/DEVELOPMENT_PLAN.md
git commit -m "docs: mark Phase 5a (ebooks pipeline + calibre-web bridge) done in dev plan"
```
