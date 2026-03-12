@echo off
:: ================================================================
::  Red Alert Monitor v4.1  —  install.bat
::  מתקין את התוכנה ל-C:\RedAlertIDF ומגדיר הפעלה עם Windows
:: ================================================================
set INSTALL_DIR=C:\RedAlertIDF
set TASK_NAME=RedAlertMonitor
title התקנת Red Alert Monitor → %INSTALL_DIR%

echo.
echo  =============================================
echo   Red Alert Monitor v4.1  —  התקנה
echo   יעד: %INSTALL_DIR%
echo  =============================================
echo.

:: ── דרוש הרשאות מנהל ─────────────────────────────────────────
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] נדרשות הרשאות מנהל.
    echo      לחץ ימני על install.bat ← "הפעל כמנהל מערכת"
    pause
    exit /b 1
)

:: ── צור תיקיית יעד ────────────────────────────────────────────
echo [1/4] יוצר תיקייה %INSTALL_DIR% ...
if not exist "%INSTALL_DIR%" (
    mkdir "%INSTALL_DIR%"
    echo   נוצרה: %INSTALL_DIR%
) else (
    echo   קיימת: %INSTALL_DIR%
)

:: ── העתק קבצים ────────────────────────────────────────────────
echo [2/4] מעתיק קבצים...

:: EXE (אם קיים)
if exist "%~dp0RedAlertMonitor.exe" (
    copy /Y "%~dp0RedAlertMonitor.exe" "%INSTALL_DIR%\RedAlertMonitor.exe" >nul
    echo   OK: RedAlertMonitor.exe
    set RUN_CMD="%INSTALL_DIR%\RedAlertMonitor.exe"
    set RUN_ARGS=
) else if exist "%INSTALL_DIR%\RedAlertMonitor.exe" (
    echo   OK: EXE קיים כבר ב-%INSTALL_DIR%
    set RUN_CMD="%INSTALL_DIR%\RedAlertMonitor.exe"
    set RUN_ARGS=
) else (
    echo   [i] EXE לא נמצא — משתמש ב-Python
    set RUN_CMD=wscript.exe
    set RUN_ARGS="%INSTALL_DIR%\launch.vbs"
)

:: VBS
if exist "%~dp0launch.vbs" (
    copy /Y "%~dp0launch.vbs" "%INSTALL_DIR%\launch.vbs" >nul
    echo   OK: launch.vbs
)

:: קוד מקור Python
if exist "%~dp0red_alert.py" (
    copy /Y "%~dp0red_alert.py" "%INSTALL_DIR%\red_alert.py" >nul
    echo   OK: red_alert.py
)

:: requirements
if exist "%~dp0requirements.txt" (
    copy /Y "%~dp0requirements.txt" "%INSTALL_DIR%\requirements.txt" >nul
    echo   OK: requirements.txt
)

:: ── Scheduled Task (עם הרשאות מנהל) ──────────────────────────
echo [3/4] מגדיר Scheduled Task ...

:: מחיקת ישן
schtasks /delete /f /tn "%TASK_NAME%" >nul 2>&1

:: כתוב XML לקובץ זמני
set XML_FILE=%TEMP%\redalert_task.xml

(
echo ^<?xml version="1.0" encoding="UTF-16"?^>
echo ^<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"^>
echo   ^<Triggers^>
echo     ^<LogonTrigger^>^<Enabled^>true^</Enabled^>^<Delay^>PT5S^</Delay^>^</LogonTrigger^>
echo   ^</Triggers^>
echo   ^<Principals^>
echo     ^<Principal id="Author"^>
echo       ^<LogonType^>InteractiveToken^</LogonType^>
echo       ^<RunLevel^>HighestAvailable^</RunLevel^>
echo     ^</Principal^>
echo   ^</Principals^>
echo   ^<Settings^>
echo     ^<MultipleInstancesPolicy^>IgnoreNew^</MultipleInstancesPolicy^>
echo     ^<ExecutionTimeLimit^>PT0S^</ExecutionTimeLimit^>
echo     ^<DisallowStartIfOnBatteries^>false^</DisallowStartIfOnBatteries^>
echo     ^<StopIfGoingOnBatteries^>false^</StopIfGoingOnBatteries^>
echo   ^</Settings^>
echo   ^<Actions^>
echo     ^<Exec^>
echo       ^<Command^>%RUN_CMD%^</Command^>
) > "%XML_FILE%"

if not "%RUN_ARGS%"=="" (
    echo       ^<Arguments^>%RUN_ARGS%^</Arguments^> >> "%XML_FILE%"
)

(
echo       ^<WorkingDirectory^>%INSTALL_DIR%^</WorkingDirectory^>
echo     ^</Exec^>
echo   ^</Actions^>
echo ^</Task^>
) >> "%XML_FILE%"

schtasks /create /f /tn "%TASK_NAME%" /xml "%XML_FILE%"
if %errorlevel%==0 (
    echo   OK: Task Scheduler ← %RUN_CMD%
) else (
    echo   [!] Task Scheduler נכשל — בדוק ידנית ב-taskschd.msc
)
del /f /q "%XML_FILE%" >nul 2>&1

:: ── Registry (גיבוי) ──────────────────────────────────────────
echo [4/4] מוסיף ל-Registry (גיבוי) ...
if "%RUN_ARGS%"=="" (
    reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "RedAlertMonitor" /t REG_SZ /d %RUN_CMD% /f >nul
) else (
    reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "RedAlertMonitor" /t REG_SZ /d "%RUN_CMD% %RUN_ARGS%" /f >nul
)
echo   OK: Registry

echo.
echo  =============================================
echo   ✅  ההתקנה הושלמה!
echo.
echo   נתיב:   %INSTALL_DIR%\RedAlertMonitor.exe
echo   Task:   %TASK_NAME%  (מופעל 5 שניות אחרי כניסה)
echo.
echo   כדי לאמת: פתח Task Scheduler → Task Scheduler Library
echo   וחפש "RedAlertMonitor"
echo  =============================================
echo.

set /p LAUNCH="הפעל עכשיו? (Y/N): "
if /i "%LAUNCH%"=="Y" (
    if exist "%INSTALL_DIR%\RedAlertMonitor.exe" (
        start "" "%INSTALL_DIR%\RedAlertMonitor.exe"
    ) else (
        start "" wscript.exe "%INSTALL_DIR%\launch.vbs"
    )
)
pause
