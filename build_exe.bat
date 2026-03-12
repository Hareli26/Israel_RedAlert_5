@echo off
title Build EXE - Red Alert Monitor v4
set INSTALL_DIR=C:\RedAlertIDF

echo.
echo  =============================================
echo   Build EXE - Red Alert Monitor v4.1
echo   יוצר EXE ומתקין ל-C:\RedAlertIDF
echo  =============================================
echo.

REM Find Python
set PYTHON_CMD=
py --version >nul 2>&1
if %errorlevel%==0 set PYTHON_CMD=py
if defined PYTHON_CMD goto found_python

python --version >nul 2>&1
if %errorlevel%==0 set PYTHON_CMD=python
if defined PYTHON_CMD goto found_python

echo ERROR: Python not found.
pause
exit /b 1

:found_python
echo Python: %PYTHON_CMD%
echo.

REM Install build tools
echo [1/5] Installing PyInstaller and dependencies...
%PYTHON_CMD% -m pip install --upgrade pyinstaller PyQt5 PyQtWebEngine requests

REM Move to script directory
cd /d "%~dp0"

REM Run PyInstaller
echo [2/5] Running PyInstaller...
%PYTHON_CMD% -m PyInstaller --noconfirm --onefile --windowed --name "RedAlertMonitor" --add-data "requirements.txt;." --hidden-import PyQt5.sip --hidden-import PyQt5.QtWebEngineWidgets --hidden-import PyQt5.QtWebEngine --hidden-import PyQt5.QtWebEngineCore --collect-all PyQt5 red_alert.py

if %errorlevel% neq 0 (
    echo.
    echo [!] Build FAILED. Check errors above.
    pause
    exit /b 1
)

echo.
echo [3/5] Copying EXE to project folder...
if exist dist\RedAlertMonitor.exe (
    copy /Y dist\RedAlertMonitor.exe "%~dp0RedAlertMonitor.exe" >nul
    echo   OK: %~dp0RedAlertMonitor.exe
) else (
    echo [!] EXE not found in dist folder
    pause
    exit /b 1
)

echo [4/5] Installing to %INSTALL_DIR% ...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
copy /Y dist\RedAlertMonitor.exe "%INSTALL_DIR%\RedAlertMonitor.exe" >nul
copy /Y "%~dp0launch.vbs"        "%INSTALL_DIR%\launch.vbs"         >nul 2>&1
copy /Y "%~dp0red_alert.py"      "%INSTALL_DIR%\red_alert.py"       >nul 2>&1
echo   OK: %INSTALL_DIR%\RedAlertMonitor.exe

echo [5/5] Cleaning up temp build files...
if exist build  rmdir /s /q build
if exist dist   rmdir /s /q dist
if exist RedAlertMonitor.spec del /f /q RedAlertMonitor.spec

echo.
echo  =============================================
echo   Build complete!
echo.
echo   EXE: %INSTALL_DIR%\RedAlertMonitor.exe
echo   הפעל מהיר: לחץ פעמיים על RedAlertMonitor.exe
echo   ב: %INSTALL_DIR%
echo  =============================================
echo.
echo  כדי להגדיר הפעלה עם Windows:
echo  הפעל את %INSTALL_DIR%\RedAlertMonitor.exe
echo  פתח הגדרות (גלגל שיניים) וסמן "הפעל עם Windows"
echo.
pause
