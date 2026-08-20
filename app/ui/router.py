import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.arr import lidarr, radarr, readarr, sonarr
from app.auth.router import require_login
from app.config import settings
from app.jellyfin import client as jellyfin
from app.library import folders as library_folders
from app.library import shares as library_shares
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
async def index(request: Request, user: dict = Depends(require_login)) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "index.html", {"tabs": TABS}
    )


@router.get("/tab/{arr}", response_class=HTMLResponse)
async def tab(
    request: Request, arr: str, page: int = 1, user: dict = Depends(require_login)
) -> HTMLResponse:
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
    jellyfin_links = await _jellyfin_links(library_page)
    return templates.TemplateResponse(
        request,
        "_tab.html",
        {
            "arr": arr,
            "queue": queue_items,
            "library": library_page,
            "jellyfin_links": jellyfin_links,
            "page": page,
            "has_next": has_next,
            "error": error,
        },
    )


async def _jellyfin_links(library_page: list[dict]) -> dict[int, str]:
    titles = [item.get("title") or item.get("artistName") for item in library_page]
    results = await asyncio.gather(
        *(jellyfin.search_items(title) if title else _none() for title in titles)
    )
    links: dict[int, str] = {}
    for item, result in zip(library_page, results):
        if result:
            jf_id = result[0].get("Id")
            if jf_id:
                links[item.get("id")] = (
                    f"{settings.jellyfin_public_url}/web/index.html#!/details?id={jf_id}"
                )
    return links


async def _none() -> None:
    return None


@router.get("/rematch/{arr}/{item_id}", response_class=HTMLResponse)
async def rematch_candidates(
    request: Request,
    arr: str,
    item_id: int,
    path: str,
    title: str,
    user: dict = Depends(require_login),
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
    user: dict = Depends(require_login),
) -> HTMLResponse:
    if arr not in _CLIENTS:
        return HTMLResponse("Not found", status_code=404)
    item = {"path": path, "title": title}
    result = await rematch.candidates(arr, item)
    if result is None or candidate_index < 0 or candidate_index >= len(result):
        return templates.TemplateResponse(request, "_rematch_result.html", {"success": False})
    chosen = result[candidate_index]
    success = await rematch.apply(arr, item, chosen)
    return templates.TemplateResponse(request, "_rematch_result.html", {"success": success})


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
