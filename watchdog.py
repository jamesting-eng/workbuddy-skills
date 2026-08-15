#!/usr/bin/env python3
"""Watchdog for watch_sync.py (Python port of watchdog.bat).

Restarts the sync daemon when EITHER:
  1) the PID in watch_sync.pid no longer exists (crashed / killed / reboot), OR
  2) liveness_<machine>.txt has not been updated for LIVENESS_MAX_AGE seconds
     (main loop is hung while the PID still looks alive).

The daemon is (re)started with -S to skip sitecustomize hijacking of
unlink/rmtree on WPS junction paths — the root cause of a week-long silent
hang (see watch_sync.py v2.2 notes).

Run at logon (put a shortcut in shell:startup) or in a terminal:
    python watchdog.py
"""
import ctypes
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SYNC_DIR = Path(r"C:\WorkBuddy\_sync")
PID_FILE = SYNC_DIR / "watch_sync.pid"
DAEMON = SYNC_DIR / "watch_sync.py"
MACHINE = os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "unknown"
LIVENESS_FILE = SYNC_DIR / f"liveness_{MACHINE}.txt"
LIVENESS_MAX_AGE = 240   # seconds; must exceed watch_sync SYNC_TIMEOUT (180)
CHECK_INTERVAL = 30      # seconds
LOG_FILE = SYNC_DIR / "watchdog.log"

STILL_ACTIVE = 259


def log(msg: str) -> None:
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] watchdog: {msg}\n")
    except OSError:
        pass


def pid_alive(pid: int) -> bool:
    """Check a Windows PID without side effects (OpenProcess + GetExitCodeProcess)."""
    if pid <= 0:
        return False
    try:
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            code = ctypes.c_ulong()
            if not k32.GetExitCodeProcess(h, ctypes.byref(code)):
                return False
            return code.value == STILL_ACTIVE
        finally:
            k32.CloseHandle(h)
    except Exception:
        return False


def liveness_stale() -> bool:
    if not LIVENESS_FILE.exists():
        return False  # nothing to judge on yet
    try:
        return time.time() - LIVENESS_FILE.stat().st_mtime > LIVENESS_MAX_AGE
    except OSError:
        return False


def start_daemon() -> None:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen([sys.executable, "-S", str(DAEMON)],
                     creationflags=flags, close_fds=True)


def read_pid() -> int:
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip() or 0)
    except (OSError, ValueError):
        return 0


def main() -> None:
    log(f"started (pid={os.getpid()}, machine={MACHINE}, "
        f"liveness threshold={LIVENESS_MAX_AGE}s)")
    while True:
        pid = read_pid()
        if pid and pid_alive(pid):
            if liveness_stale():
                log(f"PID {pid} alive but STUCK (liveness older than "
                    f"{LIVENESS_MAX_AGE}s), killing...")
                subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                               capture_output=True)
                try:
                    PID_FILE.unlink()
                except OSError:
                    pass
                start_daemon()
            # else: healthy — do nothing
        else:
            log("daemon not running, starting with -S...")
            start_daemon()
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
