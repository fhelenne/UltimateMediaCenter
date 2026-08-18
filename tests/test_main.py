import importlib

from httpx import AsyncClient


async def test_health_returns_200(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_session_secret_changeme_refuses_to_start(monkeypatch):
    # `settings` is a module-level singleton shared by reference across every
    # module that does `from app.config import settings` (app.ui.router,
    # app.auth.router, app.arr.cache, ...). Mutating the attribute in place
    # (rather than reloading app.config, which would build a *new* Settings
    # instance and desync those other modules from it) keeps everyone's
    # reference consistent, so we only need to reload app.main itself.
    import app.config
    import app.main

    monkeypatch.setattr(app.config.settings, "session_secret", "changeme")
    try:
        try:
            importlib.reload(app.main)
        except RuntimeError:
            pass
        else:
            raise AssertionError("expected RuntimeError for SESSION_SECRET=changeme")
    finally:
        monkeypatch.setattr(app.config.settings, "session_secret", "test-session-secret")
        importlib.reload(app.main)
