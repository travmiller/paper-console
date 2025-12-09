@echo off
setlocal enabledelayedexpansion

:: PC-1 SD Card Flashing Script for Windows
:: Uses Raspberry Pi Imager CLI for fast, reliable flashing

echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║         PC-1 SD Card Flash Script                              ║
echo ║         Flash golden images to SD cards quickly                ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

:: Configuration - UPDATE THESE PATHS
set "GOLDEN_IMAGE=C:\Code\paper-console\manufacturing\pc1-golden.img.gz"
set "RPI_IMAGER=C:\Program Files\Raspberry Pi Imager\rpi-imager.exe"

:: Check if golden image exists
if not exist "%GOLDEN_IMAGE%" (
    echo [ERROR] Golden image not found at:
    echo         %GOLDEN_IMAGE%
    echo.
    echo Please create the golden image first. See:
    echo   scripts\PRODUCTION_GUIDE.md
    echo.
    pause
    exit /b 1
)

:: Check if Raspberry Pi Imager is installed
if not exist "%RPI_IMAGER%" (
    echo [ERROR] Raspberry Pi Imager not found.
    echo         Download from: https://www.raspberrypi.com/software/
    echo.
    pause
    exit /b 1
)

echo Golden Image: %GOLDEN_IMAGE%
echo.
echo ┌────────────────────────────────────────────────────────────────┐
echo │  INSERT SD CARD NOW                                            │
echo │                                                                │
echo │  Raspberry Pi Imager will open. Select:                        │
echo │    1. Device: Raspberry Pi Zero 2 W                            │
echo │    2. OS: Use custom → Select the golden image                 │
echo │    3. Storage: Your SD card                                    │
echo │    4. Click WRITE (no customization needed!)                   │
echo │                                                                │
echo │  After flashing, eject and repeat for next card.               │
echo └────────────────────────────────────────────────────────────────┘
echo.

:FLASH_LOOP
echo Starting Raspberry Pi Imager...
start "" "%RPI_IMAGER%"

echo.
set /p CONTINUE="Flash another card? [y/N]: "
if /i "%CONTINUE%"=="y" goto FLASH_LOOP
if /i "%CONTINUE%"=="yes" goto FLASH_LOOP

echo.
echo Done! Happy shipping 📦
echo.
pause

