from pathlib import Path
import base64
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
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


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    mark_stale_running_jobs_interrupted()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/")
async def index():
    return FileResponse(Path(frontend_dir) / "index.html")


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    return FileResponse(Path(frontend_dir) / "index.html")
