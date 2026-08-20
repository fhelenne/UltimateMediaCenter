from unittest.mock import AsyncMock, patch

import pytest

from app.library import db, folders


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    db.init_db(path)
    return path


async def test_add_folder_inserts_row_on_success(db_path):
    with patch("app.library.rootfolder.add_root_folder", AsyncMock(return_value="42")):
        result = await folders.add_folder(db_path, "sonarr", "/library-root/tv")
    assert result["arr"] == "sonarr"
    assert result["path"] == "/library-root/tv"
    assert result["root_folder_id"] == "42"
    assert len(folders.list_folders(db_path, "sonarr")) == 1


async def test_add_folder_returns_none_and_inserts_nothing_on_api_failure(db_path):
    with patch("app.library.rootfolder.add_root_folder", AsyncMock(return_value=None)):
        result = await folders.add_folder(db_path, "sonarr", "/library-root/tv")
    assert result is None
    assert folders.list_folders(db_path, "sonarr") == []


async def test_list_folders_filters_by_arr(db_path):
    with patch("app.library.rootfolder.add_root_folder", AsyncMock(return_value="1")):
        await folders.add_folder(db_path, "sonarr", "/library-root/tv")
        await folders.add_folder(db_path, "radarr", "/library-root/movies")
    assert len(folders.list_folders(db_path, "sonarr")) == 1
    assert len(folders.list_folders(db_path, "radarr")) == 1


async def test_remove_folder_calls_api_and_deletes_row(db_path):
    with patch("app.library.rootfolder.add_root_folder", AsyncMock(return_value="42")):
        added = await folders.add_folder(db_path, "sonarr", "/library-root/tv")
    with patch("app.library.rootfolder.remove_root_folder", AsyncMock(return_value=True)) as mock_remove:
        result = await folders.remove_folder(db_path, added["id"])
    mock_remove.assert_awaited_once_with("sonarr", "42")
    assert result is True
    assert folders.list_folders(db_path, "sonarr") == []


async def test_remove_folder_returns_false_for_unknown_id(db_path):
    result = await folders.remove_folder(db_path, 999)
    assert result is False
