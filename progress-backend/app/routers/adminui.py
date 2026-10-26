"""The admin panel: server-rendered HTML, no build step, no separate deployment.

Not a CRUD interface over the tables. Each page answers a research question - who comes
back, which replies helped, which conversations touched safety. A table browser would
show the data without answering any of them.
"""

import math
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from ..config import settings
from ..deps import ADMIN_COOKIE, Db, admin_from_cookie
from ..models import User
from ..security import create_access_token, verify_password
from ..services import adminstats, ratelimit

router = APIRouter(prefix="/admin", tags=["admin-ui"], include_in_schema=False)
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def _render(request: Request, name: str, admin: User | None, page: str, **context) -> HTMLResponse:
    return templates.TemplateResponse(
        request, name, {"admin": admin, "page": page, **context}
    )


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request) -> HTMLResponse:
    return _render(request, "login.html", None, "login")


@router.post("/login")
async def login(
    request: Request,
    db: Db,
    email: str = Form(...),
    password: str = Form(...),
):
    attempt = ratelimit.Attempt(
        request,
        "admin-login",
        email,
        settings.admin_login_limit_per_email,
        settings.admin_login_limit_per_ip,
    )
    try:
        attempt.take()
    except ratelimit.TooManyAttempts as exc:
        response = _render(
            request,
            "login.html",
            None,
            "login",
            error=f"Слишком много попыток. Попробуйте через {math.ceil(exc.retry_after / 60)} мин.",
        )
        response.status_code = 429
        response.headers["Retry-After"] = str(exc.retry_after)
        return response

    user = (
        await db.execute(select(User).where(User.email == email.strip().lower()))
    ).scalar_one_or_none()

    # One message for every failure: whether the address exists, the password is wrong,
    # or the account simply is not an admin is not information worth handing out.
    if (
        user is None
        or not verify_password(password, user.password_hash)
        or user.email.lower() not in settings.admin_email_list
    ):
        return _render(request, "login.html", None, "login", error="Неверные данные.")
    attempt.succeeded()

    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie(
        ADMIN_COOKIE,
        create_access_token(user.id, user.token_version),
        httponly=True,  # not reachable from JavaScript
        samesite="lax",
        secure=request.url.scheme == "https",
        max_age=settings.access_token_ttl_min * 60,
        path="/admin",
    )
    return response


@router.get("/logout")
async def logout() -> RedirectResponse:
    response = RedirectResponse("/admin/login", status_code=303)
    response.delete_cookie(ADMIN_COOKIE, path="/admin")
    return response


def _guard(admin: User | None):
    return RedirectResponse("/admin/login", status_code=303) if admin is None else None


@router.get("", response_class=HTMLResponse)
async def overview(
    request: Request, db: Db, admin: User | None = Depends(admin_from_cookie)
):
    if admin is None:
        return _guard(admin)
    return _render(request, "overview.html", admin, "overview", o=await adminstats.overview(db))


@router.get("/users", response_class=HTMLResponse)
async def users(request: Request, db: Db, admin: User | None = Depends(admin_from_cookie)):
    if admin is None:
        return _guard(admin)
    return _render(request, "users.html", admin, "users", users=await adminstats.user_rows(db))


@router.get("/users/{user_id}", response_class=HTMLResponse)
async def user_page(
    user_id: uuid.UUID,
    request: Request,
    db: Db,
    admin: User | None = Depends(admin_from_cookie),
):
    """One person's whole history on one screen - for the interview on day seven."""
    if admin is None:
        return _guard(admin)
    detail = await adminstats.user_detail(db, user_id)
    if detail is None:
        return RedirectResponse("/admin/users", status_code=303)
    return _render(request, "user.html", admin, "users", d=detail)


@router.get("/conversations/{conversation_id}", response_class=HTMLResponse)
async def conversation_page(
    conversation_id: uuid.UUID,
    request: Request,
    db: Db,
    admin: User | None = Depends(admin_from_cookie),
):
    """One conversation as it was said; the safety list links here."""
    if admin is None:
        return _guard(admin)
    detail = await adminstats.conversation_detail(db, conversation_id)
    if detail is None:
        return RedirectResponse("/admin", status_code=303)
    return _render(request, "conversation.html", admin, "conversation", c=detail)


@router.get("/events", response_class=HTMLResponse)
async def events(request: Request, db: Db, admin: User | None = Depends(admin_from_cookie)):
    if admin is None:
        return _guard(admin)
    return _render(
        request, "events.html", admin, "events", rows=await adminstats.event_counts(db)
    )
