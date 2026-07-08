@echo off
echo ================================================
echo  Push Sync (Company - Before Leaving)
echo ================================================
echo.

cd /d C://WorkBuddy//_sync

echo [1/3] Updating handoff...
python workspace_sync.py --handoff

echo.
echo [2/3] Verifying sync...
python workspace_sync.py --verify

echo.
echo [3/3] Confirm WPS cloud shows synced:
echo  - HANDOFF.md
echo  - secret.txt
echo.
pause
