from typing import Literal

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from app.config import settings
from app.notifications import ntfy

router = APIRouter()


class SonarrSeries(BaseModel):
    title: str


class SonarrEpisode(BaseModel):
    title: str
    seasonNumber: int
    episodeNumber: int


class SonarrEpisodeFile(BaseModel):
    quality: str


class SonarrEvent(BaseModel):
    eventType: Literal["Download", "Test"]
    series: SonarrSeries | None = None
    episodes: list[SonarrEpisode] | None = None
    episodeFile: SonarrEpisodeFile | None = None


@router.post("/webhook/sonarr")
async def sonarr_webhook(
    event: SonarrEvent,
    x_sonarr_secret: str | None = Header(default=None),
) -> dict[str, str]:
    if x_sonarr_secret != settings.sonarr_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    if event.eventType == "Test":
        return {"status": "ok"}

    series_title = event.series.title if event.series else "Unknown"
    ep = event.episodes[0] if event.episodes else None
    ep_title = ep.title if ep else "Unknown"
    season = ep.seasonNumber if ep else 0
    ep_num = ep.episodeNumber if ep else 0
    quality = event.episodeFile.quality if event.episodeFile else "Unknown"

    title = f"{series_title} S{season:02d}E{ep_num:02d}"
    body = f"{ep_title} · {quality}"

    await ntfy.send(title, body)
    return {"status": "ok"}
