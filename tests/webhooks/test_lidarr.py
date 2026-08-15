import httpx
import respx
from httpx import AsyncClient

VALID_SECRET = "test-secret"

DOWNLOAD_PAYLOAD = {
    "eventType": "Download",
    "artist": {"name": "Radiohead"},
    "albums": [{"title": "OK Computer"}],
    "trackFiles": [{"quality": "FLAC"}],
}


async def test_download_returns_200(client: AsyncClient) -> None:
    with respx.mock:
        respx.post("http://ntfy-test:80/test").mock(return_value=httpx.Response(200))
        response = await client.post(
            "/webhook/lidarr",
            json=DOWNLOAD_PAYLOAD,
            headers={"X-Lidarr-Secret": VALID_SECRET},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_download_sends_correct_notification(client: AsyncClient) -> None:
    with respx.mock:
        ntfy_route = respx.post("http://ntfy-test:80/test").mock(
            return_value=httpx.Response(200)
        )
        await client.post(
            "/webhook/lidarr",
            json=DOWNLOAD_PAYLOAD,
            headers={"X-Lidarr-Secret": VALID_SECRET},
        )
    assert ntfy_route.called
    req = ntfy_route.calls[0].request
    assert req.headers["Title"] == "Radiohead — OK Computer"
    assert req.content.decode() == "FLAC"


async def test_first_album_used_when_multiple(client: AsyncClient) -> None:
    payload = {
        "eventType": "Download",
        "artist": {"name": "Radiohead"},
        "albums": [{"title": "OK Computer"}, {"title": "Kid A"}],
        "trackFiles": [{"quality": "FLAC"}],
    }
    with respx.mock:
        ntfy_route = respx.post("http://ntfy-test:80/test").mock(
            return_value=httpx.Response(200)
        )
        await client.post(
            "/webhook/lidarr",
            json=payload,
            headers={"X-Lidarr-Secret": VALID_SECRET},
        )
    req = ntfy_route.calls[0].request
    assert req.headers["Title"] == "Radiohead — OK Computer"


async def test_test_event_returns_ok(client: AsyncClient) -> None:
    response = await client.post(
        "/webhook/lidarr",
        json={"eventType": "Test"},
        headers={"X-Lidarr-Secret": VALID_SECRET},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_malformed_payload_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/webhook/lidarr",
        json={"eventType": "UnknownEvent"},
        headers={"X-Lidarr-Secret": VALID_SECRET},
    )
    assert response.status_code == 422
