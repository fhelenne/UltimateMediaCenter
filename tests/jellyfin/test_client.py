import httpx
import respx

from app.jellyfin import client


@respx.mock
async def test_search_items_returns_results():
    respx.get("http://jellyfin-test:8096/Items").mock(
        return_value=httpx.Response(200, json={"Items": [{"Id": "abc123", "Name": "Inception"}]})
    )
    result = await client.search_items("Inception")
    assert result == [{"Id": "abc123", "Name": "Inception"}]


@respx.mock
async def test_search_items_returns_none_on_http_error():
    respx.get("http://jellyfin-test:8096/Items").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    result = await client.search_items("Inception")
    assert result is None


@respx.mock
async def test_refresh_item_returns_true_on_success():
    respx.post("http://jellyfin-test:8096/Items/abc123/Refresh").mock(
        return_value=httpx.Response(204)
    )
    result = await client.refresh_item("abc123")
    assert result is True


@respx.mock
async def test_refresh_item_returns_false_on_http_error():
    respx.post("http://jellyfin-test:8096/Items/abc123/Refresh").mock(
        return_value=httpx.Response(500)
    )
    result = await client.refresh_item("abc123")
    assert result is False
