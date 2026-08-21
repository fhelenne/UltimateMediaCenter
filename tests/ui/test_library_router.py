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


async def test_browse_root_lists_directories(logged_in_client):
    with patch(
        "app.library.rootfolder.browse",
        AsyncMock(return_value=[{"path": "/books-library/", "name": "books-library"}]),
    ):
        resp = await logged_in_client.get("/library/readarr/browse")
    assert resp.status_code == 200
    assert "books-library" in resp.text
    assert "(remonter)" not in resp.text  # root has no parent to go up to


async def test_browse_subpath_shows_parent_link(logged_in_client):
    with patch("app.library.rootfolder.browse", AsyncMock(return_value=[])):
        resp = await logged_in_client.get("/library/readarr/browse", params={"path": "/books-library/sub"})
    assert resp.status_code == 200
    assert "(remonter)" in resp.text


async def test_browse_shows_error_on_failure(logged_in_client):
    with patch("app.library.rootfolder.browse", AsyncMock(return_value=None)):
        resp = await logged_in_client.get("/library/readarr/browse")
    assert resp.status_code == 200
    assert "erreur" in resp.text.lower()


async def test_browse_use_this_folder_form_targets_current_path(logged_in_client):
    with patch("app.library.rootfolder.browse", AsyncMock(return_value=[])):
        resp = await logged_in_client.get("/library/readarr/browse", params={"path": "/books-library"})
    assert 'value="/books-library"' in resp.text


async def test_browse_rejects_unknown_arr(logged_in_client):
    resp = await logged_in_client.get("/library/unknown/browse")
    assert resp.status_code == 404


async def test_add_folder_success(logged_in_client):
    with patch("app.library.folders.add_folder", AsyncMock(return_value={"id": 1})):
        resp = await logged_in_client.post("/library/sonarr/folders", data={"path": "/library-root/tv2"})
    assert resp.status_code == 200


async def test_add_folder_failure_shows_error(logged_in_client):
    with patch("app.library.folders.add_folder", AsyncMock(return_value=None)):
        resp = await logged_in_client.post("/library/sonarr/folders", data={"path": "/library-root/tv2"})
    assert resp.status_code == 200
    assert "erreur" in resp.text.lower()


async def test_add_folder_rejects_non_absolute_path(logged_in_client):
    """Paths now come from the *arr's own filesystem browse API (each *arr
    sees its own mounts, e.g. /books-library for readarr, which isn't under
    HOST_LIBRARY_ROOT) — the app no longer restricts to a fixed local
    prefix, it just guards against an obviously malformed relative path."""
    with patch("app.library.folders.add_folder", AsyncMock(return_value={"id": 1})) as mock_add:
        resp = await logged_in_client.post("/library/sonarr/folders", data={"path": "relative/path"})
    assert resp.status_code == 400
    mock_add.assert_not_awaited()
    # the 400 response must still be the full _library.html fragment (id
    # preserved for future hx-target swaps) with a visible error message —
    # HTMX only swaps 2xx/3xx by default without the responseHandling
    # override in base.html, so this also guards that config.
    assert 'id="library-sonarr"' in resp.text
    assert "erreur" in resp.text.lower()


async def test_add_folder_normalizes_path_traversal(logged_in_client):
    with patch("app.library.folders.add_folder", AsyncMock(return_value={"id": 1})) as mock_add:
        resp = await logged_in_client.post(
            "/library/sonarr/folders", data={"path": "/books-library/../books-library/sub"}
        )
    assert resp.status_code == 200
    assert mock_add.await_args.args[1:] == ("sonarr", "/books-library/sub")


async def test_add_folder_accepts_arr_native_path(logged_in_client):
    """A path outside HOST_LIBRARY_ROOT is fine now — e.g. readarr's own
    pre-existing /books-library mount, which the browse API surfaces."""
    with patch("app.library.folders.add_folder", AsyncMock(return_value={"id": 1})) as mock_add:
        resp = await logged_in_client.post(
            "/library/readarr/folders", data={"path": "/books-library"}
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
    assert 'id="shares-list"' in resp.text
    assert "erreur" in resp.text.lower()


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
    assert 'id="shares-list"' in resp.text
    assert "erreur" in resp.text.lower()


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
    assert 'id="shares-list"' in resp.text
    assert "erreur" in resp.text.lower()
