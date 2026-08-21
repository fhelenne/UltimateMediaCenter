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


async def test_add_folder_rejects_path_outside_host_library_root(logged_in_client):
    """Regression test for finding I3: a folder must be a sub-path of
    HOST_LIBRARY_ROOT (or SHARES_MOUNT), rejected otherwise before any add_folder call."""
    with patch("app.library.folders.add_folder", AsyncMock(return_value={"id": 1})) as mock_add:
        resp = await logged_in_client.post("/library/sonarr/folders", data={"path": "/etc/passwd"})
    assert resp.status_code == 400
    mock_add.assert_not_awaited()


async def test_add_folder_rejects_path_traversal_out_of_host_library_root(logged_in_client):
    with patch("app.library.folders.add_folder", AsyncMock(return_value={"id": 1})) as mock_add:
        resp = await logged_in_client.post(
            "/library/sonarr/folders", data={"path": "/library-root/../etc"}
        )
    assert resp.status_code == 400
    mock_add.assert_not_awaited()


async def test_add_folder_accepts_shares_mount_subpath(logged_in_client):
    with patch("app.library.folders.add_folder", AsyncMock(return_value={"id": 1})) as mock_add:
        resp = await logged_in_client.post(
            "/library/sonarr/folders", data={"path": "/library-root/shares/nas"}
        )
    assert resp.status_code == 200
    mock_add.assert_awaited_once()


async def test_remove_folder(logged_in_client):
    with patch("app.library.folders.remove_folder", AsyncMock(return_value=True)):
        resp = await logged_in_client.delete("/library/sonarr/folders/1")
    assert resp.status_code == 200


async def test_remove_folder_reports_error_when_backend_fails(logged_in_client):
    """Regression test for finding I5: a failed remove_folder (e.g. *arr API
    unreachable) must surface as an error, not be silently reported as a success."""
    with patch("app.library.folders.remove_folder", AsyncMock(return_value=False)):
        resp = await logged_in_client.delete("/library/sonarr/folders/1")
    assert resp.status_code == 200
    assert "erreur" in resp.text.lower()


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


async def test_shares_remove_reports_error_when_umount_fails(logged_in_client):
    """Regression test for finding I5: remove_share returning False (umount failed)
    must not be treated as a success."""
    with patch("app.library.shares.remove_share", AsyncMock(return_value=False)):
        resp = await logged_in_client.delete("/library/shares/1")
    assert resp.status_code != 200
    assert "erreur" in resp.text.lower()


async def test_shares_add_rejects_invalid_slug(logged_in_client):
    """Regression test for finding I2: slug must match a strict regex before being
    used as a mkdir/mount/umount path component (path traversal protection)."""
    with patch("app.library.shares.add_share", AsyncMock(return_value={"id": 1})) as mock_add:
        resp = await logged_in_client.post(
            "/library/shares",
            data={"slug": "../../etc", "server": "s", "share": "sh", "username": "u", "password": "p"},
        )
    assert resp.status_code == 400
    mock_add.assert_not_awaited()


async def test_shares_add_rejects_comma_in_server_share_or_username(logged_in_client):
    """Regression test for finding I1: a comma in server/share/username would let an
    attacker inject extra CIFS mount options via the -o option string."""
    with patch("app.library.shares.add_share", AsyncMock(return_value={"id": 1})) as mock_add:
        resp = await logged_in_client.post(
            "/library/shares",
            data={"slug": "nas", "server": "s,uid=0", "share": "sh", "username": "u", "password": "p"},
        )
    assert resp.status_code == 400
    mock_add.assert_not_awaited()
