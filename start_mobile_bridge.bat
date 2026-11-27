@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "PY_CMD="

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import flask, flask_cors, yt_dlp" >nul 2>nul
    if not errorlevel 1 set "PY_CMD=.venv\Scripts\python.exe"
)

if not defined PY_CMD if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" -c "import flask, flask_cors, yt_dlp" >nul 2>nul
    if not errorlevel 1 set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
)

if not defined PY_CMD (
    for %%V in (3.14 3.13 3.12 3.11) do (
        if not defined PY_CMD (
            py -%%V -c "import flask, flask_cors, yt_dlp" >nul 2>nul
            if not errorlevel 1 set "PY_CMD=py -%%V"
        )
    )
)

if not defined PY_CMD (
    python -c "import flask, flask_cors, yt_dlp" >nul 2>nul
    if not errorlevel 1 set "PY_CMD=python"
)

if not defined PY_CMD (
    echo [錯誤] 找不到已安裝 flask、flask-cors、yt-dlp 的 Python 環境。
    echo 請先建立虛擬環境並執行: pip install -r requirements.txt
    pause
    exit /b 1
)

echo [AudioStudio] 使用 Python: %PY_CMD%
%PY_CMD% mobile_bridge.py
echo.
pause
