import pytest

from app.auth import auth


@pytest.fixture(autouse=True)
def _no_jellyfin_lookup(monkeypatch):
    async def _none(query):
        return None

    monkeypatch.setattr("app.jellyfin.client.search_items", _none)


@pytest.fixture(autouse=True)
async def _authed(client, db_path):
    auth.create_user(db_path, "admin", "initial-pass", must_change_password=True)
    await client.post("/auth/login", data={"username": "admin", "password": "initial-pass"})
    await client.post("/auth/change-password", data={"new_password": "final-pass"})
