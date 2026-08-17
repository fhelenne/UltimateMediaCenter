from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import auth
from app.config import settings

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "ui" / "templates")

CHANGE_PASSWORD_PATH = "/auth/change-password"


class RedirectToLogin(Exception):
    pass


class RedirectToChangePassword(Exception):
    pass


async def require_login(request: Request) -> dict:
    user_id = request.session.get("user_id")
    if user_id is None:
        raise RedirectToLogin()
    user = auth.get_user_by_id(settings.db_path, user_id)
    if user is None:
        raise RedirectToLogin()
    if user["must_change_password"] and request.url.path != CHANGE_PASSWORD_PATH:
        raise RedirectToChangePassword()
    return user


@router.get("/auth/login", response_class=HTMLResponse)
async def login_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "login.html", {"error": False})


@router.post("/auth/login", response_class=HTMLResponse, response_model=None)
async def login_submit(
    request: Request, username: str = Form(...), password: str = Form(...)
) -> HTMLResponse | RedirectResponse:
    user = auth.get_user(settings.db_path, username)
    if user is None:
        # Pay the same scrypt cost as a real check, so response time doesn't
        # leak whether the username exists.
        auth.dummy_hash(password)
        return templates.TemplateResponse(
            request, "login.html", {"error": True}, status_code=401
        )
    if not auth.verify_password(password, user):
        return templates.TemplateResponse(
            request, "login.html", {"error": True}, status_code=401
        )
    request.session["user_id"] = user["id"]
    if user["must_change_password"]:
        return RedirectResponse("/auth/change-password", status_code=303)
    return RedirectResponse("/", status_code=303)


@router.post("/auth/logout")
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/auth/login", status_code=303)


@router.get(CHANGE_PASSWORD_PATH, response_class=HTMLResponse)
async def change_password_form(
    request: Request, user: dict = Depends(require_login)
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "change_password.html",
        {"error": False, "must_change_password": user["must_change_password"]},
    )


@router.post(CHANGE_PASSWORD_PATH, response_class=HTMLResponse, response_model=None)
async def change_password_submit(
    request: Request,
    new_password: str = Form(...),
    current_password: str = Form(""),
    user: dict = Depends(require_login),
) -> HTMLResponse | RedirectResponse:
    # The forced first-change flow (right after login) doesn't require the
    # current password. A voluntary change (must_change_password already
    # False) does, so a hijacked/left-open session can't silently take over
    # the account.
    if not user["must_change_password"]:
        if not current_password or not auth.verify_password(current_password, user):
            return templates.TemplateResponse(
                request,
                "change_password.html",
                {"error": True, "must_change_password": user["must_change_password"]},
                status_code=400,
            )

    if len(new_password) < 8:
        return templates.TemplateResponse(
            request,
            "change_password.html",
            {"error": True, "must_change_password": user["must_change_password"]},
            status_code=400,
        )

    auth.set_password(settings.db_path, user["username"], new_password)
    return RedirectResponse("/", status_code=303)
