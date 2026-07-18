@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo EDEN's local Python environment is missing.
  echo Run:  python -m venv .venv
  echo Then: .venv\Scripts\python.exe -m pip install -r requirements.txt
  exit /b 1
)
".venv\Scripts\python.exe" run.py %*

