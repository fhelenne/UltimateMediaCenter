from fastapi import APIRouter, Header
from pydantic import BaseModel

from app.config import settings
from app.webhooks.base import ArrEvent, handle_webhook

router = APIRouter()


class ReadarrAuthor(BaseModel):
    name: str


class ReadarrBook(BaseModel):
    title: str


class ReadarrBookFile(BaseModel):
    quality: str


class ReadarrEvent(ArrEvent):
    author: ReadarrAuthor | None = None
    books: list[ReadarrBook] | None = None
    bookFiles: list[ReadarrBookFile] | None = None


def _format(event: ReadarrEvent) -> tuple[str, str]:
    book = event.books[0].title if event.books else "Unknown"
    author = event.author.name if event.author else "Unknown"
    quality = event.bookFiles[0].quality if event.bookFiles else "Unknown"
    return f"{book} — {author}", quality


@router.post("/webhook/readarr")
async def readarr_webhook(
    event: ReadarrEvent,
    x_readarr_secret: str | None = Header(default=None),
) -> dict[str, str]:
    return await handle_webhook(event, x_readarr_secret, settings.readarr_secret, _format)
