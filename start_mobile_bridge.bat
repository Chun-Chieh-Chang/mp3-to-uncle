@echo off
setlocal
cd /d "%~dp0"

set "PY_EXE="
set "PY_ARG="

if exist ".venv\Scripts\python.exe" goto check_venv
goto try_314_local

:check_venv
".venv\Scripts\python.exe" -c "import flask, flask_cors, yt_dlp" >nul 2>nul
if errorlevel 1 goto try_314_local
set "PY_EXE=.venv\Scripts\python.exe"
goto run_bridge

:try_314_local
if not exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" goto try_py314
"%LOCALAPPDATA%\Programs\Python\Python314\python.exe" -c "import flask, flask_cors, yt_dlp" >nul 2>nul
if errorlevel 1 goto try_py314
set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
goto run_bridge

:try_py314
py -3.14 -c "import flask, flask_cors, yt_dlp" >nul 2>nul
if errorlevel 1 goto try_py313
set "PY_EXE=py"
set "PY_ARG=-3.14"
goto run_bridge

:try_py313
py -3.13 -c "import flask, flask_cors, yt_dlp" >nul 2>nul
if errorlevel 1 goto try_py312
set "PY_EXE=py"
set "PY_ARG=-3.13"
goto run_bridge

:try_py312
py -3.12 -c "import flask, flask_cors, yt_dlp" >nul 2>nul
if errorlevel 1 goto try_path_python
set "PY_EXE=py"
set "PY_ARG=-3.12"
goto run_bridge

:try_path_python
python -c "import flask, flask_cors, yt_dlp" >nul 2>nul
if errorlevel 1 goto no_python
set "PY_EXE=python"
goto run_bridge

:no_python
echo [AudioStudio] ERROR: Python with flask, flask-cors, yt-dlp was not found.
echo Please run: pip install -r requirements.txt
if not "%~1"=="--check" pause
exit /b 1

:run_bridge
if defined PY_ARG goto run_with_arg
echo [AudioStudio] Starting Mobile Bridge with "%PY_EXE%"...
"%PY_EXE%" mobile_bridge.py %*
goto done

:run_with_arg
echo [AudioStudio] Starting Mobile Bridge with %PY_EXE% %PY_ARG%...
%PY_EXE% %PY_ARG% mobile_bridge.py %*

:done
set "EXIT_CODE=%ERRORLEVEL%"
if not "%~1"=="--check" pause
exit /b %EXIT_CODE%
