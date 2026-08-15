import httpx
import pytest
import respx
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Literal

from app.webhooks.base import ArrEvent, handle_webhook


class _Event(ArrEvent):
    pass


def _fmt(event: _Event) -> tuple[str, str]:
    return "title", "body"


SECRET = "secret"


async def test_missing_secret_raises_403():
    with pytest.raises(HTTPException) as exc:
        await handle_webhook(_Event(eventType="Download"), None, SECRET, _fmt)
    assert exc.value.status_code == 403


async def test_wrong_secret_raises_403():
    with pytest.raises(HTTPException) as exc:
        await handle_webhook(_Event(eventType="Download"), "wrong", SECRET, _fmt)
    assert exc.value.status_code == 403


@respx.mock
async def test_test_event_returns_ok_without_ntfy():
    result = await handle_webhook(_Event(eventType="Test"), SECRET, SECRET, _fmt)
    assert result == {"status": "ok"}
    assert not respx.calls


@respx.mock
async def test_download_calls_ntfy():
    respx.post("http://ntfy-test:80/test").mock(return_value=httpx.Response(200))
    result = await handle_webhook(_Event(eventType="Download"), SECRET, SECRET, _fmt)
    assert result == {"status": "ok"}
    assert respx.calls.call_count == 1


async def test_ntfy_error_still_returns_ok(monkeypatch):
    async def _fail(*a, **kw):
        raise httpx.HTTPError("timeout")

    monkeypatch.setattr("app.notifications.ntfy.send", _fail)
    result = await handle_webhook(_Event(eventType="Download"), SECRET, SECRET, _fmt)
    assert result == {"status": "ok"}
