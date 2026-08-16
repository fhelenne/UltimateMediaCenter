import httpx
import respx

from app.rematch import rematch

ITEM = {"path": "/data/movies/Inception (2010)", "title": "Inception"}


@respx.mock
async def test_candidates_returns_list_on_success():
    respx.get("http://radarr-test:7878/api/v3/manualimport").mock(
        return_value=httpx.Response(200, json=[{"path": "/data/movies/Inception.mkv"}])
    )
    result = await rematch.candidates("radarr", ITEM)
    assert result == [{"path": "/data/movies/Inception.mkv"}]


@respx.mock
async def test_candidates_returns_none_on_http_error():
    respx.get("http://radarr-test:7878/api/v3/manualimport").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    result = await rematch.candidates("radarr", ITEM)
    assert result is None


@respx.mock
async def test_candidates_returns_empty_list_when_no_matches():
    respx.get("http://radarr-test:7878/api/v3/manualimport").mock(
        return_value=httpx.Response(200, json=[])
    )
    result = await rematch.candidates("radarr", ITEM)
    assert result == []


@respx.mock
async def test_apply_returns_false_when_arr_command_fails(monkeypatch):
    called = {"jellyfin": False}

    async def _fake_search(query):
        called["jellyfin"] = True
        return None

    monkeypatch.setattr("app.rematch.rematch.jellyfin.search_items", _fake_search)
    respx.post("http://radarr-test:7878/api/v3/command").mock(
        return_value=httpx.Response(500)
    )
    result = await rematch.apply("radarr", ITEM, {"path": "/data/movies/Inception.mkv"})
    assert result is False
    assert called["jellyfin"] is False


@respx.mock
async def test_apply_returns_true_when_arr_and_jellyfin_succeed(monkeypatch):
    async def _fake_search(query):
        return [{"Id": "abc123"}]

    refreshed = {}

    async def _fake_refresh(item_id):
        refreshed["id"] = item_id
        return True

    monkeypatch.setattr("app.rematch.rematch.jellyfin.search_items", _fake_search)
    monkeypatch.setattr("app.rematch.rematch.jellyfin.refresh_item", _fake_refresh)
    respx.post("http://radarr-test:7878/api/v3/command").mock(
        return_value=httpx.Response(201)
    )
    result = await rematch.apply("radarr", ITEM, {"path": "/data/movies/Inception.mkv"})
    assert result is True
    assert refreshed["id"] == "abc123"


@respx.mock
async def test_apply_returns_true_when_jellyfin_fails_but_arr_succeeded(monkeypatch):
    async def _fake_search(query):
        return None

    monkeypatch.setattr("app.rematch.rematch.jellyfin.search_items", _fake_search)
    respx.post("http://radarr-test:7878/api/v3/command").mock(
        return_value=httpx.Response(201)
    )
    result = await rematch.apply("radarr", ITEM, {"path": "/data/movies/Inception.mkv"})
    assert result is True
