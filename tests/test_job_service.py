import pytest

from app.database.db import SessionLocal
from app.database.init_db import mark_stale_running_jobs_interrupted
from app.models.job import Job
from app.config import settings
from app.services.job_service import job_service


def test_create_job_and_stop_state():
    with SessionLocal() as db:
        job = job_service.create_job(db, [{"phone": "0901234567"}], "Xin chao")
        assert job.status == "PENDING"
        assert job.total == 1
        stopped = job_service.stop_job(db, job.id)
        assert stopped.status == "STOPPED"
        assert stopped.stop_requested is True


def test_create_job_with_image_only():
    with SessionLocal() as db:
        job = job_service.create_job(db, [{"phone": "0901234567"}], "", image_paths=["D:/tmp/test-image.png"])
        assert job.message == ""
        assert job.image_path_list == ["D:/tmp/test-image.png"]
        assert job.total == 1


def test_startup_marks_stale_running_interrupted():
    with SessionLocal() as db:
        job = Job(message="old", status="RUNNING", total=1, pending=1)
        db.add(job)
        db.commit()
        job_id = job.id
    count = mark_stale_running_jobs_interrupted()
    assert count == 1
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        assert job.status == "INTERRUPTED"
        assert job.stop_requested is True


@pytest.mark.anyio
async def test_dry_run_job_pipeline_completes():
    original_dry_run = settings.dry_run
    original_delay = settings.dry_run_delay
    settings.dry_run = True
    settings.dry_run_delay = 0
    try:
        with SessionLocal() as db:
            job = job_service.create_job(db, [{"phone": "0901234567"}, {"phone": "0912345678"}], "Xin chao")
            job_id = job.id
        await job_service.run_job(job_id)
        with SessionLocal() as db:
            status = job_service.get_job_status(db, job_id)
            assert status["status"] == "COMPLETED"
            assert status["success"] == 2
            assert status["processed"] == 2
    finally:
        settings.dry_run = original_dry_run
        settings.dry_run_delay = original_delay
