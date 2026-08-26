from datetime import datetime

from pydantic import BaseModel, Field


class RecipientInput(BaseModel):
    phone: str = Field(min_length=1, max_length=32)
    name: str | None = Field(default=None, max_length=255)


class BulkSendRequest(BaseModel):
    recipients: list[RecipientInput] = Field(min_length=1)
    message: str = Field(default="", max_length=4000)


class JobCreateResponse(BaseModel):
    job_id: int
    status: str


class RecipientStatus(BaseModel):
    id: int
    phone: str
    name: str | None
    status: str
    attempts: int
    error: str | None
    sent_at: datetime | None

    model_config = {"from_attributes": True}


class LogEntry(BaseModel):
    id: int
    level: str
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}


class JobStatusResponse(BaseModel):
    id: int
    status: str
    total: int
    processed: int
    success: int
    failed: int
    not_found: int
    pending: int
    current_phone: str | None
    percent: float
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    latest_logs: list[LogEntry] = []
    recipients: list[RecipientStatus] = []


class JobSummary(BaseModel):
    id: int
    status: str
    total: int
    success: int
    failed: int
    not_found: int
    pending: int
    created_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}
