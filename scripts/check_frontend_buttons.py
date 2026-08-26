import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from openpyxl import Workbook
from playwright.sync_api import Route, expect, sync_playwright


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")


def make_test_excel() -> str:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["phone", "name"])
    sheet.append(["0901234567", "Nguyen Van A"])
    sheet.append(["0912345678", "Tran Thi B"])
    temp = NamedTemporaryFile(delete=False, suffix=".xlsx")
    temp.close()
    workbook.save(temp.name)
    return temp.name


def main() -> None:
    calls: list[tuple[str, str]] = []
    mock_state = {"job_stopped": False}

    def api_mock(route: Route) -> None:
        request = route.request
        path = request.url.replace(BASE_URL, "")
        calls.append((request.method, path))
        if path == "/api/zalo/status":
            route.fulfill(json={"browser": True, "zalo_login": False, "status": "LOGIN_REQUIRED", "profile": None})
        elif path == "/api/zalo/open":
            route.fulfill(json={"status": "LOGIN_REQUIRED", "logged_in": False})
        elif path == "/api/excel/upload":
            route.fulfill(
                json={
                    "success": True,
                    "filename": "test.xlsx",
                    "phone_column": "phone",
                    "columns": ["phone", "name"],
                    "total_rows": 2,
                    "valid": 2,
                    "invalid": 0,
                    "duplicates": 0,
                    "rows": [
                        {
                            "index": 1,
                            "original_row": 2,
                            "phone": "0901234567",
                            "raw_phone": "0901234567",
                            "name": "Nguyen Van A",
                            "status": "VALID",
                            "selected": True,
                            "error": None,
                        },
                        {
                            "index": 2,
                            "original_row": 3,
                            "phone": "0912345678",
                            "raw_phone": "0912345678",
                            "name": "Tran Thi B",
                            "status": "VALID",
                            "selected": True,
                            "error": None,
                        },
                    ],
                }
            )
        elif path == "/api/jobs/bulk-send":
            route.fulfill(json={"job_id": 123, "status": "PENDING"})
        elif path == "/api/jobs/123":
            job_status = "STOPPED" if mock_state["job_stopped"] else "RUNNING"
            route.fulfill(
                json={
                    "id": 123,
                    "status": job_status,
                    "total": 2,
                    "processed": 1 if not mock_state["job_stopped"] else 1,
                    "success": 1,
                    "failed": 0,
                    "not_found": 0,
                    "pending": 1,
                    "current_phone": "0912345678" if not mock_state["job_stopped"] else None,
                    "percent": 100,
                    "created_at": "2026-08-25T00:00:00",
                    "started_at": "2026-08-25T00:00:01",
                    "finished_at": "2026-08-25T00:00:02" if mock_state["job_stopped"] else None,
                    "latest_logs": [
                        {"id": 1, "level": "INFO", "message": "Job started", "created_at": "2026-08-25T00:00:01"}
                    ],
                    "recipients": [],
                }
            )
        elif path == "/api/jobs/123/stop":
            mock_state["job_stopped"] = True
            route.fulfill(json={"job_id": 123, "status": "STOPPED"})
        elif path == "/api/jobs":
            route.fulfill(
                json=[
                    {
                        "id": 123,
                        "status": "STOPPED" if mock_state["job_stopped"] else "RUNNING",
                        "total": 2,
                        "success": 2,
                        "failed": 0,
                        "not_found": 0,
                        "pending": 0,
                        "created_at": "2026-08-25T00:00:00",
                        "finished_at": "2026-08-25T00:00:02" if mock_state["job_stopped"] else None,
                    }
                ]
            )
        else:
            route.continue_()

    excel_path = make_test_excel()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.route(f"{BASE_URL}/api/**", api_mock)
            page.goto(BASE_URL)

            expect(page.get_by_role("heading", name="Tool Zalo kết bạn và tự động gửi tin nhắn")).to_be_visible()
            expect(page.locator(".sidebar")).to_have_count(0)
            expect(page.locator(".app-header")).to_have_count(0)
            expect(page.locator(".tool-grid")).to_have_count(0)
            expect(page.locator(".zalo-page")).to_be_visible()

            page.get_by_role("button", name="Làm mới").click()
            expect(page.locator("#zaloStatus")).to_contain_text("Cần đăng nhập")
            expect(page.locator("#zaloProfileCard")).to_contain_text("Chưa liên kết")

            page.get_by_role("button", name="Mở Zalo").click()
            expect(page.locator("#browserStatus")).to_contain_text("Đã kết nối")

            expect(page.get_by_role("heading", name="Gửi một người")).to_have_count(0)

            page.locator("#excelFile").set_input_files(excel_path)
            page.get_by_role("button", name="Tải lên và xem trước").click()
            expect(page.locator("#excelStats")).to_contain_text("hợp lệ 2")
            expect(page.locator("#recipientCounter")).to_contain_text("Đã chọn 2 người nhận")

            page.get_by_role("button", name="Bỏ chọn").click()
            expect(page.locator("#recipientCounter")).to_contain_text("Đã chọn 0 người nhận")

            page.get_by_role("button", name="Chọn tất cả").click()
            expect(page.locator("#recipientCounter")).to_contain_text("Đã chọn 2 người nhận")

            page.locator("#bulkMessage").fill("Tin nhan hang loat")
            page.once("dialog", lambda dialog: dialog.accept())
            page.get_by_role("button", name="Bắt đầu gửi").click()
            expect(page.locator("#currentJobLabel")).to_contain_text("Đang chạy")
            expect(page.locator("#processedCount")).to_contain_text("1/2")

            page.get_by_role("button", name="Dừng").click()
            expect(page.locator("#currentJobLabel")).to_contain_text("Đã dừng")

            page.get_by_role("button", name="Tải lại").click()
            expect(page.locator("#jobRows")).to_contain_text("Xuất Excel")

            browser.close()

        required_calls = {
            ("GET", "/api/zalo/status"),
            ("POST", "/api/zalo/open"),
            ("POST", "/api/excel/upload"),
            ("POST", "/api/jobs/bulk-send"),
            ("GET", "/api/jobs/123"),
            ("GET", "/api/jobs"),
        }
        missing = sorted(required_calls - set(calls))
        if missing:
            raise AssertionError(f"Missing expected API calls: {missing}")
        print("OK: Man hinh tool Zalo hoat dong.")
    finally:
        Path(excel_path).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
