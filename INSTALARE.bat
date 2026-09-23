@echo off
REM ============================================================
REM  ArenaEdit - Instalare (se ruleaza O SINGURA DATA)
REM  Creeaza mediul virtual Python si instaleaza dependentele.
REM ============================================================
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title ArenaEdit - Instalare

echo.
echo  ================================================
echo    ArenaEdit - instalare initiala
echo    Au rabdare: torch + librariile AI au ~3-4 GB
echo    si dura 5-15 minute, in functie de net.
echo  ================================================
echo.

REM ---- gaseste Python (python sau py launcher)
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY (
    where py >nul 2>nul && set "PY=py -3"
)
if not defined PY (
    echo  [EROARE] Python nu a fost gasit pe acest calculator.
    echo  Descarca-l gratuit de la https://www.python.org/downloads/
    echo  IMPORTANT: la instalare, bifeaza "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)
echo  Python gasit: !PY!

REM ---- mediu virtual
if exist ".venv\Scripts\python.exe" (
    echo  Mediul virtual exista deja - se refoloseste.
) else (
    echo  Se creeaza mediul virtual .venv ...
    !PY! -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo  [EROARE] Nu am putut crea mediul virtual.
        echo  Probabil Python nu e adaugat in PATH sau lipseste componenta venv.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"

echo  Se actualizeaza pip ...
python -m pip install --upgrade pip >nul 2>nul

echo  Se instaleaza dependentele (cel mai lung pas) ...
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo  [EROARE] Instalarea dependetelor a esuat. Verifica conexiunea la internet
    echo  si ruleaza din nou acest fisier.
    pause
    exit /b 1
)

echo.
echo  ================================================
echo    Instalare completa!
echo    Se porneste aplicatia ...
echo  ================================================
echo.
python app.py
if errorlevel 1 pause
endlocal
