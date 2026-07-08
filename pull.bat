@echo off
echo ================================================
echo  Pull Sync (Home - After Arriving)
echo ================================================
echo.

cd /d C://WorkBuddy//_sync

echo [1/2] Verifying sync status...
python workspace_sync.py --verify

echo.
echo [2/2] If secret mismatch:
echo  1. Open WPS cloud client
echo  2. Refresh C://WorkBuddy// folder
echo  3. Wait for download complete
echo  4. Run this script again
echo.
pause
