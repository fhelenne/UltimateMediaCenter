from httpx import AsyncClient

from app.auth import auth


async def test_login_wrong_password_shows_error(client: AsyncClient, db_path):
    auth.create_user(db_path, "admin", "correct-pass", must_change_password=False)
    response = await client.post(
        "/auth/login", data={"username": "admin", "password": "wrong"}
    )
    assert response.status_code == 401
    assert "invalides" in response.text.lower()


async def test_login_correct_password_forced_change_redirects(
    client: AsyncClient, db_path
):
    auth.create_user(db_path, "admin", "correct-pass", must_change_password=True)
    response = await client.post(
        "/auth/login", data={"username": "admin", "password": "correct-pass"}
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/auth/change-password"


async def test_login_correct_password_no_forced_change_redirects_home(
    client: AsyncClient, db_path
):
    auth.create_user(db_path, "admin", "correct-pass", must_change_password=False)
    response = await client.post(
        "/auth/login", data={"username": "admin", "password": "correct-pass"}
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"


async def test_change_password_without_session_redirects_to_login(
    client: AsyncClient, db_path
):
    response = await client.get("/auth/change-password")
    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"


async def test_change_password_updates_and_redirects_home(client: AsyncClient, db_path):
    auth.create_user(db_path, "admin", "old-pass", must_change_password=True)
    await client.post("/auth/login", data={"username": "admin", "password": "old-pass"})
    response = await client.post("/auth/change-password", data={"new_password": "new-pass"})
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    user = auth.get_user(db_path, "admin")
    assert user["must_change_password"] is False
    assert auth.verify_password("new-pass", user) is True


async def test_logout_clears_session(client: AsyncClient, db_path):
    auth.create_user(db_path, "admin", "pass", must_change_password=False)
    await client.post("/auth/login", data={"username": "admin", "password": "pass"})
    await client.post("/auth/logout")
    response = await client.get("/auth/change-password")
    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"


async def test_index_without_session_redirects_to_login(client: AsyncClient, db_path):
    response = await client.get("/")
    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"


async def test_index_without_session_htmx_returns_204_with_hx_redirect(
    client: AsyncClient, db_path
):
    response = await client.get("/", headers={"HX-Request": "true"})
    assert response.status_code == 204
    assert response.headers["HX-Redirect"] == "/auth/login"


async def test_change_password_too_short_rejected(client: AsyncClient, db_path):
    auth.create_user(db_path, "admin", "old-pass", must_change_password=True)
    await client.post("/auth/login", data={"username": "admin", "password": "old-pass"})
    response = await client.post(
        "/auth/change-password", data={"new_password": "short"}
    )
    assert response.status_code == 400
    user = auth.get_user(db_path, "admin")
    assert user["must_change_password"] is True
    assert auth.verify_password("old-pass", user) is True


async def test_voluntary_change_with_correct_current_password_succeeds(
    client: AsyncClient, db_path
):
    auth.create_user(db_path, "admin", "old-pass", must_change_password=False)
    await client.post("/auth/login", data={"username": "admin", "password": "old-pass"})
    response = await client.post(
        "/auth/change-password",
        data={"current_password": "old-pass", "new_password": "new-password"},
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    user = auth.get_user(db_path, "admin")
    assert auth.verify_password("new-password", user) is True


async def test_voluntary_change_with_wrong_current_password_fails(
    client: AsyncClient, db_path
):
    auth.create_user(db_path, "admin", "old-pass", must_change_password=False)
    await client.post("/auth/login", data={"username": "admin", "password": "old-pass"})
    response = await client.post(
        "/auth/change-password",
        data={"current_password": "wrong", "new_password": "new-password"},
    )
    assert response.status_code == 400
    user = auth.get_user(db_path, "admin")
    assert auth.verify_password("old-pass", user) is True


async def test_voluntary_change_with_missing_current_password_fails(
    client: AsyncClient, db_path
):
    auth.create_user(db_path, "admin", "old-pass", must_change_password=False)
    await client.post("/auth/login", data={"username": "admin", "password": "old-pass"})
    response = await client.post(
        "/auth/change-password", data={"new_password": "new-password"}
    )
    assert response.status_code == 400
    user = auth.get_user(db_path, "admin")
    assert auth.verify_password("old-pass", user) is True


async def test_forced_first_change_works_without_current_password(
    client: AsyncClient, db_path
):
    auth.create_user(db_path, "admin", "old-pass", must_change_password=True)
    await client.post("/auth/login", data={"username": "admin", "password": "old-pass"})
    response = await client.post(
        "/auth/change-password", data={"new_password": "new-password"}
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    user = auth.get_user(db_path, "admin")
    assert user["must_change_password"] is False
    assert auth.verify_password("new-password", user) is True


async def test_webhook_route_accessible_without_session(client: AsyncClient, db_path):
    response = await client.post(
        "/webhook/sonarr",
        json={"eventType": "Test"},
        headers={"X-Sonarr-Secret": "test-secret"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
