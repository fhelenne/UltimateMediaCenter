import os

os.environ["NTFY_URL"] = "http://ntfy-test:80"
os.environ["NTFY_TOPIC"] = "test"
os.environ["SONARR_SECRET"] = "test-secret"

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client() -> AsyncClient:
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
