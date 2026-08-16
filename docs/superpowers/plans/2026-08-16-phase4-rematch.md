# Phase 4 — Re-match manuel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user fix a mismatched *arr item from the UI: pick a Manual Import candidate, apply it, and have Jellyfin refresh its metadata automatically.

**Architecture:** A new `app/jellyfin/client.py` (httpx client, same shape as `app/arr/*.py`) handles Jellyfin search + refresh. A new `app/rematch/rematch.py` calls the chosen *arr's `manualimport`/`command` endpoints and, on success, chains into the Jellyfin client. Two new UI routes on the existing `app/ui/router.py` expose this as an HTMX modal reachable from a "Re-match" button on each library row.

**Tech Stack:** FastAPI, httpx (async), Jinja2/HTMX, pytest + respx (existing stack, no new dependencies).

**Spec:** `docs/superpowers/specs/2026-08-16-phase4-rematch-design.md`

## Global Constraints

- Every httpx call uses `timeout=5.0` and catches `httpx.HTTPError` → log + safe fallback (`None`/`False`), never raises to the caller
- No new cache — Jellyfin/re-match calls are on-demand actions, not polled data
- `*arr` config lookup by name reuses the existing per-arr `Settings` fields (`{arr}_url`, `{arr}_api_key`) — no new per-arr modules
- No persistent *arr↔Jellyfin ID mapping — Jellyfin item is found via live `search_items` at apply time
- Tests use `respx` to mock httpx and `monkeypatch` to set `settings` fields, matching `tests/arr/test_radarr.py`'s pattern

---

## Task 1: Config + conftest + .env.example

**Files:**
- Modify: `app/config.py`
- Modify: `tests/conftest.py`
- Modify: `.env.example`

**Interfaces:**
- Produces: `settings.jellyfin_url: str`, `settings.jellyfin_api_key: str` — consumed by Task 2 and Task 3

- [ ] **Step 1: Add the two new settings fields**

Edit `app/config.py`, add after `readarr_api_key`:

```python
    jellyfin_url: str
    jellyfin_api_key: str
```

- [ ] **Step 2: Add test env vars**

Edit `tests/conftest.py`, add after `os.environ["READARR_API_KEY"] = "test-api-key"`:

```python
os.environ["JELLYFIN_URL"] = "http://jellyfin-test:8096"
os.environ["JELLYFIN_API_KEY"] = "test-api-key"
```

- [ ] **Step 3: Add to .env.example**

Append to `.env.example`:

```env
JELLYFIN_URL=http://jellyfin:8096
JELLYFIN_API_KEY=changeme
```

- [ ] **Step 4: Verify existing test suite still passes**

Run: `pytest -q`
Expected: all existing tests PASS (config now requires the two new fields, which conftest now provides)

- [ ] **Step 5: Commit**

```bash
git add app/config.py tests/conftest.py .env.example
git commit -m "feat: add jellyfin config settings"
```

---

## Task 2: Jellyfin client

**Files:**
- Create: `app/jellyfin/__init__.py` (empty)
- Create: `app/jellyfin/client.py`
- Test: `tests/jellyfin/__init__.py` (empty)
- Test: `tests/jellyfin/test_client.py`

**Interfaces:**
- Consumes: `settings.jellyfin_url`, `settings.jellyfin_api_key` (Task 1)
- Produces: `async def search_items(query: str) -> list[dict] | None`, `async def refresh_item(item_id: str) -> bool` — consumed by Task 3

- [ ] **Step 1: Create empty package files**

```bash
mkdir -p app/jellyfin tests/jellyfin
touch app/jellyfin/__init__.py tests/jellyfin/__init__.py
```

- [ ] **Step 2: Write failing tests**

Create `tests/jellyfin/test_client.py`:

```python
import httpx
import respx

from app.jellyfin import client


@respx.mock
async def test_search_items_returns_results():
    respx.get("http://jellyfin-test:8096/Items").mock(
        return_value=httpx.Response(200, json={"Items": [{"Id": "abc123", "Name": "Inception"}]})
    )
    result = await client.search_items("Inception")
    assert result == [{"Id": "abc123", "Name": "Inception"}]


@respx.mock
async def test_search_items_returns_none_on_http_error():
    respx.get("http://jellyfin-test:8096/Items").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    result = await client.search_items("Inception")
    assert result is None


@respx.mock
async def test_refresh_item_returns_true_on_success():
    respx.post("http://jellyfin-test:8096/Items/abc123/Refresh").mock(
        return_value=httpx.Response(204)
    )
    result = await client.refresh_item("abc123")
    assert result is True


@respx.mock
async def test_refresh_item_returns_false_on_http_error():
    respx.post("http://jellyfin-test:8096/Items/abc123/Refresh").mock(
        return_value=httpx.Response(500)
    )
    result = await client.refresh_item("abc123")
    assert result is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/jellyfin/test_client.py -v`
Expected: FAIL with `ModuleNotFoundError` or `ImportError` (no `client.py` yet)

- [ ] **Step 4: Implement the client**

Create `app/jellyfin/client.py`:

```python
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def search_items(query: str) -> list[dict] | None:
    try:
        async with httpx.AsyncClient() as http:
            response = await http.get(
                f"{settings.jellyfin_url}/Items",
                params={"searchTerm": query, "api_key": settings.jellyfin_api_key},
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json().get("Items", [])
    except httpx.HTTPError as exc:
        logger.error("jellyfin search failed", extra={"error": str(exc)})
        return None
    return data


async def refresh_item(item_id: str) -> bool:
    try:
        async with httpx.AsyncClient() as http:
            response = await http.post(
                f"{settings.jellyfin_url}/Items/{item_id}/Refresh",
                params={"api_key": settings.jellyfin_api_key},
                json={"Replace All Metadata": True, "Replace All Images": False},
                timeout=5.0,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("jellyfin refresh failed", extra={"error": str(exc), "item_id": item_id})
        return False
    return True
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/jellyfin/test_client.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add app/jellyfin tests/jellyfin
git commit -m "feat: add jellyfin API client"
```

---

## Task 3: Re-match business logic

**Files:**
- Create: `app/rematch/__init__.py` (empty)
- Create: `app/rematch/rematch.py`
- Test: `tests/rematch/__init__.py` (empty)
- Test: `tests/rematch/test_rematch.py`

**Interfaces:**
- Consumes: `app.jellyfin.client.search_items`, `app.jellyfin.client.refresh_item` (Task 2); `settings.{arr}_url`, `settings.{arr}_api_key` (Task 1, existing)
- Produces: `async def candidates(arr: str, item: dict) -> list[dict] | None`, `async def apply(arr: str, item: dict, candidate: dict) -> bool` — consumed by Task 4. `item` dict requires keys `"path"` and `"title"`.

- [ ] **Step 1: Create empty package files**

```bash
mkdir -p app/rematch tests/rematch
touch app/rematch/__init__.py tests/rematch/__init__.py
```

- [ ] **Step 2: Write failing tests**

Create `tests/rematch/test_rematch.py`:

```python
import httpx
import respx

from app.rematch import rematch

ITEM = {"path": "/data/movies/Inception (2010)", "title": "Inception"}


@respx.mock
async def test_candidates_returns_list_on_success():
    respx.get("http://radarr-test:7878/api/v3/manualimport").mock(
        return_value=httpx.Response(200, json=[{"path": "/data/movies/Inception.mkv"}])
    )
    result = await rematch.candidates("radarr", ITEM)
    assert result == [{"path": "/data/movies/Inception.mkv"}]


@respx.mock
async def test_candidates_returns_none_on_http_error():
    respx.get("http://radarr-test:7878/api/v3/manualimport").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    result = await rematch.candidates("radarr", ITEM)
    assert result is None


@respx.mock
async def test_candidates_returns_empty_list_when_no_matches():
    respx.get("http://radarr-test:7878/api/v3/manualimport").mock(
        return_value=httpx.Response(200, json=[])
    )
    result = await rematch.candidates("radarr", ITEM)
    assert result == []


@respx.mock
async def test_apply_returns_false_when_arr_command_fails(monkeypatch):
    called = {"jellyfin": False}

    async def _fake_search(query):
        called["jellyfin"] = True
        return None

    monkeypatch.setattr("app.rematch.rematch.jellyfin.search_items", _fake_search)
    respx.post("http://radarr-test:7878/api/v3/command").mock(
        return_value=httpx.Response(500)
    )
    result = await rematch.apply("radarr", ITEM, {"path": "/data/movies/Inception.mkv"})
    assert result is False
    assert called["jellyfin"] is False


@respx.mock
async def test_apply_returns_true_when_arr_and_jellyfin_succeed(monkeypatch):
    async def _fake_search(query):
        return [{"Id": "abc123"}]

    refreshed = {}

    async def _fake_refresh(item_id):
        refreshed["id"] = item_id
        return True

    monkeypatch.setattr("app.rematch.rematch.jellyfin.search_items", _fake_search)
    monkeypatch.setattr("app.rematch.rematch.jellyfin.refresh_item", _fake_refresh)
    respx.post("http://radarr-test:7878/api/v3/command").mock(
        return_value=httpx.Response(201)
    )
    result = await rematch.apply("radarr", ITEM, {"path": "/data/movies/Inception.mkv"})
    assert result is True
    assert refreshed["id"] == "abc123"


@respx.mock
async def test_apply_returns_true_when_jellyfin_fails_but_arr_succeeded(monkeypatch):
    async def _fake_search(query):
        return None

    monkeypatch.setattr("app.rematch.rematch.jellyfin.search_items", _fake_search)
    respx.post("http://radarr-test:7878/api/v3/command").mock(
        return_value=httpx.Response(201)
    )
    result = await rematch.apply("radarr", ITEM, {"path": "/data/movies/Inception.mkv"})
    assert result is True
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/rematch/test_rematch.py -v`
Expected: FAIL with `ModuleNotFoundError` (no `rematch.py` yet)

- [ ] **Step 4: Implement the module**

Create `app/rematch/rematch.py`:

```python
import logging

import httpx

from app.config import settings
from app.jellyfin import client as jellyfin

logger = logging.getLogger(__name__)

_ARR_SETTINGS = {
    "sonarr": ("sonarr_url", "sonarr_api_key"),
    "radarr": ("radarr_url", "radarr_api_key"),
    "lidarr": ("lidarr_url", "lidarr_api_key"),
    "readarr": ("readarr_url", "readarr_api_key"),
}


def _arr_config(arr: str) -> tuple[str, str]:
    url_attr, key_attr = _ARR_SETTINGS[arr]
    return getattr(settings, url_attr), getattr(settings, key_attr)


async def candidates(arr: str, item: dict) -> list[dict] | None:
    base_url, api_key = _arr_config(arr)
    try:
        async with httpx.AsyncClient() as http:
            response = await http.get(
                f"{base_url}/api/v3/manualimport",
                headers={"X-Api-Key": api_key},
                params={"folder": item["path"]},
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        logger.error("manualimport candidates failed", extra={"error": str(exc), "arr": arr})
        return None
    return data


async def apply(arr: str, item: dict, candidate: dict) -> bool:
    base_url, api_key = _arr_config(arr)
    try:
        async with httpx.AsyncClient() as http:
            response = await http.post(
                f"{base_url}/api/v3/command",
                headers={"X-Api-Key": api_key},
                json={"name": "ManualImport", "files": [candidate]},
                timeout=5.0,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("manual import apply failed", extra={"error": str(exc), "arr": arr})
        return False

    results = await jellyfin.search_items(item.get("title", ""))
    if results:
        await jellyfin.refresh_item(results[0]["Id"])
    return True
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/rematch/test_rematch.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add app/rematch tests/rematch
git commit -m "feat: add re-match business logic"
```

---

## Task 4: UI routes + templates

**Files:**
- Modify: `app/ui/router.py`
- Create: `app/ui/templates/_rematch.html`
- Create: `app/ui/templates/_rematch_result.html`
- Modify: `tests/ui/test_router.py`

**Interfaces:**
- Consumes: `rematch.candidates(arr, item)`, `rematch.apply(arr, item, candidate)` (Task 3); existing `_CLIENTS` dict in `app/ui/router.py`
- Produces: `GET /rematch/{arr}/{item_id}?path=&title=` and `POST /rematch/{arr}/{item_id}` (form fields `path`, `title`, `candidate_index`) — consumed by Task 5's template button

- [ ] **Step 1: Write failing router tests**

Add to `tests/ui/test_router.py`:

```python
async def test_rematch_get_returns_candidates(client: AsyncClient, monkeypatch):
    async def _candidates(arr, item):
        return [{"path": "/data/movies/Inception.mkv"}]

    monkeypatch.setattr("app.rematch.rematch.candidates", _candidates)
    response = await client.get(
        "/rematch/radarr/1", params={"path": "/data/movies/Inception", "title": "Inception"}
    )
    assert response.status_code == 200
    assert "Inception.mkv" in response.text


async def test_rematch_get_unknown_arr_returns_404(client: AsyncClient):
    response = await client.get("/rematch/unknown/1", params={"path": "x", "title": "x"})
    assert response.status_code == 404


async def test_rematch_get_arr_unreachable_shows_error(client: AsyncClient, monkeypatch):
    async def _none(arr, item):
        return None

    monkeypatch.setattr("app.rematch.rematch.candidates", _none)
    response = await client.get(
        "/rematch/radarr/1", params={"path": "/data/movies/Inception", "title": "Inception"}
    )
    assert response.status_code == 200
    assert "Service indisponible" in response.text


async def test_rematch_post_applies_chosen_candidate(client: AsyncClient, monkeypatch):
    async def _candidates(arr, item):
        return [{"path": "/data/movies/Inception.mkv"}]

    async def _apply(arr, item, candidate):
        return True

    monkeypatch.setattr("app.rematch.rematch.candidates", _candidates)
    monkeypatch.setattr("app.rematch.rematch.apply", _apply)
    response = await client.post(
        "/rematch/radarr/1",
        data={"path": "/data/movies/Inception", "title": "Inception", "candidate_index": "0"},
    )
    assert response.status_code == 200
    assert "succ" in response.text.lower()


async def test_rematch_post_arr_failure_shows_error(client: AsyncClient, monkeypatch):
    async def _candidates(arr, item):
        return [{"path": "/data/movies/Inception.mkv"}]

    async def _apply(arr, item, candidate):
        return False

    monkeypatch.setattr("app.rematch.rematch.candidates", _candidates)
    monkeypatch.setattr("app.rematch.rematch.apply", _apply)
    response = await client.post(
        "/rematch/radarr/1",
        data={"path": "/data/movies/Inception", "title": "Inception", "candidate_index": "0"},
    )
    assert response.status_code == 200
    assert "Échec" in response.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_router.py -v -k rematch`
Expected: FAIL (routes/templates don't exist yet — 404 or `TemplateNotFound`)

- [ ] **Step 3: Add routes to router.py**

Edit `app/ui/router.py`, add import and two routes:

```python
from fastapi import APIRouter, Form, Request
```

(replace the existing `from fastapi import APIRouter, Request` line)

Add near the top, alongside the other imports:

```python
from app.rematch import rematch
```

Append at the end of the file:

```python
@router.get("/rematch/{arr}/{item_id}", response_class=HTMLResponse)
async def rematch_candidates(
    request: Request, arr: str, item_id: int, path: str, title: str
) -> HTMLResponse:
    if arr not in _CLIENTS:
        return HTMLResponse("Not found", status_code=404)
    result = await rematch.candidates(arr, {"path": path, "title": title})
    return templates.TemplateResponse(
        request,
        "_rematch.html",
        {
            "arr": arr,
            "item_id": item_id,
            "path": path,
            "title": title,
            "candidates": result or [],
            "error": result is None,
        },
    )


@router.post("/rematch/{arr}/{item_id}", response_class=HTMLResponse)
async def rematch_apply(
    request: Request,
    arr: str,
    item_id: int,
    path: str = Form(...),
    title: str = Form(...),
    candidate_index: int = Form(...),
) -> HTMLResponse:
    if arr not in _CLIENTS:
        return HTMLResponse("Not found", status_code=404)
    item = {"path": path, "title": title}
    result = await rematch.candidates(arr, item)
    if result is None or candidate_index >= len(result):
        return templates.TemplateResponse(request, "_rematch_result.html", {"success": False})
    chosen = result[candidate_index]
    success = await rematch.apply(arr, item, chosen)
    return templates.TemplateResponse(request, "_rematch_result.html", {"success": success})
```

- [ ] **Step 4: Create the candidate list template**

Create `app/ui/templates/_rematch.html`:

```html
{% if error %}
<p><strong>Service indisponible.</strong></p>
{% elif not candidates %}
<p>Aucun candidat trouvé.</p>
{% else %}
<form hx-post="/rematch/{{ arr }}/{{ item_id }}" hx-target="this" hx-swap="outerHTML">
    <input type="hidden" name="path" value="{{ path }}">
    <input type="hidden" name="title" value="{{ title }}">
    <ul>
        {% for c in candidates %}
        <li>
            <label>
                <input type="radio" name="candidate_index" value="{{ loop.index0 }}" {% if loop.first %}checked{% endif %}>
                {{ c.get("path", "—") }}
                {% if c.get("rejections") %}
                (rejeté : {{ c["rejections"] | map(attribute="reason") | join(", ") }})
                {% endif %}
            </label>
        </li>
        {% endfor %}
    </ul>
    <button type="submit">Appliquer</button>
</form>
{% endif %}
```

- [ ] **Step 5: Create the result template**

Create `app/ui/templates/_rematch_result.html`:

```html
{% if success %}
<p>Import appliqué avec succès.</p>
{% else %}
<p><strong>Échec de l'import.</strong></p>
{% endif %}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/ui/test_router.py -v -k rematch`
Expected: PASS (5 tests)

- [ ] **Step 7: Run full test suite**

Run: `pytest -q`
Expected: all tests PASS

- [ ] **Step 8: Commit**

```bash
git add app/ui/router.py app/ui/templates/_rematch.html app/ui/templates/_rematch_result.html tests/ui/test_router.py
git commit -m "feat: add re-match UI routes and templates"
```

---

## Task 5: Wire "Re-match" button into the library table

**Files:**
- Modify: `app/ui/templates/_tab.html`
- Modify: `tests/ui/test_router.py`

**Interfaces:**
- Consumes: `GET /rematch/{arr}/{item_id}` route (Task 4)

- [ ] **Step 1: Write failing test**

Add to `tests/ui/test_router.py`:

```python
async def test_tab_shows_rematch_button(client: AsyncClient, monkeypatch):
    async def _queue():
        return []

    async def _library():
        return [{"id": 42, "title": "Inception", "path": "/data/movies/Inception", "monitored": True}]

    monkeypatch.setattr("app.arr.sonarr.queue", _queue)
    monkeypatch.setattr("app.arr.sonarr.library", _library)
    response = await client.get("/tab/sonarr")
    assert response.status_code == 200
    assert "/rematch/sonarr/42" in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/ui/test_router.py -v -k rematch_button`
Expected: FAIL (`/rematch/sonarr/42` not in response text — button doesn't exist yet)

- [ ] **Step 3: Add the button and modal target**

Edit `app/ui/templates/_tab.html`, change the library table header and rows:

```html
    <table>
        <thead>
            <tr><th>Titre</th><th>Suivi</th><th>Actions</th></tr>
        </thead>
        <tbody>
            {% for item in library %}
            <tr>
                <td>{{ item.get("title") or item.get("artistName", "—") }}</td>
                <td>{{ "✓" if item.get("monitored") else "✗" }}</td>
                <td>
                    <button
                        hx-get="/rematch/{{ arr }}/{{ item.get('id') }}?path={{ item.get('path', '') | urlencode }}&title={{ (item.get('title') or item.get('artistName', '')) | urlencode }}"
                        hx-target="#rematch-modal">
                        Re-match
                    </button>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
```

Then add, right after the closing `{% endif %}` at the end of the file:

```html
<div id="rematch-modal"></div>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/ui/test_router.py -v -k rematch_button`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest -q`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add app/ui/templates/_tab.html tests/ui/test_router.py
git commit -m "feat: wire re-match button into library table"
```

---

## Final verification

- [ ] Run `pytest -q --cov=app` and confirm coverage stays at or above the Phase 3 bar (94%)
- [ ] Update `.ai/DEVELOPMENT_PLAN.md` Phase 4 checkboxes to `[x]`
- [ ] Commit: `git commit -m "docs: mark Phase 4 (re-match manuel) done in dev plan"`
