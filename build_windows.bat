@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo Spektra Product Collector - Windows build
echo ==========================================

where py >nul 2>nul
if errorlevel 1 (
  echo Python nebol najdeny. Nainstaluj Python 3.11 alebo novsi.
  pause
  exit /b 1
)

py -m pip install --upgrade pip
if errorlevel 1 goto :error

py -m pip install -r requirements.txt
if errorlevel 1 goto :error

py -m PyInstaller --noconfirm --clean --onefile --windowed --name Spektra-Product-Collector app.py
if errorlevel 1 goto :error

echo.
echo HOTOVO:
echo %CD%\dist\Spektra-Product-Collector.exe
echo.
pause
exit /b 0

:error
echo.
echo Build zlyhal. Pozri chybu vyssie.
pause
exit /b 1
