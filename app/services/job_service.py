import asyncio
import json
import logging
import random
from datetime import datetime
from io import BytesIO

import pandas as pd
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.automation.exceptions import (
    ContactNotFoundError,
    LoginRequiredError,
    TemporaryAutomationError,
    UserActionRequiredError,
    ZaloAutomationError,
)
from app.config import settings
from app.database.db import SessionLocal
from app.models.job import Job
from app.models.message_log import MessageLog
from app.models.recipient import Recipient
from app.services.messaging_service import AutomationBusyError, MessagingService, automation_lock, messaging_service
from app.utils.phone import normalize_phone, validate_phone

logger = logging.getLogger(__name__)


class JobService:
    def __init__(self, messenger: MessagingService | None = None) -> None:
        self.messenger = messenger or messaging_service
        self._active_tasks: dict[int, asyncio.Task] = {}

    def create_job(self, db: Session, recipients: list[dict], message: str, image_paths: list[str] | None = None) -> Job:
        clean_message = message.strip()
        clean_image_paths = [str(path) for path in image_paths or [] if path]
        if not clean_message and not clean_image_paths:
            raise ValueError("Message cannot be empty")
        if len(clean_message) > 4000:
            raise ValueError("Message is too long")
        self._assert_no_active_job(db)

        normalized_rows: list[dict] = []
        seen: set[str] = set()
        for item in recipients:
            phone = normalize_phone(item.get("phone"))
            if not validate_phone(phone):
                raise ValueError(f"Invalid phone: {item.get('phone')}")
            if phone in seen:
                continue
            seen.add(phone)
            normalized_rows.append({"phone": phone, "name": item.get("name")})
        if not normalized_rows:
            raise ValueError("No valid recipients")

        job = Job(
            message=clean_message,
            image_paths=json.dumps(clean_image_paths, ensure_ascii=False) if clean_image_paths else None,
            status="PENDING",
            total=len(normalized_rows),
            pending=len(normalized_rows),
        )
        db.add(job)
        db.flush()
        for row in normalized_rows:
            db.add(Recipient(job_id=job.id, phone=row["phone"], name=row.get("name"), status="PENDING"))
        db.commit()
        db.refresh(job)
        self.log(db, job.id, None, "INFO", f"Job created with {job.total} recipients")
        return job

    def start_job(self, job_id: int) -> None:
        task = self._active_tasks.get(job_id)
        if task and not task.done():
            return
        self._active_tasks[job_id] = asyncio.create_task(self.run_job(job_id))

    async def run_job(self, job_id: int) -> None:
        if automation_lock.locked():
            with SessionLocal() as db:
                job = db.get(Job, job_id)
                if job:
                    job.status = "FAILED"
                    job.finished_at = datetime.utcnow()
                    self.log(db, job.id, None, "ERROR", "Automation is busy")
                    db.commit()
            return

        async with automation_lock:
            with SessionLocal() as db:
                job = db.get(Job, job_id)
                if not job:
                    return
                job.status = "RUNNING"
                job.started_at = datetime.utcnow()
                db.commit()
                self.log(db, job.id, None, "INFO", "Job started")

            try:
                await self._process_recipients(job_id)
            finally:
                self._active_tasks.pop(job_id, None)

    async def _process_recipients(self, job_id: int) -> None:
        while True:
            with SessionLocal() as db:
                job = db.get(Job, job_id)
                if not job:
                    return
                if job.stop_requested:
                    job.status = "STOPPED"
                    job.current_phone = None
                    job.finished_at = datetime.utcnow()
                    self.recount_job(db, job)
                    self.log(db, job.id, None, "INFO", "Job stopped by user")
                    db.commit()
                    return
                recipient = db.execute(
                    select(Recipient)
                    .where(Recipient.job_id == job_id, Recipient.status == "PENDING")
                    .order_by(Recipient.id)
                ).scalars().first()
                if not recipient:
                    job.status = "COMPLETED"
                    job.current_phone = None
                    job.finished_at = datetime.utcnow()
                    self.recount_job(db, job)
                    self.log(db, job.id, None, "INFO", "Job completed")
                    db.commit()
                    return
                recipient.status = "SENDING"
                recipient.attempts += 1
                job.current_phone = recipient.phone
                self.recount_job(db, job)
                self.log(db, job.id, recipient.id, "INFO", f"PHONE={recipient.phone} sending attempt {recipient.attempts}")
                db.commit()
                phone = recipient.phone
                message = job.message
                image_paths = job.image_path_list
                recipient_id = recipient.id

            terminal = await self._send_one(job_id, recipient_id, phone, message, image_paths)
            if terminal in {"USER_ACTION_REQUIRED", "LOGIN_REQUIRED"}:
                return
            if terminal == "SENT":
                await self._delay_if_needed(job_id)

    async def _send_one(self, job_id: int, recipient_id: int, phone: str, message: str, image_paths: list[str]) -> str:
        try:
            result = await self.messenger.send_single_unlocked(phone, message, image_paths=image_paths)
            with SessionLocal() as db:
                job = db.get(Job, job_id)
                recipient = db.get(Recipient, recipient_id)
                if job and recipient:
                    recipient.status = result.get("status", "SENT")
                    recipient.name = result.get("name") or recipient.name
                    recipient.error = None
                    recipient.sent_at = datetime.utcnow()
                    self.recount_job(db, job)
                    self.log(db, job.id, recipient.id, "INFO", f"PHONE={phone} sent")
                    db.commit()
            return "SENT"
        except ContactNotFoundError as exc:
            self._mark_recipient(job_id, recipient_id, "FAILED", str(exc), "WARN")
            return "FAILED"
        except (LoginRequiredError, UserActionRequiredError) as exc:
            status = "LOGIN_REQUIRED" if isinstance(exc, LoginRequiredError) else "USER_ACTION_REQUIRED"
            with SessionLocal() as db:
                job = db.get(Job, job_id)
                recipient = db.get(Recipient, recipient_id)
                if job and recipient:
                    recipient.status = status
                    recipient.error = str(exc)
                    job.status = status
                    job.current_phone = phone
                    self.recount_job(db, job)
                    self.log(db, job.id, recipient.id, "ERROR", f"PHONE={phone} requires manual action: {exc}")
                    db.commit()
            return status
        except TemporaryAutomationError as exc:
            with SessionLocal() as db:
                recipient = db.get(Recipient, recipient_id)
                if recipient and recipient.attempts <= settings.max_retry:
                    recipient.status = "PENDING"
                    recipient.error = str(exc)
                    self.log(db, job_id, recipient_id, "WARN", f"PHONE={phone} temporary error, retry queued: {exc}")
                    db.commit()
                    return "RETRY"
            self._mark_recipient(job_id, recipient_id, "FAILED", str(exc), "ERROR")
            return "FAILED"
        except ZaloAutomationError as exc:
            self._mark_recipient(job_id, recipient_id, "FAILED", str(exc), "ERROR")
            return "FAILED"
        except Exception as exc:
            logger.exception("Unexpected job error")
            self._mark_recipient(job_id, recipient_id, "FAILED", str(exc), "ERROR")
            return "FAILED"

    async def _delay_if_needed(self, job_id: int) -> None:
        if settings.dry_run:
            await asyncio.sleep(settings.dry_run_delay)
            return
        delay = random.uniform(settings.min_send_delay, settings.max_send_delay)
        end = asyncio.get_running_loop().time() + delay
        while asyncio.get_running_loop().time() < end:
            with SessionLocal() as db:
                job = db.get(Job, job_id)
                if not job or job.stop_requested:
                    return
            await asyncio.sleep(min(0.5, end - asyncio.get_running_loop().time()))

    def _mark_recipient(self, job_id: int, recipient_id: int, status: str, error: str, level: str) -> None:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            recipient = db.get(Recipient, recipient_id)
            if job and recipient:
                recipient.status = status
                recipient.error = error
                self.recount_job(db, job)
                self.log(db, job.id, recipient.id, level, f"PHONE={recipient.phone} {status}: {error}")
                db.commit()

    def stop_job(self, db: Session, job_id: int) -> Job:
        job = db.get(Job, job_id)
        if not job:
            raise LookupError("Job not found")
        job.stop_requested = True
        if job.status in {"PENDING"}:
            job.status = "STOPPED"
            job.finished_at = datetime.utcnow()
        self.log(db, job.id, None, "INFO", "Stop requested")
        db.commit()
        db.refresh(job)
        return job

    def resume_job(self, db: Session, job_id: int) -> Job:
        job = db.get(Job, job_id)
        if not job:
            raise LookupError("Job not found")
        if job.status not in {"LOGIN_REQUIRED", "USER_ACTION_REQUIRED", "FAILED", "STOPPED"}:
            raise ValueError("Chỉ tiếp tục được phiên đã dừng hoặc cần thao tác")
        active_db_job = (
            db.execute(select(Job).where(Job.id != job.id, Job.status.in_(["PENDING", "RUNNING"]))).scalars().first()
        )
        active_task = any(not task.done() for task_id, task in self._active_tasks.items() if task_id != job.id)
        if active_db_job or active_task:
            raise AutomationBusyError("Another job is already active")

        stuck_recipients = db.execute(
            select(Recipient)
            .where(Recipient.job_id == job.id, Recipient.status.in_(["LOGIN_REQUIRED", "USER_ACTION_REQUIRED", "SENDING"]))
            .order_by(Recipient.id)
        ).scalars().all()
        for recipient in stuck_recipients:
            recipient.status = "PENDING"
            recipient.error = None

        self.recount_job(db, job)
        if job.pending <= 0:
            job.status = "COMPLETED"
            job.current_phone = None
            job.finished_at = datetime.utcnow()
        else:
            job.status = "PENDING"
            job.stop_requested = False
            job.pause_requested = False
            job.current_phone = None
            job.finished_at = None
            self.log(db, job.id, None, "INFO", "Job resumed")
        db.commit()
        db.refresh(job)
        if job.status == "PENDING":
            self.start_job(job.id)
        return job

    def get_job_status(self, db: Session, job_id: int) -> dict:
        job = db.get(Job, job_id)
        if not job:
            raise LookupError("Job not found")
        recipients = db.execute(select(Recipient).where(Recipient.job_id == job_id).order_by(Recipient.id)).scalars().all()
        logs = db.execute(
            select(MessageLog).where(MessageLog.job_id == job_id).order_by(desc(MessageLog.id)).limit(20)
        ).scalars().all()
        processed = job.total - job.pending
        percent = round((processed / job.total) * 100, 2) if job.total else 0.0
        return {
            "id": job.id,
            "status": job.status,
            "total": job.total,
            "processed": processed,
            "success": job.success,
            "failed": job.failed,
            "not_found": job.not_found,
            "pending": job.pending,
            "current_phone": job.current_phone,
            "percent": percent,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "latest_logs": list(reversed(logs)),
            "recipients": recipients,
        }

    def list_jobs(self, db: Session) -> list[Job]:
        return db.execute(select(Job).order_by(desc(Job.id)).limit(50)).scalars().all()

    def export_job(self, db: Session, job_id: int) -> BytesIO:
        job = db.get(Job, job_id)
        if not job:
            raise LookupError("Job not found")
        recipients = db.execute(select(Recipient).where(Recipient.job_id == job_id).order_by(Recipient.id)).scalars().all()
        rows = [
            {
                "phone": row.phone,
                "name": row.name,
                "status": row.status,
                "attempts": row.attempts,
                "error": row.error,
                "sent_at": row.sent_at,
            }
            for row in recipients
        ]
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            pd.DataFrame(rows).to_excel(writer, index=False, sheet_name="results")
        output.seek(0)
        return output

    def recount_job(self, db: Session, job: Job) -> None:
        counts = dict(
            db.execute(
                select(Recipient.status, func.count(Recipient.id)).where(Recipient.job_id == job.id).group_by(Recipient.status)
            ).all()
        )
        job.success = counts.get("SENT", 0)
        job.failed = counts.get("FAILED", 0)
        job.not_found = counts.get("NOT_FOUND", 0)
        job.pending = counts.get("PENDING", 0)

    def log(self, db: Session, job_id: int | None, recipient_id: int | None, level: str, message: str) -> None:
        db.add(MessageLog(job_id=job_id, recipient_id=recipient_id, level=level, message=message))

    def _assert_no_active_job(self, db: Session) -> None:
        active_db_job = db.execute(select(Job).where(Job.status.in_(["PENDING", "RUNNING"]))).scalars().first()
        active_task = any(not task.done() for task in self._active_tasks.values())
        if active_db_job or active_task:
            raise AutomationBusyError("Another job is already active")


job_service = JobService()
