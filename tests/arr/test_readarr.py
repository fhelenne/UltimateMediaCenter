import httpx
import pytest
import respx

from app.arr import readarr


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
    respx.get("http://readarr-test:8787/api/v3/queue").mock(
        return_value=httpx.Response(200, json={"records": [{"title": "book1", "status": "queued"}]})
    )
    result = await readarr.queue()
    assert result == [{"title": "book1", "status": "queued"}]
    assert respx.calls.call_count == 1


@respx.mock
async def test_queue_returns_cache_on_hit(db):
    from app.arr import cache
    from app.config import settings

    cache.set(settings.db_path, "readarr:queue", [{"title": "cached"}], ttl=60)
    result = await readarr.queue()
    assert result == [{"title": "cached"}]
    assert not respx.calls


@respx.mock
async def test_library_hits_api_on_cache_miss(db):
    respx.get("http://readarr-test:8787/api/v3/book").mock(
        return_value=httpx.Response(200, json=[{"title": "Dune", "monitored": True}])
    )
    result = await readarr.library()
    assert result == [{"title": "Dune", "monitored": True}]


@respx.mock
async def test_queue_returns_none_on_http_error(db):
    respx.get("http://readarr-test:8787/api/v3/queue").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    result = await readarr.queue()
    assert result is None
