import logging
from collections.abc import Awaitable, Callable
from typing import Literal, TypeVar

import httpx
from fastapi import HTTPException, status
from pydantic import BaseModel

from app.notifications import ntfy

logger = logging.getLogger(__name__)


class ArrEvent(BaseModel):
    eventType: Literal["Download", "Test"]


T = TypeVar("T", bound=ArrEvent)


async def handle_webhook(
    event: T,
    received_secret: str | None,
    expected_secret: str,
    on_download: Callable[[T], tuple[str, str]],
    on_download_extra: Callable[[T], "Awaitable[None]"] | None = None,
) -> dict[str, str]:
    if received_secret != expected_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    if event.eventType == "Test":
        return {"status": "ok"}
    if on_download_extra is not None:
        try:
            await on_download_extra(event)
        except Exception as exc:  # noqa: BLE001 - best-effort side effect
            logger.error("on_download_extra failed in handle_webhook", extra={"error": str(exc)})
    title, body = on_download(event)
    try:
        await ntfy.send(title, body)
    except httpx.HTTPError as exc:
        logger.error("ntfy send failed in handle_webhook", extra={"error": str(exc)})
    return {"status": "ok"}
