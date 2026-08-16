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
