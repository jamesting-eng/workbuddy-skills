"""
WorkBuddy cross-device sync daemon v2.2 (single-leader election / self-healing / root fix for copy conflicts / stall self-healing)
========================================================================
Watches key "source" files and auto-pushes to the relay directory when they change.
Zero dependencies: pure Python standard library (mtime polling).

v2.0 key improvements (root fix for the 6,895-file WPS "-copy" conflict storm):
  - [Single-leader election] Each machine writes its own heartbeat_<machine>.txt
    (different file names, no conflicts). Only the "currently sole active" machine
    may push, preventing two computers from writing the same WPS path simultaneously
    → no more conflict copies.
  - [No longer watching the relay directory] Only sources are watched: user-level
    memory, each workspace's memory, and the handoff files (HANDOFF.md / secret.txt /
    AI_HANDOFF_GUIDE.md). The _sync relay directory is never watched as a whole,
    eradicating the "download → re-push → re-download" loop.
  - [Machine-independent] PYTHON_EXE now uses sys.executable, so it runs directly
    at home and at the office; the hardcoded 62588 path is gone.
  - Manual push.bat kept as a fallback (running it once before leaving is the most reliable).

v2.1 key improvements (self-healing; root fix for the silent week-long death on 7/7):
  - [Process never exits] The watcher main loop is wrapped in try/except; any uncaught
    exception is only logged + sleep 10s, the baseline is rebuilt and the loop re-entered.
    The process never exits (except explicit stop / Ctrl-C).
  - [run_sync self-healing] Consecutive-failure counter; timeouts/errors are no longer
    fatal — the next loop retries. When consecutive failures reach the threshold
    (default 3), the baseline is rebuilt + a fallback pull runs, avoiding getting stuck
    in a dirty state or a one-way deadlock.
  - [Heartbeat thread protection] heartbeat_loop is wrapped in try/except; one failed
    beat does not affect the main loop.
  - [Watchdog] watchdog.bat uses watch_sync.pid to check process liveness and restarts
    within 30s after a crash/kill (autostarting watchdog.bat at boot gives the ultimate
    self-healing against "machine reboot / process killed").
  - On Windows, subprocess uses CREATE_NO_WINDOW to avoid black console windows popping up.

v2.2 key improvements (root fix for the "process alive but blocked" stall since 7/13):
  - [Root cause: sitecustomize hijacking] When sync_identity.py does unlink/rmtree on WPS
    junction paths, WorkBuddy's sitecustomize.py hijacks it into an "external recycle-bin
    subprocess that never returns" → the main process stalls and spawns grandchild
    processes holding locks on WPS paths; the next sync stalls on the same lock →
    permanent timeout/deadlock.
  - [Self-healing root fix 1] The watchdog (watchdog.bat) starts this process with -S,
    and run_sync's push plus _recover_after_failures' pull subprocesses also use -S,
    skipping sitecustomize's hijacking of unlink/rmtree — all file deletions regain
    normal semantics, eliminating the recycle-bin deadlock on WPS paths at the root.
    (In practice self-re-exec crashes in environments where sitecustomize rewrites
      sys.executable to a WPS path, so no self-re-exec; the watchdog starts everything with -S.)
  - [Main-loop liveness signal] Each scan round updates liveness_<machine>.txt (mtime).
    The watchdog uses it to decide whether the main loop is stalled — PID alive but
    liveness expired = stalled → force kill and restart.
    (The v2.1 watchdog only checked PID liveness and could not detect "blocked" —
      the real cause of the silent week-long death after 7/13.)

Startup:
  python watch_sync.py            # resident daemon (single leader + self-healing + stall self-healing)
  python watch_sync.py --once     # run one sync then exit
  python watch_sync.py --status   # print watch status + leader status
"""

import os
import sys
import time
import threading
import subprocess
from pathlib import Path
from datetime import datetime

# ─── Configuration ────────────────────────────────────────────────────────────
SYNC_SCRIPT = Path(r"C:\WorkBuddy\_sync\sync_identity.py")
# Machine-independent: use the current interpreter itself; runs at home and at the office
PYTHON_EXE = Path(sys.executable)

# Only watch "source" roots; never watch the _sync relay directory as a whole
WATCH_ROOTS = [
    Path(r"C:\WorkBuddy"),
    Path.home() / ".workbuddy",
]
# Handoff files watched explicitly (they live under _sync but are content to sync, not relay loops)
HANDOFF_FILES = [
    Path(r"C:\WorkBuddy\_sync\HANDOFF.md"),
    Path(r"C:\WorkBuddy\_sync\secret.txt"),
    Path(r"C:\WorkBuddy\_sync\AI_HANDOFF_GUIDE.md"),
]

SKIP_DIRS = {"node_modules", "__pycache__", ".git", ".venv", "envs", "venv",
             ".next", "dist", "build", ".claude", ".playwright-mcp",
             "$RECYCLE.BIN", "System Volume Information",
             "identity", "_sync"}   # ← v2.0 adds _sync: the relay directory is no longer scanned
INTERESTED_EXTS = {".md", ".json", ".py", ".txt"}
SCAN_INTERVAL = 1.0       # seconds
DEBOUNCE_SEC = 1.0        # seconds
HEARTBEAT_SEC = 5         # heartbeat write interval
STANDDOWN_SEC = 45        # if another machine's heartbeat is within 45s, this machine yields leadership and does not push
LOG_FILE = Path(r"C:\WorkBuddy\_sync\watch_sync.log")
PID_FILE = Path(r"C:\WorkBuddy\_sync\watch_sync.pid")

# Self-healing parameters
RESTART_DELAY = 10        # seconds to wait before restarting after a main-loop exception
SYNC_TIMEOUT = 180        # per-sync subprocess timeout (seconds)
MAX_CONSECUTIVE_FAILS = 3  # consecutive-failure threshold that triggers fallback recovery (rebuild baseline + pull)
# v2.2: main-loop liveness signal expiry threshold (seconds). The watchdog uses it to detect a stalled main loop.
# Must be > SYNC_TIMEOUT + margin to avoid false kills during legitimately long syncs.
LIVENESS_MAX_AGE = 240

# Machine identity: the computer name (office DESKTOP-7QBVB48 / home James Ting); each machine gets its own heartbeat file
MACHINE_ID = (os.environ.get("COMPUTERNAME")
              or os.environ.get("HOSTNAME")
              or "unknown").strip()
HEARTBEAT_FILE = Path(r"C:\WorkBuddy\_sync") / f"heartbeat_{MACHINE_ID}.txt"
# v2.2: main-loop liveness signal (tied to the main loop; stops being written when stalled → watchdog can detect)
LIVENESS_FILE = HEARTBEAT_FILE.with_name(f"liveness_{MACHINE_ID}.txt")

# ─── Global state ─────────────────────────────────────────────────────────────
stop_event = threading.Event()
sync_lock = threading.Lock()
last_change_time = 0
sync_running = False
pending_refresh = False
baseline_index = {}            # v2.1: baseline file index (global, easy to reset for self-healing)
consecutive_failures = 0       # v2.1: consecutive sync failure counter


def log(msg: str):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _win_no_window() -> int:
    """On Windows return the CREATE_NO_WINDOW flag so no black console window pops up in the background; return 0 on other platforms."""
    if sys.platform == "win32":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


# ─── Single-leader election ───────────────────────────────────────────────────

def write_heartbeat():
    """Write this machine's heartbeat file (every HEARTBEAT_SEC). File name includes the machine name, so no conflicts."""
    try:
        HEARTBEAT_FILE.write_text(datetime.now().isoformat(), encoding="utf-8")
    except Exception:
        pass


def touch_liveness():
    """v2.2: refresh the liveness signal each main-loop round (mtime). Stops being written when stalled → watchdog can detect."""
    try:
        LIVENESS_FILE.write_text(datetime.now().isoformat(), encoding="utf-8")
    except Exception:
        pass


def am_leader() -> bool:
    """Whether this is the currently sole active machine. If another machine's heartbeat is within STANDDOWN_SEC → yield."""
    now = time.time()
    sync_dir = Path(r"C:\WorkBuddy\_sync")
    if not sync_dir.exists():
        return True
    for f in sync_dir.glob("heartbeat_*.txt"):
        if f == HEARTBEAT_FILE:
            continue
        try:
            age = now - f.stat().st_mtime
            if age < STANDDOWN_SEC:
                return False
        except OSError:
            pass
    return True


def heartbeat_loop():
    # v2.1: wrapped in try/except so one failed beat does not affect the main loop
    while not stop_event.is_set():
        try:
            write_heartbeat()
        except Exception as e:
            log(f"⚠️  heartbeat write error (ignored): {e!r}")
        time.sleep(HEARTBEAT_SEC)


# ─── File index ───────────────────────────────────────────────────────────────

def _is_interested(path: Path) -> bool:
    name = path.name
    # NOTE: "公司电脑操作清单.md" is a real synced file name ("company computer
    # operations checklist") — functional literal, do NOT translate.
    if name in {"HANDOFF.md", "AI_HANDOFF_GUIDE.md", "secret.txt",
                "公司电脑操作清单.md"}:
        return True
    if name in {"MEMORY.md", "STATUS.md", "DAILY_STATUS.md", "MORNING_BRIEF.md",
                "HOME_WRAPUP.md", "SOUL.md", "IDENTITY.md", "USER.md",
                "workspace-state.json"}:
        return True
    parts = path.parts
    if "memory" in parts and path.suffix.lower() == ".md":
        return True
    return False


def build_file_index() -> dict:
    index = {}
    roots = list(WATCH_ROOTS) + HANDOFF_FILES
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            try:
                index[root] = root.stat().st_mtime
            except OSError:
                pass
            continue
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
                for fname in filenames:
                    if not any(fname.lower().endswith(e) for e in INTERESTED_EXTS):
                        continue
                    fpath = Path(dirpath) / fname
                    if not _is_interested(fpath):
                        continue
                    try:
                        index[fpath] = fpath.stat().st_mtime
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            # v2.1: transient IO errors during walk only skip that root, no bubbling up
            pass
    return index


def run_sync(force: bool = False):
    """Run one sync_identity.py push (only called when this machine is leader). With self-healing."""
    global sync_running, consecutive_failures
    if sync_running and not force:
        return
    with sync_lock:
        if sync_running:
            return
        sync_running = True
    try:
        # v2.2: use -S to skip sitecustomize, avoiding unlink/rmtree on WPS paths being
        # hijacked into a never-returning recycle-bin subprocess (the root cause of the
        # process being blocked since 7/13).
        result = subprocess.run(
            [str(PYTHON_EXE), "-S", str(SYNC_SCRIPT), "push"],
            capture_output=True, text=True, timeout=SYNC_TIMEOUT,
            creationflags=_win_no_window(),
        )
        pushed = pulled = 0
        for line in result.stdout.splitlines():
            if "pushed:" in line and "files" in line.lower():
                try:
                    pushed += int(line.split("pushed:")[-1].strip().rstrip(".").split()[0])
                except Exception:
                    pass
            if "pulled:" in line and "files" in line.lower():
                try:
                    pulled += int(line.split("pulled:")[-1].strip().rstrip(".").split()[0])
                except Exception:
                    pass
            # NOTE: the Chinese markers below are INTENTIONAL — they parse the Chinese
            # per-workspace status lines printed by sync_identity.py's
            # sync_workspace_memories() (工作区 = "workspace", 推送 = "pushed").
            # Output-format contract between the two scripts; do NOT translate.
            if "推送" in line and "工作区" in line:
                try:
                    pushed += int(line.split("推送")[-1].strip().split()[0])
                except Exception:
                    pass
        log(f"🔄 auto-sync pushed={pushed} pulled={pulled} | leader={MACHINE_ID}")
        consecutive_failures = 0   # v2.1: reset on success
        return "refresh_index"
    except subprocess.TimeoutExpired:
        consecutive_failures += 1
        log(f"⚠️  sync timeout ({SYNC_TIMEOUT}s) [consecutive failures: {consecutive_failures}]")
        if consecutive_failures >= MAX_CONSECUTIVE_FAILS:
            _recover_after_failures()
    except Exception as e:
        consecutive_failures += 1
        log(f"❌ sync error: {e} [consecutive failures: {consecutive_failures}]")
        if consecutive_failures >= MAX_CONSECUTIVE_FAILS:
            _recover_after_failures()
    finally:
        sync_running = False
    return None


def _recover_after_failures():
    """v2.1: self-healing recovery after consecutive failures reach the threshold. Rebuilds the baseline + runs a fallback pull, avoiding a dirty state / one-way deadlock."""
    global consecutive_failures, baseline_index
    log("🔧 Consecutive failures reached the threshold; triggering self-healing recovery (rebuild baseline + fallback pull)")
    try:
        baseline_index = build_file_index()
        log(f"🔧 Baseline rebuilt: {len(baseline_index)} files")
    except Exception as e:
        log(f"🔧 Baseline rebuild failed (ignored): {e!r}")
    # Fallback pull: make sure we don't only push; can pull back when one-way stuck
    try:
        # v2.2: the pull also uses -S to avoid sitecustomize hijacking
        subprocess.run(
            [str(PYTHON_EXE), "-S", str(SYNC_SCRIPT), "pull"],
            capture_output=True, text=True, timeout=SYNC_TIMEOUT,
            creationflags=_win_no_window(),
        )
        log("🔧 Fallback pull finished")
    except Exception as e:
        log(f"🔧 Fallback pull also failed (ignored): {e!r}")
    consecutive_failures = 0


def _debounced_sync():
    global pending_refresh
    time.sleep(DEBOUNCE_SEC)
    if not stop_event.is_set():
        result = run_sync()
        if result == "refresh_index":
            pending_refresh = True


def _watcher_inner():
    """v2.1: the actual watch-loop body (wrapped by the outer self-healing layer)."""
    global baseline_index, pending_refresh
    baseline_index = build_file_index()
    log(f"Initial scan: {len(baseline_index)} files")

    pending_thread = None
    while not stop_event.is_set():
        touch_liveness()   # v2.2: announce main-loop liveness each round (stops when stalled → watchdog can detect)
        time.sleep(SCAN_INTERVAL)
        if pending_refresh:
            baseline_index = build_file_index()
            pending_refresh = False
            continue
        new_index = build_file_index()
        changed = []
        for path, mtime in new_index.items():
            if path not in baseline_index or baseline_index[path] != mtime:
                changed.append(path)
        for path in baseline_index:
            if path not in new_index:
                changed.append(path)
        baseline_index = new_index

        if not changed:
            continue

        for p in changed[:5]:
            try:
                rel = p.relative_to(r"C:\WorkBuddy")
            except Exception:
                rel = p
            log(f"📝 Changed: {rel}")
        if len(changed) > 5:
            log(f"   ...and {len(changed) - 5} more files")

        # Single leader: if the other machine is active, this machine yields and does not push (avoids concurrent writes → conflict copies)
        if not am_leader():
            log("🕊  Another machine is active; this machine yields leadership and skips push")
            # Rebuild the baseline to avoid re-detecting the same change repeatedly
            baseline_index = build_file_index()
            continue

        if pending_thread and pending_thread.is_alive():
            continue
        pending_thread = threading.Thread(target=_debounced_sync, daemon=True)
        pending_thread.start()


def watcher_loop():
    """v2.1: self-healing outer layer. Any uncaught exception is only logged + wait + re-enter; the process never exits."""
    log(f"Daemon started PID={os.getpid()} machine={MACHINE_ID}")
    log(f"Watch roots: {[str(r) for r in WATCH_ROOTS]} + {len(HANDOFF_FILES)} handoff files")
    log(f"Scan interval: {SCAN_INTERVAL}s | debounce: {DEBOUNCE_SEC}s | leader yield window: {STANDDOWN_SEC}s")
    log(f"Self-healing: restart after {RESTART_DELAY}s | consecutive-failure threshold {MAX_CONSECUTIVE_FAILS} | timeout {SYNC_TIMEOUT}s")
    log(f"Stall self-healing: liveness threshold {LIVENESS_MAX_AGE}s (the watchdog force-kills blocked processes based on it)")

    while not stop_event.is_set():
        try:
            _watcher_inner()
        except Exception as e:
            log(f"❌ Watch loop exception (self-healing, restarting in {RESTART_DELAY}s): {e!r}")
            # Clear a possibly-dirty baseline; the next re-entry rebuilds it
            try:
                baseline_index = build_file_index()
            except Exception:
                pass
            time.sleep(RESTART_DELAY)
            continue
        break  # normal end (stop_event was set)


def write_pid():
    try:
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass


def cleanup_pid():
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
    except Exception:
        pass


def main():
    # NOTE: this process is started by watchdog.bat with -S (uniformly skips the sitecustomize hijack).
    # No -S re-exec inside main: in practice os.execv re-exec crashes in environments where
    # sitecustomize rewrites sys.executable to a WPS path; and the core fix is already covered
    # by watchdog (-S start) + run_sync (-S spawn).
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="run one sync then exit")
    parser.add_argument("--status", action="store_true", help="print watch status + leader status")
    args = parser.parse_args()

    if args.once:
        run_sync(force=True)
        return

    if args.status:
        idx = build_file_index()
        print(f"Machine: {MACHINE_ID}")
        print(f"Watched files: {len(idx)}")
        print(f"Current leader: {'yes' if am_leader() else 'no (another machine is active)'}")
        print(f"Consecutive failures: {consecutive_failures}/{MAX_CONSECUTIVE_FAILS}")
        print(f"liveness file: {LIVENESS_FILE} (threshold {LIVENESS_MAX_AGE}s)")
        from collections import Counter
        roots = Counter(str(p.parent) for p in idx)
        for r, c in roots.most_common(10):
            print(f"  {c:4d}  {r}")
        return

    # Start the heartbeat thread (single-leader election)
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    log("=" * 60)
    log("WorkBuddy cross-device sync daemon v2.2 (single leader + self-healing + stall self-healing) started")
    log("=" * 60)
    write_pid()
    try:
        watcher_loop()
    except KeyboardInterrupt:
        log("Exit signal received")
    finally:
        stop_event.set()
        cleanup_pid()
        log("Daemon exited")


if __name__ == "__main__":
    main()
