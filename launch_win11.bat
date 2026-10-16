@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
if not exist ".venv\Scripts\pythonw.exe" (
  echo [Aurora] 首次启动，创建 Python 环境和安装依赖...
  %PY% -m venv .venv || goto :fail
  .venv\Scripts\python.exe -m pip install --upgrade pip || goto :fail
  .venv\Scripts\python.exe -m pip install -r requirements.txt || goto :fail
)
start "" ".venv\Scripts\pythonw.exe" "%~dp0main.py"
exit /b 0
:fail
echo 安装失败。请检查 Python 3.10+ 与网络连接。
pause
exit /b 1
