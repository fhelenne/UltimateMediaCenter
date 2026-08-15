from fastapi import FastAPI

from app.webhooks import sonarr

app = FastAPI()
app.include_router(sonarr.router)
