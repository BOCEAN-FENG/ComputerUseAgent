@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

REM Short, user-writable venv path prevents deep Qt package paths exceeding MAX_PATH.
REM Override with AURORA_VENV_DIR if your Windows user profile is unusually long.
if not defined AURORA_VENV_DIR set "AURORA_VENV_DIR=%LOCALAPPDATA%\AuroraStudio\venv"
set "AURORA_PY=%AURORA_VENV_DIR%\Scripts\python.exe"
set "AURORA_PYW=%AURORA_VENV_DIR%\Scripts\pythonw.exe"
set "DEPS_MARKER=%AURORA_VENV_DIR%\.aurora_deps_171.ok"

if not exist "%AURORA_PY%" goto create_env

goto check_dependencies

:create_env
echo [Aurora] Creating a short-path Python environment: "%AURORA_VENV_DIR%"
where py >nul 2>nul
if errorlevel 1 goto create_with_python
py -3 -m venv "%AURORA_VENV_DIR%" || goto fail
goto check_dependencies

:create_with_python
python -m venv "%AURORA_VENV_DIR%" || goto fail

:check_dependencies
REM Do not skip installation just because pythonw.exe exists: old pip runs may be incomplete.
"%AURORA_PY%" -c "from PySide6.QtWidgets import QApplication; import httpx, PIL, pyautogui, pyperclip, keyring" >nul 2>&1
if errorlevel 1 goto install_dependencies
if not exist "%DEPS_MARKER%" goto install_dependencies
goto launch

:install_dependencies
echo [Aurora] Installing minimal GUI dependencies (PySide6-Essentials)...
"%AURORA_PY%" -m pip install --prefer-binary -r "%~dp0requirements.txt" || goto fail
"%AURORA_PY%" -c "from PySide6.QtWidgets import QApplication; import httpx, PIL, pyautogui, pyperclip, keyring" || goto fail
>"%DEPS_MARKER%" echo OK

:launch
if not exist "%AURORA_PYW%" goto fail
start "" "%AURORA_PYW%" "%~dp0main.py"
exit /b 0

:fail
echo.
echo [Aurora] Python environment initialization failed.
echo [Aurora] If Windows reports long paths, move the project to D:\Aurora
 echo [Aurora] or set AURORA_VENV_DIR to a short, writable path.
pause
exit /b 1
