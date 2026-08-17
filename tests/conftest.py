import os

os.environ["NTFY_URL"] = "http://ntfy-test:80"
os.environ["NTFY_TOPIC"] = "test"
os.environ["SONARR_SECRET"] = "test-secret"
os.environ["RADARR_SECRET"] = "test-secret"
os.environ["LIDARR_SECRET"] = "test-secret"
os.environ["READARR_SECRET"] = "test-secret"
os.environ["SONARR_URL"] = "http://sonarr-test:8989"
os.environ["SONARR_API_KEY"] = "test-api-key"
os.environ["RADARR_URL"] = "http://radarr-test:7878"
os.environ["RADARR_API_KEY"] = "test-api-key"
os.environ["LIDARR_URL"] = "http://lidarr-test:8686"
os.environ["LIDARR_API_KEY"] = "test-api-key"
os.environ["READARR_URL"] = "http://readarr-test:8787"
os.environ["READARR_API_KEY"] = "test-api-key"
os.environ["JELLYFIN_URL"] = "http://jellyfin-test:8096"
os.environ["JELLYFIN_API_KEY"] = "test-api-key"
os.environ["JELLYFIN_PUBLIC_URL"] = "http://jellyfin-public-test:8096"
os.environ["SESSION_SECRET"] = "test-session-secret"
os.environ["DB_PATH"] = ":memory:"
os.environ["CALIBRE_LIBRARY_PATH"] = "/test/library"

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client() -> AsyncClient:
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture(autouse=True)
def db_path(tmp_path, monkeypatch):
    from app.arr import cache
    from app.auth import auth
    from app.config import settings

    path = str(tmp_path / "test.db")
    monkeypatch.setattr(settings, "db_path", path)
    # httpx's ASGITransport doesn't fire ASGI lifespan events, so the
    # tables the app's lifespan would normally create are initialized here.
    auth.init_db(path)
    cache.init_db(path)
    return path
