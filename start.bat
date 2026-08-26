@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
  call "venv\Scripts\activate.bat"
) else (
  echo No virtual environment found. Create one with:
  echo python -m venv .venv
  echo .venv\Scripts\activate
  echo pip install -r requirements.txt
  echo playwright install chromium
  pause
  exit /b 1
)

python -c "import fastapi,uvicorn,playwright,pandas,sqlalchemy" >nul 2>nul
if errorlevel 1 (
  echo Missing dependencies. Run:
  echo pip install -r requirements.txt
  echo playwright install chromium
  pause
  exit /b 1
)

start "" http://127.0.0.1:8000
python run.py
pause
