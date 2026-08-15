@echo off
setlocal
rem ============================================================
rem watchdog.bat v2 (matches watch_sync.py v2.2)
rem Restarts the daemon when EITHER:
rem   1) PID in watch_sync.pid no longer exists (crashed/killed), OR
rem   2) liveness_<machine>.txt not updated for LIVE_MAX_AGE seconds
rem      (main loop blocked - PID alive but stuck)
rem Restart uses -S to skip sitecustomize hijack of unlink/rmtree
rem (root cause of the 2026-07 week-long silent hang).
rem All comments ASCII-only on purpose: safe in any codepage.
rem Place this file (or a shortcut) into shell:startup.
rem ============================================================
set "SYNC_DIR=C:\WorkBuddy\_sync"
set "PIDFILE=%SYNC_DIR%\watch_sync.pid"
set "PYEXE=%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe"
set "MACHINE=%COMPUTERNAME%"
set "LIVENESS=%SYNC_DIR%\liveness_%MACHINE%.txt"
set "LIVE_MAX_AGE=240"

:loop
if not exist "%PIDFILE%" goto start
set /p PID=<"%PIDFILE%"
tasklist /FI "PID eq %PID%" | find "%PID%" >nul
if errorlevel 1 goto start
if not exist "%LIVENESS%" goto wait
"%PYEXE%" -S -c "import os,sys,time; sys.exit(1 if time.time()-os.path.getmtime(sys.argv[1])>int(sys.argv[2]) else 0)" "%LIVENESS%" %LIVE_MAX_AGE%
if errorlevel 1 goto kill
goto wait

:kill
echo [%date% %time%] watchdog: PID %PID% alive but STUCK (liveness older than %LIVE_MAX_AGE%s), killing... >> "%SYNC_DIR%\watchdog.log"
taskkill /F /PID %PID% >nul 2>&1
if exist "%PIDFILE%" del /f /q "%PIDFILE%"
goto start

:start
echo [%date% %time%] watchdog: watch_sync not running, restarting with -S... >> "%SYNC_DIR%\watchdog.log"
if exist "%PIDFILE%" del /f /q "%PIDFILE%"
start "" /B "%PYEXE%" -S "%SYNC_DIR%\watch_sync.py"

:wait
timeout /t 30 /nobreak >nul
goto loop
