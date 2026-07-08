@echo off
REM ============================================
REM WorkBuddy 跨设备同步守护进程 - 启动脚本
REM 开机自启：把这个 .bat 放到启动文件夹
REM Win+R -> shell:startup -> 粘贴此文件
REM ============================================

REM 静默启动 watch_sync.py（无窗口弹出，机器无关路径）
start "" /B "%USERPROFILE%\.workbuddyinaries\pythonersions.13.12\python.exe" "C:\WorkBuddy\_sync\watch_sync.py"
