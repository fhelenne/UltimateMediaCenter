from fastapi import APIRouter, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

from app.config import settings
from app.webhooks.base import ArrEvent, handle_webhook

router = APIRouter()
_security = HTTPBasic(auto_error=False)


class SonarrSeries(BaseModel):
    title: str


class SonarrEpisode(BaseModel):
    title: str
    seasonNumber: int
    episodeNumber: int


class SonarrEpisodeFile(BaseModel):
    quality: str


class SonarrEvent(ArrEvent):
    series: SonarrSeries | None = None
    episodes: list[SonarrEpisode] | None = None
    episodeFile: SonarrEpisodeFile | None = None


def _format(event: SonarrEvent) -> tuple[str, str]:
    series_title = event.series.title if event.series else "Unknown"
    ep = event.episodes[0] if event.episodes else None
    ep_title = ep.title if ep else "Unknown"
    season = ep.seasonNumber if ep else 0
    ep_num = ep.episodeNumber if ep else 0
    quality = event.episodeFile.quality if event.episodeFile else "Unknown"
    return f"{series_title} S{season:02d}E{ep_num:02d}", f"{ep_title} · {quality}"


@router.post("/webhook/sonarr")
async def sonarr_webhook(
    event: SonarrEvent,
    credentials: HTTPBasicCredentials | None = Depends(_security),
) -> dict[str, str]:
    secret = credentials.password if credentials else None
    return await handle_webhook(event, secret, settings.sonarr_secret, _format)
