@echo off
echo ========================================
echo PC-1 Windows Test
echo ========================================
echo.

echo [1/3] Checking Python...
python --version
if errorlevel 1 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)
echo.

echo [2/3] Installing dependencies...
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install -q -r requirements.txt
if errorlevel 1 (
    echo WARNING: Some dependencies failed to install
    echo This is OK if RPi.GPIO failed (not needed on Windows)
)
echo.

echo [3/3] Testing modules...
echo.
python test_modules.py
if errorlevel 1 (
    echo.
    echo ERROR: Module tests failed!
    pause
    exit /b 1
)
echo.

echo ========================================
echo All tests passed!
echo.
echo To start the server:
echo   run.bat
echo.
echo Or visit: http://localhost:8000/docs
echo ========================================
pause

