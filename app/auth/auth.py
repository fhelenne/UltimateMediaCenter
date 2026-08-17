import hashlib
import hmac
import secrets
import sqlite3

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_DKLEN = 64


def init_db(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                username             TEXT UNIQUE NOT NULL,
                password_hash        TEXT NOT NULL,
                salt                 TEXT NOT NULL,
                must_change_password INTEGER NOT NULL DEFAULT 1
            )
            """
        )


def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_DKLEN,
    ).hex()


def create_user(
    db_path: str, username: str, password: str, must_change_password: bool = True
) -> None:
    salt = secrets.token_bytes(16)
    password_hash = _hash_password(password, salt)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, salt, must_change_password) "
            "VALUES (?, ?, ?, ?)",
            (username, password_hash, salt.hex(), int(must_change_password)),
        )


def _row_to_user(row: tuple) -> dict:
    return {
        "id": row[0],
        "username": row[1],
        "password_hash": row[2],
        "salt": row[3],
        "must_change_password": bool(row[4]),
    }


def get_user(db_path: str, username: str) -> dict | None:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, salt, must_change_password "
            "FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_id(db_path: str, user_id: int) -> dict | None:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, salt, must_change_password "
            "FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return _row_to_user(row) if row else None


def verify_password(password: str, user: dict) -> bool:
    salt = bytes.fromhex(user["salt"])
    candidate = _hash_password(password, salt)
    return hmac.compare_digest(candidate, user["password_hash"])


def set_password(db_path: str, username: str, new_password: str) -> None:
    salt = secrets.token_bytes(16)
    password_hash = _hash_password(new_password, salt)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, salt = ?, must_change_password = 0 "
            "WHERE username = ?",
            (password_hash, salt.hex(), username),
        )


def bootstrap_admin(db_path: str) -> str | None:
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count > 0:
        return None
    password = secrets.token_urlsafe(16)
    create_user(db_path, "admin", password, must_change_password=True)
    return password
