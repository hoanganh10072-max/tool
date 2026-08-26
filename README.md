# ToolSuite - Zalo Web Automation Dashboard

## Overview

Local FastAPI dashboard with a ToolSuite-style desktop UI. It lists multiple tool categories and connects the Zalo tool to the existing Python/Playwright automation backend. The Zalo page supports opening a persistent Chromium profile, checking login state, sending one message, uploading an Excel list, previewing/validating recipients, running a sequential bulk job, tracking progress, stopping the job, saving logs, and exporting results.

The app is local-only by default and binds to `127.0.0.1`.

## Requirements

- Windows, macOS, or Linux
- Python 3.11+
- A Zalo account logged in manually through the opened browser

## Install

```powershell
cd D:\TOOLMSCILABS\zalo-web-automation
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
copy .env.example .env
```

## Run

```powershell
python run.py
```

Open `http://127.0.0.1:8000`. The Zalo tool is available from the ToolSuite card or directly at `http://127.0.0.1:8000/tools/zalo/send-message`. On Windows you can run `start.bat` after dependencies are installed.

## Login Zalo

Click `Open Zalo`. Chromium opens with a persistent profile stored in `browser_profile/`. Scan the QR code manually. The app does not store passwords, cookies, tokens, or QR data in source or logs. If Zalo asks for CAPTCHA, logout recovery, or verification, handle it manually in the browser, then retry.

## Excel Format

Upload `.xlsx` only. The phone column is auto-detected from:

- `phone`
- `phone_number`
- `mobile`
- `sdt`
- `số điện thoại`
- `so dien thoai`

Optional name columns: `name`, `ten`, `tên`, `full name`, `ho ten`, `họ tên`.

## Send Single

Use the `Send Single` panel with a Vietnamese mobile number and a non-empty message. The automation is locked while an action is active, so another action returns a busy error instead of sharing the browser at the same time.

## Bulk Send

1. Upload Excel.
2. Review valid, invalid, and duplicate rows.
3. Select recipients.
4. Enter message.
5. Confirm before starting.
6. Watch progress and recent logs.
7. Export job results from Job History.

Bulk jobs run sequentially. Stop requests finish the current safe action and prevent the next recipient from starting.

## Dry Run

Set `DRY_RUN=true` in `.env` to test the full dashboard/job pipeline without sending real Zalo messages.

```env
DRY_RUN=true
```

Dry-run simulates found/sent contacts. Numbers ending in `000` simulate not found.

## API

- `GET /api/health`
- `POST /api/zalo/open`
- `GET /api/zalo/status`
- `POST /api/contacts/search`
- `POST /api/messages/send`
- `POST /api/excel/upload`
- `POST /api/jobs/bulk-send`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `POST /api/jobs/{job_id}/stop`
- `GET /api/jobs/{job_id}/export`

## Testing

```powershell
pytest
python scripts\check_frontend_buttons.py
```

Browser automation is not exercised in unit tests. Use `DRY_RUN=true` for end-to-end pipeline checks without real sending.

## Troubleshooting

- If `Open Zalo` fails, run `playwright install chromium`.
- If login status is wrong, open the browser and complete login or verification manually.
- If Zalo changes UI, update selectors in `app/automation/selectors.py`.
- If a previous run stopped mid-job, old `RUNNING` jobs are marked `INTERRUPTED` on startup and are not resumed automatically.

## Safety And Limitations

This project does not bypass CAPTCHA, anti-bot systems, rate limits, verification flows, or platform restrictions. Zalo Web selectors are best-effort and may need updates when the Zalo UI changes.
