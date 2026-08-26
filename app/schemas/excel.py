from pydantic import BaseModel


class ExcelPreviewRow(BaseModel):
    index: int
    original_row: int
    phone: str
    raw_phone: str
    name: str | None = None
    status: str
    selected: bool
    error: str | None = None


class ExcelPreviewResponse(BaseModel):
    success: bool
    filename: str
    phone_column: str | None = None
    columns: list[str] = []
    total_rows: int
    valid: int
    invalid: int
    duplicates: int
    rows: list[ExcelPreviewRow]
    message: str | None = None
