from fastapi import APIRouter, Header
from pydantic import BaseModel

from app.config import settings
from app.webhooks.base import ArrEvent, handle_webhook

router = APIRouter()


class RadarrMovie(BaseModel):
    title: str
    year: int


class RadarrMovieFile(BaseModel):
    quality: str


class RadarrEvent(ArrEvent):
    movie: RadarrMovie | None = None
    movieFile: RadarrMovieFile | None = None


def _format(event: RadarrEvent) -> tuple[str, str]:
    title = f"{event.movie.title} ({event.movie.year})" if event.movie else "Unknown"
    quality = event.movieFile.quality if event.movieFile else "Unknown"
    return title, quality


@router.post("/webhook/radarr")
async def radarr_webhook(
    event: RadarrEvent,
    x_radarr_secret: str | None = Header(default=None),
) -> dict[str, str]:
    return await handle_webhook(event, x_radarr_secret, settings.radarr_secret, _format)
