from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
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
