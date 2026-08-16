from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.arr import cache
from app.config import settings
from app.ui import router as ui_router
from app.webhooks import lidarr, radarr, readarr, sonarr


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    cache.init_db(settings.db_path)
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(sonarr.router)
app.include_router(radarr.router)
app.include_router(lidarr.router)
app.include_router(readarr.router)
app.include_router(ui_router.router)
