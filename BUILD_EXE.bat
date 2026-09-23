@echo off
REM ============================================================
REM  ArenaEdit - Construieste ArenaEdit.exe (aplicatie portabila)
REM  Rezultatul: folderul dist\ArenaEdit\ cu ArenaEdit.exe
REM
REM  Necesita sa fi rulat intai INSTALARE.bat.
REM  Procesul dureaza 5-15 minute (exe-ul contine tot motorul AI).
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"
title ArenaEdit - Build EXE

if not exist ".venv\Scripts\python.exe" (
    echo  ArenaEdit nu este instalat. Ruleaza intai INSTALARE.bat
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"

echo  Se instaleaza PyInstaller ...
pip install "pyinstaller>=6.6" >nul
if errorlevel 1 (
    echo  [EROARE] Nu am putut instala PyInstaller.
    pause
    exit /b 1
)

echo  Se construieste ArenaEdit.exe (dureaza, ai rabdare) ...
python -m PyInstaller --noconfirm --clean --windowed --onedir ^
  --name ArenaEdit ^
  --icon "assets\icon.ico" ^
  --add-data "assets\icon.ico;assets" ^
  --collect-all customtkinter ^
  --collect-all diffusers ^
  --collect-all transformers ^
  --collect-all accelerate ^
  --collect-data safetensors ^
  app.py

if errorlevel 1 (
    echo.
    echo  [EROARE] Build-ul a esuat. Vezi mesajele de mai sus.
    pause
    exit /b 1
)

echo.
echo  ================================================
echo    Gata! Aplicatia e in:  dist\ArenaEdit\ArenaEdit.exe
echo.
echo    Poti copia folderul dist\ArenaEdit oriunde vrei
echo    (ex. pe Desktop) - functioneaza standalone.
echo    Modelele AI se descarca in subfolderul "models"
echo    langa exe, la prima folosire.
echo  ================================================
echo.
if exist "dist\ArenaEdit\ArenaEdit.exe" start "" "dist\ArenaEdit"
pause
