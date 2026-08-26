from pydantic import BaseModel, Field


class SendMessageRequest(BaseModel):
    phone: str = Field(min_length=1, max_length=32)
    message: str = Field(min_length=1, max_length=4000)


class SendMessageResponse(BaseModel):
    success: bool
    phone: str
    status: str
    message: str | None = None
