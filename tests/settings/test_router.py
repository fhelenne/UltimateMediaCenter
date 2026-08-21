from unittest.mock import patch

import pytest


@pytest.fixture
async def logged_in_client(client):
    from app.auth import auth
    from app.config import settings

    auth.create_user(settings.db_path, "admin", "changeme", must_change_password=False)
    resp = await client.post("/auth/login", data={"username": "admin", "password": "changeme"})
    assert resp.status_code == 303
    return client


async def test_export_requires_login(client):
    resp = await client.get("/settings/export")
    assert resp.status_code in (303, 204)


async def test_export_returns_json_when_authenticated(logged_in_client):
    resp = await logged_in_client.get("/settings/export")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == 1
    assert "env" in data
    assert "library_folders" in data
    assert "smb_shares" in data


async def test_import_requires_login(client):
    resp = await client.post(
        "/settings/import",
        files={"file": ("export.json", b"{}", "application/json")},
    )
    assert resp.status_code in (303, 204)


async def test_import_authenticated_with_valid_payload(logged_in_client):
    payload = b'{"version": 1, "env": {}, "library_folders": [], "smb_shares": []}'
    # os._exit(0) is scheduled 1s after a successful import to force a restart
    # (restart: unless-stopped picks up the rewritten .env) — must never fire
    # during the test process itself.
    with patch("os._exit") as mock_exit:
        resp = await logged_in_client.post(
            "/settings/import",
            files={"file": ("export.json", payload, "application/json")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["folders_restored"] == 0
    assert data["shares_restored"] == 0
    mock_exit.assert_not_called()  # call_later hasn't fired yet within the test


async def test_import_rejects_invalid_json(logged_in_client):
    resp = await logged_in_client.post(
        "/settings/import",
        files={"file": ("export.json", b"not json", "application/json")},
    )
    assert resp.status_code == 400
