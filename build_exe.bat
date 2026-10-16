@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 请先运行 launch_win11.bat 来安装依赖。
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m pip install -U pyinstaller || goto :fail
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name "AuroraComputer" --icon "assets\app.ico" --collect-submodules keyring.backends main.py || goto :fail
echo.
echo 构建成功：dist\AuroraComputer.exe
echo.
pause
exit /b 0
:fail
echo 构建失败。
pause
exit /b 1
