"""
WorkBuddy 跨设备同步守护进程 v2.0 (单 leader 选举 / 根治副本冲突)
==================================================================
监听关键「源」文件，变了自动 push 到中转目录。
零依赖：纯 Python 标准库（轮询 mtime）。

v2.0 关键改进（根治 6895 个 -副本 冲突风暴）：
  - 【单 leader 选举】每台机器写自己的 heartbeat_<机器名>.txt（不同文件名，互不冲突）。
    只有「当前唯一活跃」的机器才允许 push，避免两台电脑同时写同一 WPS 路径 → 不再产生副本。
  - 【不再监听传输目录】只监听源：用户级 memory、各工作区 memory、以及交接文件
    (HANDOFF.md / secret.txt / AI_HANDOFF_GUIDE.md)。绝不监听整个 _sync 传输目录，
    根除「下载→再 push→再下载」回环。
  - 【机器无关】PYTHON_EXE 改用 sys.executable，家里/公司都能直接跑，不再硬编码 62588 路径。
  - 保留手动 push.bat 作为兜底（离开电脑前跑一次最稳）。

启动方式：
  python watch_sync.py            # 常驻守护（单 leader 模式下安全）
  python watch_sync.py --once     # 跑一次 sync 后退出
  python watch_sync.py --status   # 打印监听状态 + leader 状态
"""
import os
import sys
import time
import threading
import subprocess
from pathlib import Path
from datetime import datetime

# ─── 配置 ────────────────────────────────────────────────────────────────
SYNC_SCRIPT = Path(r"C:\WorkBuddy\_sync\sync_identity.py")
# 机器无关：用当前解释器自身，家里/公司都能跑
PYTHON_EXE = Path(sys.executable)

# 只监听「源」根，绝不监听 _sync 传输目录整体
WATCH_ROOTS = [
    Path(r"C:\WorkBuddy"),
    Path.home() / ".workbuddy",
]
# 交接文件显式监听（它们在 _sync 下，但属于要同步的内容，不是传输回环）
HANDOFF_FILES = [
    Path(r"C:\WorkBuddy\_sync\HANDOFF.md"),
    Path(r"C:\WorkBuddy\_sync\secret.txt"),
    Path(r"C:\WorkBuddy\_sync\AI_HANDOFF_GUIDE.md"),
]

SKIP_DIRS = {"node_modules", "__pycache__", ".git", ".venv", "envs", "venv",
             ".next", "dist", "build", ".claude", ".playwright-mcp",
             "$RECYCLE.BIN", "System Volume Information",
             "identity", "_sync"}   # ← v2.0 新增 _sync：不再扫传输目录
INTERESTED_EXTS = {".md", ".json", ".py", ".txt"}
SCAN_INTERVAL = 1.0       # 秒
DEBOUNCE_SEC = 1.0        # 秒
HEARTBEAT_SEC = 5         # 心跳写入间隔
STANDDOWN_SEC = 45        # 若另一台机器心跳在 45s 内，本机让出 leader，不 push
LOG_FILE = Path(r"C:\WorkBuddy\_sync\watch_sync.log")

# 机器标识：用计算机名（公司 DESKTOP-7QBVB48 / 家里 James Ting），每机独立心跳文件
MACHINE_ID = (os.environ.get("COMPUTERNAME")
              or os.environ.get("HOSTNAME")
              or "unknown").strip()
HEARTBEAT_FILE = Path(r"C:\WorkBuddy\_sync") / f"heartbeat_{MACHINE_ID}.txt"

# ─── 全局状态 ────────────────────────────────────────────────────────────
stop_event = threading.Event()
sync_lock = threading.Lock()
last_change_time = 0
sync_running = False
pending_refresh = False


def log(msg: str):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ─── 单 leader 选举 ──────────────────────────────────────────────────────

def write_heartbeat():
    """写自己的心跳文件（每 HEARTBEAT_SEC 一次）。文件名含机器名，互不冲突。"""
    try:
        HEARTBEAT_FILE.write_text(datetime.now().isoformat(), encoding="utf-8")
    except Exception:
        pass


def am_leader() -> bool:
    """是否当前唯一活跃机器。若发现其他机器的心跳在 STANDDOWN_SEC 内 → 让出。"""
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
    while not stop_event.is_set():
        write_heartbeat()
        time.sleep(HEARTBEAT_SEC)


# ─── 文件索引 ────────────────────────────────────────────────────────────

def _is_interested(path: Path) -> bool:
    name = path.name
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
            pass
    return index


def run_sync(force: bool = False):
    """执行一次 sync_identity.py push（仅本机为 leader 时调用）。"""
    global sync_running
    if sync_running and not force:
        return
    with sync_lock:
        if sync_running:
            return
        sync_running = True
    try:
        result = subprocess.run(
            [str(PYTHON_EXE), str(SYNC_SCRIPT), "push"],
            capture_output=True, text=True, timeout=120,
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
            if "推送" in line and "工作区" in line:
                try:
                    pushed += int(line.split("推送")[-1].strip().split()[0])
                except Exception:
                    pass
        log(f"🔄 auto-sync pushed={pushed} pulled={pulled} | leader={MACHINE_ID}")
        return "refresh_index"
    except subprocess.TimeoutExpired:
        log("⚠️  sync timeout (120s)")
    except Exception as e:
        log(f"❌ sync error: {e}")
    finally:
        sync_running = False
    return None


def watcher_loop():
    log(f"启动守护进程 PID={os.getpid()} machine={MACHINE_ID}")
    log(f"监听根: {[str(r) for r in WATCH_ROOTS]} + {len(HANDOFF_FILES)} 个交接文件")
    log(f"扫描间隔: {SCAN_INTERVAL}s | 防抖: {DEBOUNCE_SEC}s | leader 让出窗口: {STANDDOWN_SEC}s")

    last_index = build_file_index()
    log(f"初始扫描: {len(last_index)} 个文件")

    pending_thread = None
    while not stop_event.is_set():
        time.sleep(SCAN_INTERVAL)
        global pending_refresh
        if pending_refresh:
            last_index = build_file_index()
            pending_refresh = False
            continue
        new_index = build_file_index()
        changed = []
        for path, mtime in new_index.items():
            if path not in last_index or last_index[path] != mtime:
                changed.append(path)
        for path in last_index:
            if path not in new_index:
                changed.append(path)
        last_index = new_index

        if not changed:
            continue

        for p in changed[:5]:
            try:
                rel = p.relative_to(r"C:\WorkBuddy")
            except Exception:
                rel = p
            log(f"📝 变化: {rel}")
        if len(changed) > 5:
            log(f"   ...还有 {len(changed) - 5} 个文件")

        # 单 leader：若另一台机器活跃，本机让出，不 push（避免并发写 → 副本）
        if not am_leader():
            log("🕊  另一台机器活跃，本机让出 leader，跳过 push")
            # 重建基线，避免反复检测同一变化
            last_index = build_file_index()
            continue

        if pending_thread and pending_thread.is_alive():
            continue
        pending_thread = threading.Thread(target=_debounced_sync, daemon=True)
        pending_thread.start()


def _debounced_sync():
    global pending_refresh
    time.sleep(DEBOUNCE_SEC)
    if not stop_event.is_set():
        result = run_sync()
        if result == "refresh_index":
            pending_refresh = True


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="跑一次 sync 后退出")
    parser.add_argument("--status", action="store_true", help="打印监听状态 + leader 状态")
    args = parser.parse_args()

    if args.once:
        run_sync(force=True)
        return

    if args.status:
        idx = build_file_index()
        print(f"机器: {MACHINE_ID}")
        print(f"监听文件数: {len(idx)}")
        print(f"当前 leader: {'是' if am_leader() else '否（另一台机器活跃）'}")
        from collections import Counter
        roots = Counter(str(p.parent) for p in idx)
        for r, c in roots.most_common(10):
            print(f"  {c:4d}  {r}")
        return

    # 启动心跳线程（单 leader 选举）
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    log("=" * 60)
    log("WorkBuddy 跨设备同步守护进程 v2.0 (单 leader) 启动")
    log("=" * 60)
    try:
        watcher_loop()
    except KeyboardInterrupt:
        log("收到退出信号")
    finally:
        stop_event.set()


if __name__ == "__main__":
    main()
