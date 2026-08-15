@echo off
REM ============================================
REM WorkBuddy cross-device sync - startup launcher
REM Put this file in shell:startup (Win+R -> shell:startup)
REM It launches watchdog.bat, which brings up watch_sync.py.
REM Watchdog auto-restarts the daemon within 30s if it crashes/dies.
REM Machine-independent path (%USERPROFILE%), no hardcoded username.
REM ============================================
start "" /B cmd /c "C:\WorkBuddy\_sync\watchdog.bat"
