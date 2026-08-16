from fastapi import FastAPI

from app.ui import router as ui_router
from app.webhooks import lidarr, radarr, readarr, sonarr

app = FastAPI()
app.include_router(sonarr.router)
app.include_router(radarr.router)
app.include_router(lidarr.router)
app.include_router(readarr.router)
app.include_router(ui_router.router)
