from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.arr import lidarr, radarr, readarr, sonarr
from app.rematch import rematch

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
        request, "index.html", {"tabs": TABS}
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
        request,
        "_tab.html",
        {
            "arr": arr,
            "queue": queue_items,
            "library": library_page,
            "page": page,
            "has_next": has_next,
            "error": error,
        },
    )


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
