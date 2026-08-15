from fastapi import APIRouter, Header
from pydantic import BaseModel

from app.config import settings
from app.webhooks.base import ArrEvent, handle_webhook

router = APIRouter()


class LidarrArtist(BaseModel):
    name: str


class LidarrAlbum(BaseModel):
    title: str


class LidarrTrackFile(BaseModel):
    quality: str


class LidarrEvent(ArrEvent):
    artist: LidarrArtist | None = None
    albums: list[LidarrAlbum] | None = None
    trackFiles: list[LidarrTrackFile] | None = None


def _format(event: LidarrEvent) -> tuple[str, str]:
    artist = event.artist.name if event.artist else "Unknown"
    album = event.albums[0].title if event.albums else "Unknown"
    quality = event.trackFiles[0].quality if event.trackFiles else "Unknown"
    return f"{artist} — {album}", quality


@router.post("/webhook/lidarr")
async def lidarr_webhook(
    event: LidarrEvent,
    x_lidarr_secret: str | None = Header(default=None),
) -> dict[str, str]:
    return await handle_webhook(event, x_lidarr_secret, settings.lidarr_secret, _format)
