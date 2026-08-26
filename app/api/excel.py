import re
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, HttpUrl

from app.services.excel_service import excel_service

router = APIRouter(prefix="/api/excel", tags=["excel"])


class ExcelUrlImportRequest(BaseModel):
    url: HttpUrl


@router.post("/upload")
async def upload_excel(file: UploadFile = File(...)):
    content = await file.read()
    try:
        parsed = excel_service.parse_upload(file.filename or "contacts.xlsx", content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"success": True, **parsed.__dict__}


@router.post("/import-url")
async def import_excel_url(payload: ExcelUrlImportRequest):
    url = _normalize_download_url(str(payload.url))
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=422, detail="Không tải được file từ link Drive. Hãy kiểm tra quyền chia sẻ.") from exc

    content = response.content
    filename = _filename_from_response(response) or _filename_from_url(url) or "drive_contacts.xlsx"
    if not filename.lower().endswith(".xlsx"):
        filename = f"{filename.rsplit('.', 1)[0]}.xlsx" if "." in filename else f"{filename}.xlsx"
    try:
        parsed = excel_service.parse_upload(filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"success": True, **parsed.__dict__}


def _normalize_download_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "drive.google.com" not in host:
        return url

    file_id = None
    match = re.search(r"/file/d/([^/]+)", parsed.path)
    if match:
        file_id = match.group(1)
    if not file_id:
        query = parse_qs(parsed.query)
        file_id = (query.get("id") or [None])[0]
    if not file_id:
        return url
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def _filename_from_response(response: httpx.Response) -> str | None:
    disposition = response.headers.get("content-disposition", "")
    match = re.search(r"filename\*=UTF-8''([^;]+)", disposition, flags=re.I)
    if match:
        return unquote(match.group(1)).strip('"')
    match = re.search(r'filename="?([^";]+)"?', disposition, flags=re.I)
    if match:
        return unquote(match.group(1)).strip('"')
    return None


def _filename_from_url(url: str) -> str | None:
    name = urlparse(url).path.rsplit("/", 1)[-1]
    return unquote(name) if name else None
