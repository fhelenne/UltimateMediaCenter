import httpx
import respx
from httpx import AsyncClient

VALID_SECRET = "test-secret"

DOWNLOAD_PAYLOAD = {
    "eventType": "Download",
    "series": {"title": "The Boys"},
    "episodes": [
        {"title": "Payback", "seasonNumber": 3, "episodeNumber": 1}
    ],
    "episodeFile": {"quality": "HDTV-1080p"},
}


async def test_test_event_returns_ok(client: AsyncClient) -> None:
    response = await client.post(
        "/webhook/sonarr",
        json={"eventType": "Test"},
        auth=("webhook", VALID_SECRET),
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_test_event_does_not_call_ntfy(client: AsyncClient) -> None:
    with respx.mock:
        ntfy_route = respx.post("http://ntfy-test:80/test").mock(
            return_value=httpx.Response(200)
        )
        await client.post(
            "/webhook/sonarr",
            json={"eventType": "Test"},
            auth=("webhook", VALID_SECRET),
        )
    assert not ntfy_route.called


async def test_missing_secret_returns_403(client: AsyncClient) -> None:
    response = await client.post("/webhook/sonarr", json=DOWNLOAD_PAYLOAD)
    assert response.status_code == 403


async def test_wrong_secret_returns_403(client: AsyncClient) -> None:
    response = await client.post(
        "/webhook/sonarr",
        json=DOWNLOAD_PAYLOAD,
        auth=("webhook", "wrong-secret"),
    )
    assert response.status_code == 403


async def test_malformed_payload_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/webhook/sonarr",
        json={"eventType": "UnknownEvent"},
        auth=("webhook", VALID_SECRET),
    )
    assert response.status_code == 422


async def test_download_returns_200(client: AsyncClient) -> None:
    with respx.mock:
        respx.post("http://ntfy-test:80/test").mock(return_value=httpx.Response(200))
        response = await client.post(
            "/webhook/sonarr",
            json=DOWNLOAD_PAYLOAD,
            auth=("webhook", VALID_SECRET),
        )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_download_sends_notification_with_correct_content(
    client: AsyncClient,
) -> None:
    with respx.mock:
        ntfy_route = respx.post("http://ntfy-test:80/test").mock(
            return_value=httpx.Response(200)
        )
        await client.post(
            "/webhook/sonarr",
            json=DOWNLOAD_PAYLOAD,
            auth=("webhook", VALID_SECRET),
        )

    assert ntfy_route.called
    req = ntfy_route.calls[0].request
    assert req.headers["Title"] == "The Boys S03E01"
    assert req.content.decode() == "Payback · HDTV-1080p"


async def test_ntfy_failure_still_returns_200(client: AsyncClient) -> None:
    with respx.mock:
        respx.post("http://ntfy-test:80/test").mock(
            side_effect=httpx.TimeoutException("timeout")
        )
        response = await client.post(
            "/webhook/sonarr",
            json=DOWNLOAD_PAYLOAD,
            auth=("webhook", VALID_SECRET),
        )
    assert response.status_code == 200
