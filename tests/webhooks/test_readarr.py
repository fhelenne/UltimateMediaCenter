import httpx
import respx
from httpx import AsyncClient

VALID_SECRET = "test-secret"

DOWNLOAD_PAYLOAD = {
    "eventType": "Download",
    "author": {"name": "Frank Herbert"},
    "books": [{"title": "Dune"}],
    "bookFiles": [{"quality": "EPUB", "path": "/test/library/incoming/Dune.epub"}],
}


async def test_download_returns_200(client: AsyncClient) -> None:
    with respx.mock:
        respx.post("http://ntfy-test:80/test").mock(return_value=httpx.Response(200))
        response = await client.post(
            "/webhook/readarr",
            json=DOWNLOAD_PAYLOAD,
            auth=("webhook", VALID_SECRET),
        )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_download_sends_correct_notification(client: AsyncClient) -> None:
    with respx.mock:
        ntfy_route = respx.post("http://ntfy-test:80/test").mock(
            return_value=httpx.Response(200)
        )
        await client.post(
            "/webhook/readarr",
            json=DOWNLOAD_PAYLOAD,
            auth=("webhook", VALID_SECRET),
        )
    assert ntfy_route.called
    req = ntfy_route.calls[0].request
    assert req.headers["Title"] == "Dune — Frank Herbert"
    assert req.content.decode() == "EPUB"


async def test_test_event_returns_ok(client: AsyncClient) -> None:
    response = await client.post(
        "/webhook/readarr",
        json={"eventType": "Test"},
        auth=("webhook", VALID_SECRET),
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_malformed_payload_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/webhook/readarr",
        json={"eventType": "UnknownEvent"},
        auth=("webhook", VALID_SECRET),
    )
    assert response.status_code == 422


async def test_download_triggers_ebook_scan(client: AsyncClient, monkeypatch) -> None:
    calls = []

    async def _fake_scan(path):
        calls.append(path)

    monkeypatch.setattr("app.webhooks.readarr.ebooks.scan_and_enrich", _fake_scan)
    with respx.mock:
        respx.post("http://ntfy-test:80/test").mock(return_value=httpx.Response(200))
        await client.post(
            "/webhook/readarr",
            json=DOWNLOAD_PAYLOAD,
            auth=("webhook", VALID_SECRET),
        )
    assert calls == ["/test/library/incoming/Dune.epub"]
