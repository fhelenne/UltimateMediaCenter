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


# lidarr/readarr are "profile-based" media types (books/music): unlike
# sonarr/radarr, their rootfolder endpoint 400s without a Name and a
# non-zero default metadata/quality profile id.
_PROFILE_BASED_ARRS = {"lidarr", "readarr"}


async def _first_profile_id(client: httpx.AsyncClient, base_url: str, api_version: str, api_key: str, resource: str) -> int | None:
    response = await client.get(
        f"{base_url}/api/{api_version}/{resource}",
        headers={"X-Api-Key": api_key},
        timeout=5.0,
    )
    response.raise_for_status()
    profiles = response.json()
    return profiles[0]["id"] if profiles else None


async def add_root_folder(arr: str, path: str) -> str | None:
    base_url = _URL[arr]()
    api_version = _API_VERSION[arr]
    api_key = _API_KEY[arr]()
    payload: dict = {"path": path}
    try:
        async with httpx.AsyncClient() as client:
            if arr in _PROFILE_BASED_ARRS:
                metadata_profile_id = await _first_profile_id(client, base_url, api_version, api_key, "metadataprofile")
                quality_profile_id = None
                if metadata_profile_id is not None:
                    quality_profile_id = await _first_profile_id(client, base_url, api_version, api_key, "qualityprofile")
                if metadata_profile_id is None or quality_profile_id is None:
                    logger.error(f"{arr} add_root_folder: no metadata/quality profile configured", extra={"path": path})
                    return None
                payload["name"] = path.rstrip("/").rsplit("/", 1)[-1] or path
                payload["defaultMetadataProfileId"] = metadata_profile_id
                payload["defaultQualityProfileId"] = quality_profile_id
            response = await client.post(
                f"{base_url}/api/{api_version}/rootfolder",
                headers={"X-Api-Key": api_key},
                json=payload,
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        logger.error(f"{arr} add_root_folder failed", extra={"error": str(exc), "path": path})
        return None
    return str(data["id"])


async def browse(arr: str, path: str) -> list[dict] | None:
    base_url = _URL[arr]()
    api_version = _API_VERSION[arr]
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base_url}/api/{api_version}/filesystem",
                headers={"X-Api-Key": _API_KEY[arr]()},
                params={"path": path},
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        logger.error(f"{arr} browse failed", extra={"error": str(exc), "path": path})
        return None
    return [{"path": d["path"], "name": d["name"]} for d in data.get("directories", [])]


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
