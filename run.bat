@echo off
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

echo Starting PC-1 Server...
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

