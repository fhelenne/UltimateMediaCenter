import time
import pytest
from app.arr.cache import get, init_db
from app.arr.cache import set as cache_set


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "cache.db")
    init_db(db_path)
    return db_path


async def test_get_missing_key_returns_none(db):
    assert get(db, "missing") is None


async def test_get_expired_key_returns_none(db):
    cache_set(db, "key", {"v": 1}, ttl=0)
    time.sleep(0.01)
    assert get(db, "key") is None


async def test_get_valid_key_returns_data(db):
    cache_set(db, "key", {"v": 42}, ttl=60)
    assert get(db, "key") == {"v": 42}


async def test_set_list_roundtrip(db):
    cache_set(db, "list", [1, 2, 3], ttl=60)
    assert get(db, "list") == [1, 2, 3]


async def test_set_upsert_overwrites(db):
    cache_set(db, "key", {"v": 1}, ttl=60)
    cache_set(db, "key", {"v": 2}, ttl=60)
    assert get(db, "key") == {"v": 2}
