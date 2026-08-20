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
