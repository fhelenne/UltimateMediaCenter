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
