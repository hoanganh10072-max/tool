import io
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.config import settings
from app.utils.phone import normalize_phone, validate_phone


PHONE_COLUMN_ALIASES = {"phone", "phone_number", "mobile", "sdt", "so dien thoai", "so dien thoại", "số điện thoại"}
PHONE_EXTRACT_RE = re.compile(r"(?:\+?84|0)?[\d\s().-]{8,18}\d")


@dataclass
class ParsedExcel:
    filename: str
    phone_column: str | None
    columns: list[str]
    total_rows: int
    valid: int
    invalid: int
    duplicates: int
    rows: list[dict[str, Any]]
    message: str | None = None


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text).strip().lower())
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", ascii_text)


def _is_empty_cell(value: Any) -> bool:
    if value is None or pd.isna(value):
        return True
    return str(value).strip().lower() in {"", "nan", "none", "null"}


def _display_cell(value: Any) -> str:
    if _is_empty_cell(value):
        return ""
    return str(value).strip()


def _extract_phone_numbers(value: Any) -> list[str]:
    if _is_empty_cell(value):
        return []
    text = unicodedata.normalize("NFKC", str(value))
    candidates = PHONE_EXTRACT_RE.findall(text)
    if not candidates:
        candidates = [text]
    phones: list[str] = []
    for candidate in candidates:
        phone = normalize_phone(candidate)
        if validate_phone(phone) and phone not in phones:
            phones.append(phone)
    return phones


class ExcelService:
    def validate_upload(self, filename: str, content: bytes) -> None:
        if not filename.lower().endswith(".xlsx"):
            raise ValueError("Only .xlsx files are supported")
        if len(content) > settings.upload_max_mb * 1024 * 1024:
            raise ValueError(f"File exceeds {settings.upload_max_mb} MB")

    def parse_upload(self, filename: str, content: bytes) -> ParsedExcel:
        self.validate_upload(filename, content)
        try:
            workbook = pd.read_excel(io.BytesIO(content), engine="openpyxl", dtype=object, sheet_name=None)
        except Exception as exc:
            raise ValueError("Cannot read Excel file. Ensure it is a valid .xlsx workbook.") from exc

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        valid = invalid = duplicates = 0
        scanned_rows = 0
        preview_index = 0
        for sheet_name, df in workbook.items():
            df = df.dropna(how="all")
            scanned_rows += len(df)
            columns = [str(column) for column in df.columns]
            name_column = self.detect_name_column(columns)
            for original_index, record in df.iterrows():
                name = str(record.get(name_column)).strip() if name_column and pd.notna(record.get(name_column)) else None
                for column in columns:
                    for phone in _extract_phone_numbers(record.get(column)):
                        preview_index += 1
                        status = "VALID"
                        error = None
                        selected = True
                        if phone in seen:
                            status = "DUPLICATE"
                            error = "Duplicate phone"
                            selected = False
                            duplicates += 1
                        else:
                            seen.add(phone)
                            valid += 1
                        rows.append(
                            {
                                "index": preview_index,
                                "original_row": int(original_index) + 2,
                                "phone": phone,
                                "raw_phone": _display_cell(record.get(column)),
                                "name": name,
                                "source_sheet": sheet_name,
                                "source_column": column,
                                "data": {
                                    "Số điện thoại": phone,
                                    "Tên": name or "",
                                    "Sheet": sheet_name,
                                    "Cột nguồn": column,
                                    "Dòng Excel": str(int(original_index) + 2),
                                },
                                "status": status,
                                "selected": selected,
                                "error": error,
                            }
                        )
        if not rows:
            invalid = scanned_rows
        return ParsedExcel(
            filename=filename,
            phone_column="ALL_SHEETS_ALL_COLUMNS",
            columns=["Số điện thoại", "Tên", "Sheet", "Cột nguồn", "Dòng Excel"],
            total_rows=len(rows),
            valid=valid,
            invalid=invalid,
            duplicates=duplicates,
            rows=rows,
            message=None if rows else "Không tìm thấy số điện thoại hợp lệ trong file.",
        )

    def detect_phone_column(self, columns: list[str]) -> str | None:
        folded = {_fold(column): column for column in columns}
        for alias in PHONE_COLUMN_ALIASES:
            if _fold(alias) in folded:
                return folded[_fold(alias)]
        return None

    def detect_name_column(self, columns: list[str]) -> str | None:
        folded = {_fold(column): column for column in columns}
        for alias in ("name", "ten", "tên", "full name", "ho ten", "họ tên"):
            if _fold(alias) in folded:
                return folded[_fold(alias)]
        return None


excel_service = ExcelService()
