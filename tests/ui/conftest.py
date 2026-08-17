import pytest


@pytest.fixture(autouse=True)
def _no_jellyfin_lookup(monkeypatch):
    async def _none(query):
        return None

    monkeypatch.setattr("app.jellyfin.client.search_items", _none)
