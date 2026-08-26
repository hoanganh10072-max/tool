from io import BytesIO

import pandas as pd

from app.services.excel_service import excel_service


def make_workbook() -> bytes:
    output = BytesIO()
    first_sheet = pd.DataFrame(
        {
            "sdt": ["0901234567", "0901234567", None, "abc", 912345678, "+84987654321"],
            "name": ["A", "Duplicate", "Empty", "Invalid", "Numeric", "Country"],
            "ghi_chu": ["A1", "A2", "goi 0934567890", "A4", "ma don 12345", "A6"],
        }
    )
    second_sheet = pd.DataFrame(
        {
            "khach": ["B", "C"],
            "noi_dung": ["sdt 0977777777", "lien he +84966666666"],
        }
    )
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        first_sheet.to_excel(writer, index=False, sheet_name="Sheet 1")
        second_sheet.to_excel(writer, index=False, sheet_name="Sheet 2")
    return output.getvalue()


def test_excel_parsing_validation_duplicate_and_empty_rows():
    parsed = excel_service.parse_upload("contacts.xlsx", make_workbook())
    assert parsed.total_rows == 7
    assert parsed.valid == 6
    assert parsed.invalid == 0
    assert parsed.duplicates == 1
    assert len(parsed.rows) == 7
    assert parsed.columns == ["Số điện thoại", "Tên", "Sheet", "Cột nguồn", "Dòng Excel"]
    assert parsed.rows[0]["data"]["Số điện thoại"] == "0901234567"
    assert parsed.rows[0]["source_column"] == "sdt"
    statuses = [row["status"] for row in parsed.rows]
    assert "VALID" in statuses
    assert "DUPLICATE" in statuses
    assert "INVALID" not in statuses
    assert any(row["phone"] == "0934567890" and row["source_column"] == "ghi_chu" for row in parsed.rows)
    assert any(row["phone"] == "0977777777" and row["source_sheet"] == "Sheet 2" for row in parsed.rows)


def test_missing_phone_column_returns_columns():
    output = BytesIO()
    pd.DataFrame({"email": ["a@example.com"], "ghi_chu": ["lien he 0987654321"]}).to_excel(output, index=False)
    parsed = excel_service.parse_upload("contacts.xlsx", output.getvalue())
    assert parsed.phone_column == "ALL_SHEETS_ALL_COLUMNS"
    assert parsed.columns == ["Số điện thoại", "Tên", "Sheet", "Cột nguồn", "Dòng Excel"]
    assert parsed.rows[0]["phone"] == "0987654321"
