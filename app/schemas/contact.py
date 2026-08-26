from pydantic import BaseModel, Field


class ContactSearchRequest(BaseModel):
    phone: str = Field(min_length=1, max_length=32)


class ContactSearchResponse(BaseModel):
    success: bool
    phone: str
    found: bool = False
    name: str | None = None
    status: str
    message: str | None = None
