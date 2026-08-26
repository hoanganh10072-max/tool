@echo off
setlocal
cd /d "%~dp0"

set APP_PORT=8001
set TOOL_LOGIN_ENABLED=true

where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Please install Python 3.11 or newer, then run this file again.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv .venv
  if errorlevel 1 (
    echo Cannot create virtual environment.
    pause
    exit /b 1
  )
)

echo Checking dependencies...
".venv\Scripts\python.exe" -c "import fastapi,uvicorn,playwright,pandas,sqlalchemy" >nul 2>nul
if errorlevel 1 (
  echo Installing dependencies. This can take a few minutes...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  ".venv\Scripts\python.exe" -m playwright install chromium
  if errorlevel 1 (
    echo Dependency installation failed.
    pause
    exit /b 1
  )
)

echo Opening Tool Zalo...
start "" http://127.0.0.1:8001/login
".venv\Scripts\python.exe" run.py
if errorlevel 1 (
  echo.
  echo Tool stopped or port 8001 is already in use.
  pause
  exit /b 1
)
pause
