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


async def test_on_download_extra_called_on_download():
    calls = []

    async def _extra(event):
        calls.append(event)

    with respx.mock:
        respx.post("http://ntfy-test:80/test").mock(return_value=httpx.Response(200))
        await handle_webhook(
            _Event(eventType="Download"), SECRET, SECRET, _fmt, on_download_extra=_extra
        )
    assert len(calls) == 1


async def test_on_download_extra_not_called_on_test_event():
    calls = []

    async def _extra(event):
        calls.append(event)

    await handle_webhook(
        _Event(eventType="Test"), SECRET, SECRET, _fmt, on_download_extra=_extra
    )
    assert calls == []


async def test_on_download_extra_not_called_on_wrong_secret():
    calls = []

    async def _extra(event):
        calls.append(event)

    with pytest.raises(HTTPException):
        await handle_webhook(
            _Event(eventType="Download"), "wrong", SECRET, _fmt, on_download_extra=_extra
        )
    assert calls == []


async def test_on_download_extra_error_does_not_fail_webhook(monkeypatch):
    async def _extra(event):
        raise RuntimeError("boom")

    with respx.mock:
        respx.post("http://ntfy-test:80/test").mock(return_value=httpx.Response(200))
        result = await handle_webhook(
            _Event(eventType="Download"), SECRET, SECRET, _fmt, on_download_extra=_extra
        )
    assert result == {"status": "ok"}
