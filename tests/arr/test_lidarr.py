import httpx
import pytest
import respx

from app.arr import lidarr


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
    respx.get("http://lidarr-test:8686/api/v1/queue").mock(
        return_value=httpx.Response(200, json={"records": [{"title": "album1", "status": "queued"}]})
    )
    result = await lidarr.queue()
    assert result == [{"title": "album1", "status": "queued"}]
    assert respx.calls.call_count == 1


@respx.mock
async def test_queue_returns_cache_on_hit(db):
    from app.arr import cache
    from app.config import settings

    cache.set(settings.db_path, "lidarr:queue", [{"title": "cached"}], ttl=60)
    result = await lidarr.queue()
    assert result == [{"title": "cached"}]
    assert not respx.calls


@respx.mock
async def test_library_hits_api_on_cache_miss(db):
    respx.get("http://lidarr-test:8686/api/v1/artist").mock(
        return_value=httpx.Response(200, json=[{"artistName": "Radiohead", "monitored": True}])
    )
    result = await lidarr.library()
    assert result == [{"artistName": "Radiohead", "monitored": True}]


@respx.mock
async def test_queue_returns_none_on_http_error(db):
    respx.get("http://lidarr-test:8686/api/v1/queue").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    result = await lidarr.queue()
    assert result is None
