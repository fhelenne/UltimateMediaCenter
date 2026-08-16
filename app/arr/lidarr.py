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
