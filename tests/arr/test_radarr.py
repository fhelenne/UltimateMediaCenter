import httpx
import pytest
import respx

from app.arr import radarr


@pytest.fixture
def db(tmp_path, monkeypatch):
    from app.arr import cache
    from app.config import settings

    db_path = str(tmp_path / "cache.db")
    monkeypatch.setattr(settings, "db_path", db_path)
    cache.init_db(db_path)
    return db_path


@respx.mock
async def test_queue_hits_api_on_cache_miss(db):
    respx.get("http://radarr-test:7878/api/v3/queue").mock(
        return_value=httpx.Response(200, json={"records": [{"title": "movie1", "status": "queued"}]})
    )
    result = await radarr.queue()
    assert result == [{"title": "movie1", "status": "queued"}]
    assert respx.calls.call_count == 1


@respx.mock
async def test_queue_returns_cache_on_hit(db):
    from app.arr import cache
    from app.config import settings

    cache.set(settings.db_path, "radarr:queue", [{"title": "cached"}], ttl=60)
    result = await radarr.queue()
    assert result == [{"title": "cached"}]
    assert not respx.calls


@respx.mock
async def test_library_hits_api_on_cache_miss(db):
    respx.get("http://radarr-test:7878/api/v3/movie").mock(
        return_value=httpx.Response(200, json=[{"title": "Inception", "monitored": True}])
    )
    result = await radarr.library()
    assert result == [{"title": "Inception", "monitored": True}]


@respx.mock
async def test_queue_returns_none_on_http_error(db):
    respx.get("http://radarr-test:7878/api/v3/queue").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    result = await radarr.queue()
    assert result is None
