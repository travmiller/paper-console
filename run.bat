@echo off
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

echo Starting PC-1 Server (Windows Dev Mode)...
echo.
echo Server available at:
echo   http://localhost:8001
echo   http://localhost:8001/docs (API Documentation)
echo.
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

