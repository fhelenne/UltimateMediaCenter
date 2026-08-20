from unittest.mock import AsyncMock, patch

from app.config import settings
from app.library import db as library_db


async def test_lifespan_inits_library_db_and_remounts_shares(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(settings, "db_path", db_path)

    with patch("app.library.shares.remount_all", AsyncMock()) as mock_remount:
        from app.main import lifespan, app

        async with lifespan(app):
            pass

    mock_remount.assert_awaited_once_with(db_path)
    library_db.init_db(db_path)  # doit être idempotent, ne doit pas lever
