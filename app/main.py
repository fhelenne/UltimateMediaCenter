import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from app.arr import cache
from app.auth import auth
from app.auth import router as auth_router
from app.auth.router import RedirectToChangePassword, RedirectToLogin
from app.config import settings
from app.ui import router as ui_router
from app.webhooks import lidarr, radarr, readarr, sonarr

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    cache.init_db(settings.db_path)
    auth.init_db(settings.db_path)
    password = auth.bootstrap_admin(settings.db_path)
    if password is not None:
        logger.warning("Compte admin créé, mot de passe initial: %s", password)
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)

app.include_router(sonarr.router)
app.include_router(radarr.router)
app.include_router(lidarr.router)
app.include_router(readarr.router)
app.include_router(auth_router.router)
app.include_router(ui_router.router)


@app.exception_handler(RedirectToLogin)
async def _handle_redirect_to_login(
    request: Request, exc: RedirectToLogin
) -> RedirectResponse:
    return RedirectResponse("/auth/login", status_code=303)


@app.exception_handler(RedirectToChangePassword)
async def _handle_redirect_to_change_password(
    request: Request, exc: RedirectToChangePassword
) -> RedirectResponse:
    return RedirectResponse("/auth/change-password", status_code=303)
