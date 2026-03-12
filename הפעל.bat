@echo off
title Red Alert Monitor v4.0

REM If the compiled EXE exists - run it directly (no Python needed, no .py visible)
if exist "%~dp0RedAlertMonitor.exe" goto run_exe

REM --- Fallback: run from Python source ---
set PYTHON_CMD=
py --version >nul 2>&1
if %errorlevel%==0 set PYTHON_CMD=py
if defined PYTHON_CMD goto found_python

python --version >nul 2>&1
if %errorlevel%==0 set PYTHON_CMD=python
if defined PYTHON_CMD goto found_python

echo ERROR: Python not found and RedAlertMonitor.exe is missing.
echo Run build_exe.bat to create the EXE, or install Python from:
echo https://www.python.org/downloads/
pause
exit /b 1

:found_python
echo Installing required packages...
%PYTHON_CMD% -m pip install --upgrade PyQt5 PyQtWebEngine requests >nul 2>&1

:run_py
%PYTHON_CMD% "%~dp0red_alert.py"
set APP_ERR=%ERRORLEVEL%
if %APP_ERR%==0 goto end
timeout /t 3 /nobreak >nul
goto run_py

:run_exe
"%~dp0RedAlertMonitor.exe"
set APP_ERR=%ERRORLEVEL%
if %APP_ERR%==0 goto end
timeout /t 3 /nobreak >nul
goto run_exe

:end
