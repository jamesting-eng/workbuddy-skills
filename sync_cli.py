#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# sync_cli.py - single entry point for WorkBuddy cross-device sync (v6.1+)
#
# Why this exists: distribution channels (SkillHub) reject .bat files, and the
# package therefore ships with no launcher at all once the .bat wrappers are
# stripped. This one Python file replaces push.bat / pull.bat / start_sync.bat
# / one-click-sync.bat and additionally understands the v6 watchdog chain.
#
# Usage
# -----
#     python sync_cli.py                # interactive menu (or double-click it)
#     python sync_cli.py pull           # arriving at this PC: pull + verify
#     python sync_cli.py push           # leaving this PC: HANDOFF + push + verify
#     python sync_cli.py verify         # check both PCs share the same secret
#     python sync_cli.py status         # daemon / watchdog / liveness / HANDOFF
#     python sync_cli.py start          # bring up the watchdog chain
#     python sync_cli.py stop           # stop watchdog + daemon
#     python sync_cli.py sync           # pull, then ensure the chain is up
#     python sync_cli.py startup-install    # run the chain at Windows logon
#     python sync_cli.py startup-remove     # undo the above
#
# All console output is ASCII-only on purpose: Chinese text in launcher
# scripts has repeatedly been mangled by Windows codepage conversion and
# broke the scripts at parse time.
# ---------------------------------------------------------------------------

import os
import subprocess
import sys
import time
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
SYNC_DIR = Path(r"C:\WorkBuddy\_sync")
PY = sys.executable
PYTHONW = Path(PY).with_name("pythonw.exe")

DAEMON = "watch_sync.py"
WATCHDOG = "watchdog.py"

# v6 watchdog kills the daemon when liveness is older than this (see
# watchdog.bat / watchdog.py - both use 240s). Mirror it so `status` reports
# the same health the watchdog would act on.
LIVENESS_MAX_AGE = 240
# watch_sync.py refreshes its heartbeat every 5s; allow 3 misses.
HEARTBEAT_STALE_SEC = 20


# ---------------------------------------------------------------- helpers

def machine_id() -> str:
    return (os.environ.get("COMPUTERNAME")
            or os.environ.get("HOSTNAME")
            or "unknown").strip()


def pid_file() -> Path:
    return SYNC_DIR / "watch_sync.pid"


def liveness_file() -> Path:
    return SYNC_DIR / f"liveness_{machine_id()}.txt"


def heartbeat_file() -> Path:
    return SYNC_DIR / f"heartbeat_{machine_id()}.txt"


def file_age(path: Path):
    try:
        return time.time() - path.stat().st_mtime
    except OSError:
        return None


def read_pid():
    try:
        return int(pid_file().read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def pid_alive(pid) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        try:
            # Match on raw bytes: tasklist output is GBK-encoded on Chinese
            # Windows, and decoding it as UTF-8 raises UnicodeDecodeError.
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True, timeout=30,
            )
            return str(pid).encode() in (out.stdout or b"")
        except (OSError, subprocess.SubprocessError):
            return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def run(script_name: str, *args: str) -> int:
    """Run one of the bundled scripts with the current interpreter."""
    target = TOOL_DIR / script_name
    if not target.is_file():
        print(f"[x] missing script: {target}")
        return 1
    cmd = [PY, str(target), *args]
    print(f"[>] {' '.join(cmd)}")
    print("-" * 62)
    rc = subprocess.call(cmd, cwd=str(TOOL_DIR))
    print("-" * 62)
    return rc


def spawn(script_name: str, use_pythonw: bool = True) -> bool:
    """Launch a bundled script detached, in the background."""
    target = TOOL_DIR / script_name
    if not target.is_file():
        print(f"[x] missing script: {target}")
        return False
    launcher = PYTHONW if (use_pythonw and PYTHONW.is_file()) else Path(PY)
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    try:
        subprocess.Popen(
            [str(launcher), "-S", str(target)],
            cwd=str(TOOL_DIR),
            creationflags=flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        print(f"[x] failed to launch {script_name}: {exc}")
        return False
    return True


# --------------------------------------------------------------- commands

def cmd_start() -> int:
    """Bring up the v6 chain: watchdog.py supervises watch_sync.py.

    The watchdog is the correct entry point - it restarts the daemon within
    30s on crash and force-kills it when liveness goes stale (PID alive but
    main loop blocked). Only fall back to launching the daemon directly if
    the watchdog script is unavailable.
    """
    if (TOOL_DIR / WATCHDOG).is_file():
        if spawn(WATCHDOG):
            print(f"[+] {WATCHDOG} launched (it will bring up {DAEMON})")
            time.sleep(3)
            return cmd_status()
        return 1
    print(f"[!] {WATCHDOG} not found - starting {DAEMON} directly (no self-heal)")
    if spawn(DAEMON):
        print(f"[+] {DAEMON} launched (no watchdog: it will NOT restart on crash)")
        time.sleep(3)
        return cmd_status()
    return 1


def cmd_stop() -> int:
    pattern = "'*watch_sync.py*' -or $_.CommandLine -like '*watchdog.py*'"
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | "
        "Where-Object { $_.CommandLine -like " + pattern + " } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force; $_.ProcessId }"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, errors="replace", timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"[x] failed to query processes: {exc}")
        return 1
    pids = [ln.strip() for ln in (out.stdout or "").splitlines() if ln.strip().isdigit()]
    if not pids:
        print("[=] no running daemon/watchdog found")
    else:
        print(f"[+] stopped pid(s): {', '.join(pids)}")
    pf = pid_file()
    if pf.is_file():
        try:
            pf.unlink()
            print(f"[+] removed stale {pf.name}")
        except OSError:
            pass
    return 0


def cmd_status() -> int:
    print("=" * 62)
    print(f"  STATUS - {machine_id()}")
    print("=" * 62)
    print(f"tool dir  : {TOOL_DIR}")
    print(f"sync dir  : {SYNC_DIR}  (exists: {SYNC_DIR.is_dir()})")
    print(f"python    : {PY}")

    pid = read_pid()
    alive = pid_alive(pid)
    print(f"daemon    : {'RUNNING' if alive else 'NOT RUNNING'}"
          f"  (pid={pid or '-'})")

    age = file_age(liveness_file())
    if age is None:
        print(f"liveness  : MISSING  [{liveness_file().name}]")
    else:
        health = "FRESH" if age < LIVENESS_MAX_AGE else f"STALE (watchdog will kill it)"
        print(f"liveness  : {health}  ({int(age)}s old, threshold {LIVENESS_MAX_AGE}s)")

    hb_age = file_age(heartbeat_file())
    if hb_age is not None:
        state = "ALIVE" if hb_age < HEARTBEAT_STALE_SEC else f"STALE ({int(hb_age)}s)"
        print(f"heartbeat : {state}  [{heartbeat_file().name}]")

    handoff = SYNC_DIR / "HANDOFF.md"
    if handoff.is_file():
        ts = time.strftime("%Y-%m-%d %H:%M:%S",
                           time.localtime(handoff.stat().st_mtime))
        print(f"HANDOFF.md: updated {ts}")
    else:
        print("HANDOFF.md: MISSING")

    for name in ("watchdog.log", "watch_sync.log"):
        log = SYNC_DIR / name
        if log.is_file():
            try:
                lines = log.read_text(encoding="utf-8",
                                      errors="replace").splitlines()
            except OSError:
                continue
            if lines:
                print(f"  {name}| {lines[-1]}")
    return 0


def cmd_pull() -> int:
    print("=" * 62)
    print("  PULL - arriving at this PC")
    print("=" * 62)
    rc = run("sync_identity.py", "pull")
    rc2 = run("workspace_sync.py", "--verify")
    if rc == 0 and rc2 == 0:
        print()
        print("[+] Pull done. If the secret token still mismatches:")
        print("    1. Open the WPS cloud client")
        print(f"    2. Refresh {SYNC_DIR}")
        print("    3. Wait for the download to finish, then run this again")
    return rc or rc2


def cmd_push() -> int:
    print("=" * 62)
    print("  PUSH - leaving this PC")
    print("=" * 62)
    rc = run("workspace_sync.py", "--handoff")
    rc2 = run("sync_identity.py", "push")
    rc3 = run("workspace_sync.py", "--verify")
    if rc == 0 and rc2 == 0:
        print()
        print("[+] Push done. Confirm these appear in the WPS cloud folder:")
        print("    - HANDOFF.md")
        print("    - secret.txt")
    return rc or rc2 or rc3


def cmd_verify() -> int:
    return run("workspace_sync.py", "--verify")


def cmd_sync() -> int:
    print("=" * 62)
    print("  ONE-CLICK SYNC")
    print("=" * 62)
    rc = run("sync_identity.py", "pull")
    print()
    print("[2/2] Starting the sync daemon chain...")
    cmd_start()
    print()
    print("[+] Done. You can close this window.")
    return rc


def startup_shortcut_path() -> Path:
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return (Path(appdata) / "Microsoft" / "Windows" / "Start Menu"
            / "Programs" / "Startup" / "workbuddy-sync.cmd")


def cmd_startup_install() -> int:
    """Run the watchdog chain at Windows logon.

    v6 recommendation: the *watchdog* belongs in shell:startup, not the
    daemon - the watchdog is what survives crashes, logoff, and reboots.
    """
    target = startup_shortcut_path()
    watchdog = TOOL_DIR / WATCHDOG
    if watchdog.is_file():
        line = f'start "" /B "{Path(PY).as_posix()}" -S "{watchdog.as_posix()}"'
    else:
        daemon = TOOL_DIR / DAEMON
        line = f'start "" /B "{Path(PY).as_posix()}" -S "{daemon.as_posix()}"'
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("@echo off\r\n" + line + "\r\n", encoding="ascii")
    except OSError as exc:
        print(f"[x] failed to write startup entry: {exc}")
        return 1
    print(f"[+] startup entry created: {target}")
    print("    The sync chain now starts automatically at Windows logon.")
    return 0


def cmd_startup_remove() -> int:
    target = startup_shortcut_path()
    if not target.is_file():
        print("[=] no startup entry found")
        return 0
    try:
        target.unlink()
    except OSError as exc:
        print(f"[x] failed to remove startup entry: {exc}")
        return 1
    print(f"[+] startup entry removed: {target}")
    return 0


def cmd_menu() -> int:
    while True:
        pid = read_pid()
        running = pid_alive(pid)
        print()
        print("=" * 62)
        print("  WorkBuddy Cross-Device Sync")
        print("=" * 62)
        print(f"  machine : {machine_id()}")
        print(f"  daemon  : {'RUNNING' if running else 'NOT RUNNING'} (pid={pid or '-'})")
        print("-" * 62)
        print("  1) pull    - arriving at this PC (pull + verify)")
        print("  2) push    - leaving this PC (HANDOFF + push + verify)")
        print("  3) sync    - pull, then bring up the daemon chain")
        print("  4) verify  - check the secret token matches")
        print("  5) status  - daemon / liveness / HANDOFF / logs")
        print("  6) start   - launch watchdog + daemon")
        print("  7) stop    - stop watchdog + daemon")
        print("  8) startup-install - run the chain at Windows logon")
        print("  9) startup-remove  - undo startup entry")
        print("  0) exit")
        print("-" * 62)
        try:
            choice = input("  select [0-9]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if choice in ("0", "", "q", "quit", "exit"):
            return 0
        handlers = {
            "1": cmd_pull, "2": cmd_push, "3": cmd_sync, "4": cmd_verify,
            "5": cmd_status, "6": cmd_start, "7": cmd_stop,
            "8": cmd_startup_install, "9": cmd_startup_remove,
        }
        handler = handlers.get(choice)
        if handler is None:
            print("[!] unknown option, try again")
            continue
        handler()
        try:
            input("\n  press Enter to continue...")
        except (EOFError, KeyboardInterrupt):
            return 0
    return 0


COMMANDS = {
    "pull": cmd_pull,
    "push": cmd_push,
    "verify": cmd_verify,
    "status": cmd_status,
    "sync": cmd_sync,
    "start": cmd_start,
    "stop": cmd_stop,
    "startup-install": cmd_startup_install,
    "startup-remove": cmd_startup_remove,
    "menu": cmd_menu,
}


def main(argv) -> int:
    args = [a for a in argv[1:] if not a.startswith("-")]
    if not args:
        return cmd_menu()
    cmd = args[0].lower()
    handler = COMMANDS.get(cmd)
    if handler is None:
        print(f"[x] unknown command: {cmd}")
        print(f"    available: {', '.join(sorted(COMMANDS))}")
        return 1
    return handler()


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        print("\n[=] interrupted")
        sys.exit(130)
