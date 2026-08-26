from sqlalchemy import inspect, select, text

from app.database.db import Base, SessionLocal, engine
from app.models.job import Job


def init_db() -> None:
    import app.models.message_log  # noqa: F401
    import app.models.recipient  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_job_columns()


def _ensure_job_columns() -> None:
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("jobs")}
    if "image_paths" in columns:
        return
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE jobs ADD COLUMN image_paths TEXT"))


def mark_stale_running_jobs_interrupted() -> int:
    with SessionLocal() as db:
        jobs = db.execute(select(Job).where(Job.status == "RUNNING")).scalars().all()
        for job in jobs:
            job.status = "INTERRUPTED"
            job.stop_requested = True
        db.commit()
        return len(jobs)
