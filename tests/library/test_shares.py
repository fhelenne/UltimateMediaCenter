from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.library import db, folders, shares


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    db.init_db(path)
    return path


async def test_add_share_inserts_row_on_mount_success(db_path):
    with patch("app.library.shares._mount", AsyncMock(return_value=True)):
        result = await shares.add_share(db_path, "movies-nas", "192.168.1.10", "movies", "user", "pass")
    assert result["slug"] == "movies-nas"
    assert "password" not in result
    assert len(shares.list_shares(db_path)) == 1
    assert "password" not in shares.list_shares(db_path)[0]


async def test_add_share_returns_none_and_inserts_nothing_on_mount_failure(db_path):
    with patch("app.library.shares._mount", AsyncMock(return_value=False)):
        result = await shares.add_share(db_path, "movies-nas", "192.168.1.10", "movies", "user", "pass")
    assert result is None
    assert shares.list_shares(db_path) == []


async def test_remove_share_unmounts_and_deletes_row(db_path):
    with patch("app.library.shares._mount", AsyncMock(return_value=True)):
        added = await shares.add_share(db_path, "movies-nas", "192.168.1.10", "movies", "user", "pass")
    with patch("app.library.shares._umount", AsyncMock(return_value=True)) as mock_umount:
        result = await shares.remove_share(db_path, added["id"])
    mock_umount.assert_awaited_once()
    assert result is True
    assert shares.list_shares(db_path) == []


async def test_remove_share_refused_when_referenced_by_folder(db_path):
    with patch("app.library.shares._mount", AsyncMock(return_value=True)):
        share = await shares.add_share(db_path, "movies-nas", "192.168.1.10", "movies", "user", "pass")
    with patch("app.library.rootfolder.add_root_folder", AsyncMock(return_value="1")):
        await folders.add_folder(db_path, "radarr", f"/library-root/shares/{share['slug']}")
    result = await shares.remove_share(db_path, share["id"])
    assert result is None
    assert len(shares.list_shares(db_path)) == 1


async def test_mount_passes_password_via_env_not_argv(db_path):
    """Regression test for finding I1: the password must go through mount.cifs's
    PASSWD env var, never through -o password=..., which would leak it via ps and
    let a comma in the password inject extra CIFS options."""
    process_mock = MagicMock()
    process_mock.communicate = AsyncMock(return_value=(b"", b""))
    process_mock.returncode = 0
    with patch("app.library.shares.os.makedirs"), \
         patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process_mock)) as mock_exec:
        result = await shares._mount("movies-nas", "192.168.1.10", "movies", "user", "s3cr3t,pass")
    assert result is True
    _, kwargs = mock_exec.call_args
    assert kwargs["env"]["PASSWD"] == "s3cr3t,pass"
    called_args = mock_exec.call_args.args
    assert not any("s3cr3t,pass" in str(arg) for arg in called_args)
    assert not any("password=" in str(arg) for arg in called_args)


async def test_remount_all_remounts_every_mounted_share(db_path):
    with patch("app.library.shares._mount", AsyncMock(return_value=True)):
        await shares.add_share(db_path, "movies-nas", "192.168.1.10", "movies", "user", "pass")
        await shares.add_share(db_path, "music-nas", "192.168.1.10", "music", "user", "pass")
    with patch("app.library.shares._mount", AsyncMock(return_value=True)) as mock_mount:
        await shares.remount_all(db_path)
    assert mock_mount.await_count == 2
