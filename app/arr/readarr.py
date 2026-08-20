import logging

import httpx

from app.arr import cache
from app.config import settings

logger = logging.getLogger(__name__)


async def queue() -> list[dict] | None:
    key = "readarr:queue"
    cached = cache.get(settings.db_path, key)
    if cached is not None:
        return cached
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.readarr_url}/api/v1/queue",
                headers={"X-Api-Key": settings.readarr_api_key},
                params={"pageSize": 100},
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json().get("records", [])
    except httpx.HTTPError as exc:
        logger.error("readarr queue failed", extra={"error": str(exc)})
        return None
    cache.set(settings.db_path, key, data, settings.cache_ttl)
    return data


async def library() -> list[dict] | None:
    key = "readarr:library"
    cached = cache.get(settings.db_path, key)
    if cached is not None:
        return cached
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.readarr_url}/api/v1/book",
                headers={"X-Api-Key": settings.readarr_api_key},
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        logger.error("readarr library failed", extra={"error": str(exc)})
        return None
    cache.set(settings.db_path, key, data, settings.cache_ttl)
    return data
