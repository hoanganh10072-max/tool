from pathlib import Path
import base64
import hashlib
import hmac
import secrets
import time

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api import contacts, excel, health, jobs, messages, zalo
from app.config import settings
from app.database.init_db import init_db, mark_stale_running_jobs_interrupted
from app.utils.logger import configure_logging


configure_logging()
app = FastAPI(title="Zalo Web Automation Dashboard", version="0.1.0")

app.include_router(health.router)
app.include_router(zalo.router)
app.include_router(contacts.router)
app.include_router(messages.router)
app.include_router(excel.router)
app.include_router(jobs.router)

frontend_dir = settings.project_root / "frontend"
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

PUBLIC_PATHS = {
    "/login",
    "/api/auth/login",
    "/favicon.ico",
}
PUBLIC_STATIC_PREFIXES = (
    "/static/login.css",
    "/static/assets/logo-hoi-doanh-nhan",
)


def _session_signature(username: str, expires_at: int) -> str:
    payload = f"{username}:{expires_at}".encode("utf-8")
    secret = settings.tool_login_secret.encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def _make_session_token(username: str) -> str:
    expires_at = int(time.time()) + 60 * 60 * 12
    signature = _session_signature(username, expires_at)
    raw = f"{username}:{expires_at}:{signature}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _is_valid_session(token: str) -> bool:
    if not token:
        return False
    try:
        decoded = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        username, expires_text, signature = decoded.rsplit(":", 2)
        expires_at = int(expires_text)
    except Exception:
        return False
    if expires_at < int(time.time()):
        return False
    expected = _session_signature(username, expires_at)
    return username == settings.tool_login_user and secrets.compare_digest(signature, expected)


def _is_public_path(path: str) -> bool:
    return path in PUBLIC_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_STATIC_PREFIXES)


@app.middleware("http")
async def public_basic_auth(request: Request, call_next):
    if not settings.public_auth_enabled:
        return await call_next(request)

    expected_user = settings.public_auth_user
    expected_password = settings.public_auth_password
    auth_header = request.headers.get("authorization", "")
    scheme, _, token = auth_header.partition(" ")
    authenticated = False
    if scheme.lower() == "basic" and token:
        try:
            decoded = base64.b64decode(token).decode("utf-8")
            username, _, password = decoded.partition(":")
            authenticated = secrets.compare_digest(username, expected_user) and secrets.compare_digest(
                password, expected_password
            )
        except Exception:
            authenticated = False

    if not authenticated:
        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Zalo Automation"'},
            content="Authentication required",
        )
    return await call_next(request)


@app.middleware("http")
async def tool_login_session(request: Request, call_next):
    if not settings.tool_login_enabled or _is_public_path(request.url.path):
        return await call_next(request)

    token = request.cookies.get(settings.tool_login_cookie, "")
    if _is_valid_session(token):
        return await call_next(request)

    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=401, content={"detail": "Authentication required"})
    return RedirectResponse(url="/login", status_code=303)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    mark_stale_running_jobs_interrupted()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/login")
async def login_page():
    return FileResponse(Path(frontend_dir) / "login.html")


@app.post("/api/auth/login")
async def login(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    username = str(data.get("username", ""))
    password = str(data.get("password", ""))
    if not (
        secrets.compare_digest(username, settings.tool_login_user)
        and secrets.compare_digest(password, settings.tool_login_password)
    ):
        return JSONResponse(status_code=401, content={"detail": "Sai tài khoản hoặc mật khẩu"})

    response = JSONResponse(content={"success": True})
    response.set_cookie(
        key=settings.tool_login_cookie,
        value=_make_session_token(username),
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 12,
    )
    return response


@app.post("/api/auth/logout")
async def logout():
    response = JSONResponse(content={"success": True})
    response.delete_cookie(settings.tool_login_cookie)
    return response


@app.get("/")
async def index():
    return FileResponse(Path(frontend_dir) / "index.html")


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    return FileResponse(Path(frontend_dir) / "index.html")
