from httpx import AsyncClient


async def test_index_returns_200_with_tabs(client: AsyncClient, monkeypatch):
    async def _empty():
        return []

    monkeypatch.setattr("app.arr.sonarr.queue", _empty)
    monkeypatch.setattr("app.arr.sonarr.library", _empty)
    response = await client.get("/")
    assert response.status_code == 200
    assert "Séries" in response.text
    assert "Films" in response.text
    assert "Musique" in response.text
    assert "Livres" in response.text


async def test_tab_sonarr_returns_200(client: AsyncClient, monkeypatch):
    async def _queue():
        return []

    async def _library():
        return [{"title": "The Boys", "monitored": True}]

    monkeypatch.setattr("app.arr.sonarr.queue", _queue)
    monkeypatch.setattr("app.arr.sonarr.library", _library)
    response = await client.get("/tab/sonarr")
    assert response.status_code == 200
    assert "The Boys" in response.text


async def test_tab_pagination(client: AsyncClient, monkeypatch):
    async def _queue():
        return []

    async def _library():
        return [{"title": f"Series {i}", "monitored": True} for i in range(30)]

    monkeypatch.setattr("app.arr.sonarr.queue", _queue)
    monkeypatch.setattr("app.arr.sonarr.library", _library)
    response = await client.get("/tab/sonarr?page=2")
    assert response.status_code == 200
    assert "Series 25" in response.text
    assert "Series 0" not in response.text


async def test_tab_service_unavailable(client: AsyncClient, monkeypatch):
    async def _none():
        return None

    monkeypatch.setattr("app.arr.sonarr.queue", _none)
    monkeypatch.setattr("app.arr.sonarr.library", _none)
    response = await client.get("/tab/sonarr")
    assert response.status_code == 200
    assert "Service indisponible" in response.text
