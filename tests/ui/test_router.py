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


async def test_rematch_get_returns_candidates(client: AsyncClient, monkeypatch):
    async def _candidates(arr, item):
        return [{"path": "/data/movies/Inception.mkv"}]

    monkeypatch.setattr("app.rematch.rematch.candidates", _candidates)
    response = await client.get(
        "/rematch/radarr/1", params={"path": "/data/movies/Inception", "title": "Inception"}
    )
    assert response.status_code == 200
    assert "Inception.mkv" in response.text


async def test_rematch_get_unknown_arr_returns_404(client: AsyncClient):
    response = await client.get("/rematch/unknown/1", params={"path": "x", "title": "x"})
    assert response.status_code == 404


async def test_rematch_get_arr_unreachable_shows_error(client: AsyncClient, monkeypatch):
    async def _none(arr, item):
        return None

    monkeypatch.setattr("app.rematch.rematch.candidates", _none)
    response = await client.get(
        "/rematch/radarr/1", params={"path": "/data/movies/Inception", "title": "Inception"}
    )
    assert response.status_code == 200
    assert "Service indisponible" in response.text


async def test_rematch_post_applies_chosen_candidate(client: AsyncClient, monkeypatch):
    async def _candidates(arr, item):
        return [{"path": "/data/movies/Inception.mkv"}]

    async def _apply(arr, item, candidate):
        return True

    monkeypatch.setattr("app.rematch.rematch.candidates", _candidates)
    monkeypatch.setattr("app.rematch.rematch.apply", _apply)
    response = await client.post(
        "/rematch/radarr/1",
        data={"path": "/data/movies/Inception", "title": "Inception", "candidate_index": "0"},
    )
    assert response.status_code == 200
    assert "succ" in response.text.lower()


async def test_rematch_post_arr_failure_shows_error(client: AsyncClient, monkeypatch):
    async def _candidates(arr, item):
        return [{"path": "/data/movies/Inception.mkv"}]

    async def _apply(arr, item, candidate):
        return False

    monkeypatch.setattr("app.rematch.rematch.candidates", _candidates)
    monkeypatch.setattr("app.rematch.rematch.apply", _apply)
    response = await client.post(
        "/rematch/radarr/1",
        data={"path": "/data/movies/Inception", "title": "Inception", "candidate_index": "0"},
    )
    assert response.status_code == 200
    assert "Échec" in response.text
