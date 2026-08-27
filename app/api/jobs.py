import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from starlette.datastructures import UploadFile
from starlette.requests import Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database.db import get_db
from app.schemas.job import BulkSendRequest, JobStatusResponse, JobSummary
from app.services.job_service import job_service
from app.services.messaging_service import AutomationBusyError

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_JOB_IMAGES = 8
MAX_IMAGE_BYTES = settings.upload_max_mb * 1024 * 1024


@router.post("/bulk-send")
async def bulk_send(request: Request, db: Session = Depends(get_db)):
    image_paths: list[str] = []
    try:
        payload, image_paths = await _read_bulk_send_request(request)
        job = job_service.create_job(
            db,
            [recipient.model_dump() for recipient in payload.recipients],
            payload.message,
            image_paths=image_paths,
        )
        job_service.start_job(job.id)
        return {"job_id": job.id, "status": job.status}
    except AutomationBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="Payload không hợp lệ") from exc


async def _read_bulk_send_request(request: Request) -> tuple[BulkSendRequest, list[str]]:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        return BulkSendRequest.model_validate(await request.json()), []

    form = await request.form()
    raw_payload = form.get("payload")
    if not isinstance(raw_payload, str):
        raise ValueError("Thiếu dữ liệu phiên gửi")
    payload = BulkSendRequest.model_validate(json.loads(raw_payload))
    uploads = [item for item in form.getlist("images") if isinstance(item, UploadFile) and item.filename]
    image_paths = await _save_job_images(uploads)
    return payload, image_paths


async def _save_job_images(files: list[UploadFile]) -> list[str]:
    if not files:
        return []
    if len(files) > MAX_JOB_IMAGES:
        raise ValueError(f"Chỉ chọn tối đa {MAX_JOB_IMAGES} hình ảnh mỗi phiên gửi")

    target_dir = settings.project_root / "uploads" / "job-images" / uuid4().hex
    target_dir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    for index, upload in enumerate(files, start=1):
        extension = Path(upload.filename or "").suffix.lower()
        content_type = (upload.content_type or "").lower()
        if extension not in IMAGE_EXTENSIONS or not content_type.startswith("image/"):
            raise ValueError("Chỉ hỗ trợ hình ảnh .jpg, .jpeg, .png, .webp hoặc .gif")
        content = await upload.read()
        if len(content) > MAX_IMAGE_BYTES:
            raise ValueError(f"Mỗi hình ảnh không được vượt quá {settings.upload_max_mb}MB")
        file_path = target_dir / f"image_{index}{extension}"
        file_path.write_bytes(content)
        saved.append(str(file_path))
    return saved


@router.get("", response_model=list[JobSummary])
async def list_jobs(db: Session = Depends(get_db)):
    return job_service.list_jobs(db)


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: int, db: Session = Depends(get_db)):
    try:
        return job_service.get_job_status(db, job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{job_id}/stop")
async def stop_job(job_id: int, db: Session = Depends(get_db)):
    try:
        job = job_service.stop_job(db, job_id)
        return {"job_id": job.id, "status": job.status}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{job_id}/resume")
async def resume_job(job_id: int, db: Session = Depends(get_db)):
    try:
        job = job_service.resume_job(db, job_id)
        return {"job_id": job.id, "status": job.status}
    except AutomationBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{job_id}/export")
async def export_job(job_id: int, db: Session = Depends(get_db)):
    try:
        output = job_service.export_job(db, job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    headers = {"Content-Disposition": f'attachment; filename="job_{job_id}_results.xlsx"'}
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )
