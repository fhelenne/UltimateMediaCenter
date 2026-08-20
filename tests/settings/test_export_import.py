import sqlite3
import time
from unittest.mock import AsyncMock, patch

import pytest

from app.library import db as library_db
from app.settings import export_import


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    library_db.init_db(path)
    return path


def test_build_export_includes_env_and_excludes_machine_local_and_users(db_path):
    data = export_import.build_export(db_path)
    assert data["version"] == 1
    assert "SONARR_API_KEY" in data["env"]
    assert "SESSION_SECRET" not in data["env"]
    assert "USB_MOUNT" not in data["env"]
    assert "HOST_LIBRARY_ROOT" not in data["env"]
    assert "SHARES_MOUNT" not in data["env"]
    assert data["library_folders"] == []
    assert data["smb_shares"] == []


def test_build_export_includes_folders_and_shares_with_password(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO library_folders (arr, path, root_folder_id, created_at) VALUES (?, ?, ?, ?)",
            ("sonarr", "/library-root/tv", "1", time.time()),
        )
        conn.execute(
            "INSERT INTO smb_shares (slug, server, share, username, password, mounted, created_at) VALUES (?, ?, ?, ?, ?, 1, ?)",
            ("nas", "192.168.1.10", "movies", "u", "p", time.time()),
        )
    data = export_import.build_export(db_path)
    assert data["library_folders"] == [{"arr": "sonarr", "path": "/library-root/tv"}]
    assert data["smb_shares"] == [
        {"slug": "nas", "server": "192.168.1.10", "share": "movies", "username": "u", "password": "p"}
    ]


def test_build_export_filters_excluded_keys_even_if_in_env_keys(db_path, monkeypatch):
    # Defense in depth: even if a sensitive key is accidentally added to _ENV_KEYS,
    # it should still be excluded from the export via _EXCLUDED_ENV_KEYS
    original_env_keys = export_import._ENV_KEYS.copy()
    try:
        # Temporarily add a sensitive key to _ENV_KEYS
        monkeypatch.setattr(export_import, "_ENV_KEYS", original_env_keys + ["SESSION_SECRET"])
        data = export_import.build_export(db_path)
        # SESSION_SECRET should still not appear in the export
        assert "SESSION_SECRET" not in data["env"]
        # But other keys should still be present
        assert "SONARR_API_KEY" in data["env"]
    finally:
        monkeypatch.setattr(export_import, "_ENV_KEYS", original_env_keys)


async def test_apply_import_rejects_unknown_version(db_path):
    result = await export_import.apply_import(db_path, {"version": 99})
    assert result["errors"] == ["version d'export non supportée"]
    assert result["env_written"] is False


async def test_apply_import_writes_env_and_restores_folders_and_shares(db_path, tmp_path, monkeypatch):
    from app.config import settings

    env_path = tmp_path / ".env"
    env_path.write_text("SONARR_API_KEY=old\nSESSION_SECRET=keep-me\n")
    monkeypatch.setattr(export_import, "ENV_PATH", str(env_path))

    payload = {
        "version": 1,
        "env": {"SONARR_API_KEY": "new-key"},
        "library_folders": [{"arr": "sonarr", "path": "/library-root/tv"}],
        "smb_shares": [{"slug": "nas", "server": "s", "share": "sh", "username": "u", "password": "p"}],
    }
    with patch("app.library.folders.add_folder", AsyncMock(return_value={"id": 1})), \
         patch("app.library.shares.add_share", AsyncMock(return_value={"id": 1})):
        result = await export_import.apply_import(db_path, payload)

    assert result["env_written"] is True
    assert result["folders_restored"] == 1
    assert result["shares_restored"] == 1
    assert result["errors"] == []
    content = env_path.read_text()
    assert "SONARR_API_KEY=new-key" in content
    assert "SESSION_SECRET=keep-me" in content  # jamais touché
