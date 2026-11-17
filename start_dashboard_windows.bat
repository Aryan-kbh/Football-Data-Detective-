@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.11 or newer from python.org.
  echo During installation, select Add Python to PATH.
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe (
  echo Creating the project virtual environment...
  python -m venv .venv
  if errorlevel 1 goto failed
)
echo Installing dependencies in the local virtual environment...
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Starting Football Data Detective. Keep this window open.
.venv\Scripts\python.exe -m streamlit run app.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo Something failed. Check the error above and follow the README setup steps.
pause
exit /b 1
