@echo off
REM ============================================================
REM  ArenaEdit - Pornire rapida (dupa ce ai rulat INSTALARE.bat)
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"
title ArenaEdit

if not exist ".venv\Scripts\python.exe" (
    echo  ArenaEdit nu este instalat. Ruleaza intai INSTALARE.bat
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"
python app.py
if errorlevel 1 pause
