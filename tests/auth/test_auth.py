import pytest

from app.auth import auth


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "auth.db")
    auth.init_db(db_path)
    return db_path


def test_create_and_get_user(db):
    auth.create_user(db, "alice", "s3cret", must_change_password=False)
    user = auth.get_user(db, "alice")
    assert user["username"] == "alice"
    assert user["must_change_password"] is False


def test_get_missing_user_returns_none(db):
    assert auth.get_user(db, "nobody") is None


def test_get_user_by_id(db):
    auth.create_user(db, "alice", "s3cret", must_change_password=False)
    user = auth.get_user(db, "alice")
    same_user = auth.get_user_by_id(db, user["id"])
    assert same_user["username"] == "alice"


def test_get_user_by_id_missing_returns_none(db):
    assert auth.get_user_by_id(db, 999) is None


def test_verify_password_correct(db):
    auth.create_user(db, "alice", "s3cret")
    user = auth.get_user(db, "alice")
    assert auth.verify_password("s3cret", user) is True


def test_verify_password_incorrect(db):
    auth.create_user(db, "alice", "s3cret")
    user = auth.get_user(db, "alice")
    assert auth.verify_password("wrong", user) is False


def test_set_password_clears_must_change_flag(db):
    auth.create_user(db, "alice", "old-pass", must_change_password=True)
    auth.set_password(db, "alice", "new-pass")
    user = auth.get_user(db, "alice")
    assert user["must_change_password"] is False
    assert auth.verify_password("new-pass", user) is True
    assert auth.verify_password("old-pass", user) is False


def test_bootstrap_admin_creates_user_with_random_password(db):
    password = auth.bootstrap_admin(db)
    assert password is not None
    user = auth.get_user(db, "admin")
    assert user is not None
    assert user["must_change_password"] is True
    assert auth.verify_password(password, user) is True


def test_bootstrap_admin_noop_if_user_exists(db):
    auth.create_user(db, "someone", "pw")
    result = auth.bootstrap_admin(db)
    assert result is None
    assert auth.get_user(db, "admin") is None
