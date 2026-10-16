@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not defined AURORA_VENV_DIR set "AURORA_VENV_DIR=%LOCALAPPDATA%\AuroraStudio\venv"
set "AURORA_PY=%AURORA_VENV_DIR%\Scripts\python.exe"
if not exist "%AURORA_PY%" goto missing
"%AURORA_PY%" -c "from PySide6.QtWidgets import QApplication; import httpx, PIL, pyautogui, pyperclip, keyring" >nul 2>&1
if errorlevel 1 goto missing

echo [Aurora] Installing PyInstaller...
"%AURORA_PY%" -m pip install -U pyinstaller || goto fail
"%AURORA_PY%" -m PyInstaller --noconfirm --clean --onefile --windowed --name "AuroraComputer" --icon "assets\app.ico" --collect-submodules keyring.backends main.py || goto fail

echo.
echo Build complete: dist\AuroraComputer.exe
pause
exit /b 0

:missing
echo [Aurora] Please launch launch_win11.bat first to install dependencies.
pause
exit /b 1

:fail
echo [Aurora] Build failed.
pause
exit /b 1
