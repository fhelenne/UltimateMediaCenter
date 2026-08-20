from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def _authed():
    """Shadow tests/ui/conftest.py's autouse auto-login: this file manages
    login explicitly per test (including an unauthenticated case), so the
    shared fixture would both bypass the unauthenticated test and collide
    on the "admin" username with logged_in_client below."""
    return None


@pytest.fixture
async def logged_in_client(client):
    from app.auth import auth
    from app.config import settings

    auth.create_user(settings.db_path, "admin", "changeme", must_change_password=False)
    resp = await client.post("/auth/login", data={"username": "admin", "password": "changeme"})
    assert resp.status_code == 303
    return client


async def test_library_list_requires_login(client):
    resp = await client.get("/library/sonarr")
    assert resp.status_code in (303, 204)


async def test_library_list_renders_folders(logged_in_client):
    with patch("app.library.folders.list_folders", return_value=[
        {"id": 1, "arr": "sonarr", "path": "/library-root/tv", "root_folder_id": "1", "created_at": 0}
    ]):
        resp = await logged_in_client.get("/library/sonarr")
    assert resp.status_code == 200
    assert "/library-root/tv" in resp.text


async def test_add_folder_success(logged_in_client):
    with patch("app.library.folders.add_folder", AsyncMock(return_value={"id": 1})):
        resp = await logged_in_client.post("/library/sonarr/folders", data={"path": "/library-root/tv2"})
    assert resp.status_code == 200


async def test_add_folder_failure_shows_error(logged_in_client):
    with patch("app.library.folders.add_folder", AsyncMock(return_value=None)):
        resp = await logged_in_client.post("/library/sonarr/folders", data={"path": "/library-root/tv2"})
    assert resp.status_code == 200
    assert "erreur" in resp.text.lower()


async def test_remove_folder(logged_in_client):
    with patch("app.library.folders.remove_folder", AsyncMock(return_value=True)):
        resp = await logged_in_client.delete("/library/sonarr/folders/1")
    assert resp.status_code == 200


async def test_shares_list_and_add_and_remove(logged_in_client):
    with patch("app.library.shares.list_shares", return_value=[]):
        resp = await logged_in_client.get("/library/shares")
    assert resp.status_code == 200

    with patch("app.library.shares.add_share", AsyncMock(return_value={"id": 1, "slug": "nas"})):
        resp = await logged_in_client.post(
            "/library/shares",
            data={"slug": "nas", "server": "192.168.1.10", "share": "movies", "username": "u", "password": "p"},
        )
    assert resp.status_code == 200

    with patch("app.library.shares.remove_share", AsyncMock(return_value=True)):
        resp = await logged_in_client.delete("/library/shares/1")
    assert resp.status_code == 200

    with patch("app.library.shares.remove_share", AsyncMock(return_value=None)):
        resp = await logged_in_client.delete("/library/shares/1")
    assert resp.status_code == 400
