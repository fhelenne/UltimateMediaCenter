import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def send(title: str, body: str) -> None:
    url = f"{settings.ntfy_url}/{settings.ntfy_topic}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                content=body,
                headers={"Title": title},
                timeout=5.0,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("ntfy send failed", extra={"error": str(exc), "url": url})
