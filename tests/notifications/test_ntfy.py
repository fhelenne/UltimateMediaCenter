import httpx
import respx

from app.notifications.ntfy import send


async def test_send_posts_to_ntfy_with_correct_headers() -> None:
    with respx.mock:
        route = respx.post("http://ntfy-test:80/test").mock(
            return_value=httpx.Response(200)
        )
        await send("The Boys S03E01", "Payback · HDTV-1080p")

    assert route.called
    req = route.calls[0].request
    assert req.headers["Title"] == "The Boys S03E01"
    assert req.content.decode() == "Payback · HDTV-1080p"


async def test_send_does_not_raise_on_timeout() -> None:
    with respx.mock:
        respx.post("http://ntfy-test:80/test").mock(
            side_effect=httpx.TimeoutException("timeout")
        )
        await send("title", "body")


async def test_send_does_not_raise_on_http_error() -> None:
    with respx.mock:
        respx.post("http://ntfy-test:80/test").mock(
            return_value=httpx.Response(500)
        )
        await send("title", "body")
