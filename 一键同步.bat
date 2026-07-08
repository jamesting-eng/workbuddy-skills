@echo off
title WorkBuddy Sync
color 0B

echo.
echo ============================================================
echo           WorkBuddy Cross-PC Sync
echo ============================================================
echo.
echo [1/2] Pulling latest from cloud...
echo.
python "%~dp0sync_identity.py" pull
if errorlevel 1 goto :err

echo.
echo [2/2] Starting auto-sync watcher...
echo         (If already running, will skip)
echo.
start "" pythonw "%~dp0watch_sync.py"

goto :end

:err
echo.
echo ERROR: Sync failed! Check messages above.

:end
echo.
echo Done. You can close this window.
pause
