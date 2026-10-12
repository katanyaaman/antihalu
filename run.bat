@echo off
setlocal
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe dashboard.py %*
) else (
    python dashboard.py %*
)
