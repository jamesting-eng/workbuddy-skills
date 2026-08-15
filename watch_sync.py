"""
WorkBuddy 跨设备同步守护进程 v2.2 (单 leader 选举 / 自愈 / 根治副本冲突 / 卡死自愈)
========================================================================
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

v2.1 关键改进（自愈，根治 7/7 静默死一周）：
  - 【进程级不退出】watcher 主循环外套 try/except，任何未捕获异常只记日志 + sleep 10s
    重建基线重进循环，进程永不退出（除非显式 stop / Ctrl-C）。
  - 【run_sync 自愈】连续失败计数；超时/报错不再致命，下次循环继续尝试；
    连续失败达到阈值（默认 3）自动重建基线 + 兜底 pull，避免卡在脏状态或单向僵死。
  - 【心跳线程保护】heartbeat_loop 包 try/except，单跳异常不影响主循环。
  - 【看门狗】watchdog.bat 通过 watch_sync.pid 检测进程存活，崩溃/被杀后 30s 内自动重启
    （开机自启 watchdog.bat 即获得「机器重启 / 进程被杀」级别的终极自愈）。
  - Windows 下 subprocess 用 CREATE_NO_WINDOW，避免后台弹黑窗。

v2.2 关键改进（根治 7/13 起的「进程活着但 blocked」卡死）：
  - 【根因：sitecustomize 劫持】sync_identity.py 在 WPS junction 路径上做 unlink/rmtree 时，
    被 WorkBuddy 的 sitecustomize.py 劫持成「外部回收站子进程且永不返回」→ 主进程卡死、
    还繁衍锁住 WPS 路径的孙进程，下次 sync 又卡同一把锁 → 永久超时/僵死。
  - 【自愈根因修复 1】看门狗(watchdog.bat)以 -S 启动本进程、run_sync 的 push 与
    _recover_after_failures 的 pull 子进程也都带 -S，跳过 sitecustomize 对
    unlink/rmtree 的劫持——所有文件删除恢复正常语义，从根消除 WPS 路径上的回收站死锁。
    （实测 self-re-exec 在 sitecustomize 改写 sys.executable 指向 WPS 路径的环境下会崩，
      故不自举，改由 watchdog 统一以 -S 拉起。）
  - 【主循环活性信号】每轮 scan 更新 liveness_<机器名>.txt（mtime）。
    看门狗据此判定「主循环是否卡死」——PID 在但 liveness 过期 = 卡死 → 强杀重启。
    （v2.1 的 watchdog 只看 PID 是否存活，检测不了 blocked，这是 7/13 后静默死一周的真因。）

启动方式：
  python watch_sync.py            # 常驻守护（单 leader + 自愈 + 卡死自愈）
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
PID_FILE = Path(r"C:\WorkBuddy\_sync\watch_sync.pid")

# 自愈参数
RESTART_DELAY = 10        # 主循环异常后等待重启秒数
SYNC_TIMEOUT = 180        # 单次 sync 子进程超时（秒）
MAX_CONSECUTIVE_FAILS = 3  # 连续失败达到此值触发兜底恢复（rebuild baseline + pull）
# v2.2：主循环活性信号过期阈值（秒）。看门狗据此判定主循环卡死。
# 必须 > SYNC_TIMEOUT + 余量，避免正常长耗时 sync 期间误杀。
LIVENESS_MAX_AGE = 240

# 机器标识：用计算机名（公司 DESKTOP-7QBVB48 / 家里 James Ting），每机独立心跳文件
MACHINE_ID = (os.environ.get("COMPUTERNAME")
              or os.environ.get("HOSTNAME")
              or "unknown").strip()
HEARTBEAT_FILE = Path(r"C:\WorkBuddy\_sync") / f"heartbeat_{MACHINE_ID}.txt"
# v2.2：主循环活性信号（与主循环驱动绑定，卡死即停写 → 看门狗可检测）
LIVENESS_FILE = HEARTBEAT_FILE.with_name(f"liveness_{MACHINE_ID}.txt")

# ─── 全局状态 ────────────────────────────────────────────────────────────
stop_event = threading.Event()
sync_lock = threading.Lock()
last_change_time = 0
sync_running = False
pending_refresh = False
baseline_index = {}            # v2.1：基线文件索引（全局，便于自愈重置）
consecutive_failures = 0       # v2.1：连续 sync 失败计数


def log(msg: str):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _win_no_window() -> int:
    """Windows 下返回 CREATE_NO_WINDOW 标志，避免后台弹黑窗；其他平台返回 0。"""
    if sys.platform == "win32":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


# ─── 单 leader 选举 ──────────────────────────────────────────────────────

def write_heartbeat():
    """写自己的心跳文件（每 HEARTBEAT_SEC 一次）。文件名含机器名，互不冲突。"""
    try:
        HEARTBEAT_FILE.write_text(datetime.now().isoformat(), encoding="utf-8")
    except Exception:
        pass


def touch_liveness():
    """v2.2：主循环每轮更新活性信号（mtime）。卡死即停写 → 看门狗可检测。"""
    try:
        LIVENESS_FILE.write_text(datetime.now().isoformat(), encoding="utf-8")
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
    # v2.1：包 try/except，单跳异常不影响主循环
    while not stop_event.is_set():
        try:
            write_heartbeat()
        except Exception as e:
            log(f"⚠️  heartbeat 写入异常（忽略）: {e!r}")
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
            # v2.1：walk 中途 IO 抖动只跳过该根，不冒泡
            pass
    return index


def run_sync(force: bool = False):
    """执行一次 sync_identity.py push（仅本机为 leader 时调用）。带自愈。"""
    global sync_running, consecutive_failures
    if sync_running and not force:
        return
    with sync_lock:
        if sync_running:
            return
        sync_running = True
    try:
        # v2.2：带 -S 跳过 sitecustomize，避免 WPS 路径上 unlink/rmtree 被劫持成
        # 永不返回的回收站子进程（这是 7/13 起进程 blocked 的卡死根因）。
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
            if "推送" in line and "工作区" in line:
                try:
                    pushed += int(line.split("推送")[-1].strip().split()[0])
                except Exception:
                    pass
        log(f"🔄 auto-sync pushed={pushed} pulled={pulled} | leader={MACHINE_ID}")
        consecutive_failures = 0   # v2.1：成功清零
        return "refresh_index"
    except subprocess.TimeoutExpired:
        consecutive_failures += 1
        log(f"⚠️  sync timeout ({SYNC_TIMEOUT}s) [连续失败 {consecutive_failures}]")
        if consecutive_failures >= MAX_CONSECUTIVE_FAILS:
            _recover_after_failures()
    except Exception as e:
        consecutive_failures += 1
        log(f"❌ sync error: {e} [连续失败 {consecutive_failures}]")
        if consecutive_failures >= MAX_CONSECUTIVE_FAILS:
            _recover_after_failures()
    finally:
        sync_running = False
    return None


def _recover_after_failures():
    """v2.1：连续失败达到阈值后的自愈恢复。重建基线 + 兜底 pull，避免脏状态/单向僵死。"""
    global consecutive_failures, baseline_index
    log("🔧 连续失败达到阈值，触发自愈恢复（重建基线 + 兜底 pull）")
    try:
        baseline_index = build_file_index()
        log(f"🔧 基线已重建：{len(baseline_index)} 个文件")
    except Exception as e:
        log(f"🔧 基线重建失败（忽略）: {e!r}")
    # 兜底 pull：保证不只在 push，单向卡死时能拉回
    try:
        # v2.2：pull 同样带 -S，避免 sitecustomize 劫持
        subprocess.run(
            [str(PYTHON_EXE), "-S", str(SYNC_SCRIPT), "pull"],
            capture_output=True, text=True, timeout=SYNC_TIMEOUT,
            creationflags=_win_no_window(),
        )
        log("🔧 兜底 pull 完成")
    except Exception as e:
        log(f"🔧 兜底 pull 也失败（忽略）: {e!r}")
    consecutive_failures = 0


def _debounced_sync():
    global pending_refresh
    time.sleep(DEBOUNCE_SEC)
    if not stop_event.is_set():
        result = run_sync()
        if result == "refresh_index":
            pending_refresh = True


def _watcher_inner():
    """v2.1：真正的监听循环体（可被外层自愈包裹）。"""
    global baseline_index, pending_refresh
    baseline_index = build_file_index()
    log(f"初始扫描: {len(baseline_index)} 个文件")

    pending_thread = None
    while not stop_event.is_set():
        touch_liveness()   # v2.2：每轮通告主循环活性（卡死即停写 → 看门狗可检测）
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
            log(f"📝 变化: {rel}")
        if len(changed) > 5:
            log(f"   ...还有 {len(changed) - 5} 个文件")

        # 单 leader：若另一台机器活跃，本机让出，不 push（避免并发写 → 副本）
        if not am_leader():
            log("🕊  另一台机器活跃，本机让出 leader，跳过 push")
            # 重建基线，避免反复检测同一变化
            baseline_index = build_file_index()
            continue

        if pending_thread and pending_thread.is_alive():
            continue
        pending_thread = threading.Thread(target=_debounced_sync, daemon=True)
        pending_thread.start()


def watcher_loop():
    """v2.1：自愈外层。任何未捕获异常只记日志 + 等待 + 重进，进程永不退出。"""
    log(f"启动守护进程 PID={os.getpid()} machine={MACHINE_ID}")
    log(f"监听根: {[str(r) for r in WATCH_ROOTS]} + {len(HANDOFF_FILES)} 个交接文件")
    log(f"扫描间隔: {SCAN_INTERVAL}s | 防抖: {DEBOUNCE_SEC}s | leader 让出窗口: {STANDDOWN_SEC}s")
    log(f"自愈: 异常重启 {RESTART_DELAY}s | 连续失败阈值 {MAX_CONSECUTIVE_FAILS} | 超时 {SYNC_TIMEOUT}s")
    log(f"卡死自愈: liveness 阈值 {LIVENESS_MAX_AGE}s（看门狗据此强杀 blocked 进程）")

    while not stop_event.is_set():
        try:
            _watcher_inner()
        except Exception as e:
            log(f"❌ 守护循环异常（自愈中，{RESTART_DELAY}s 后重启）: {e!r}")
            # 清掉可能脏掉的基线，下次重进会重建
            try:
                baseline_index = build_file_index()
            except Exception:
                pass
            time.sleep(RESTART_DELAY)
            continue
        break  # 正常结束（stop_event 被设置）


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
    # 注意：本进程由 watchdog.bat 以 -S 拉起（统一跳过 sitecustomize 劫持）。
    # 不在 main 内自举 -S：实测在 sitecustomize 改写 sys.executable 指向 WPS 路径的
    # 环境下，os.execv 自举会崩溃；且核心修复已由 watchdog(-S 启动) + run_sync(-S spawn)
    # 覆盖。
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
        print(f"连续失败计数: {consecutive_failures}/{MAX_CONSECUTIVE_FAILS}")
        print(f"liveness 文件: {LIVENESS_FILE} (阈值 {LIVENESS_MAX_AGE}s)")
        from collections import Counter
        roots = Counter(str(p.parent) for p in idx)
        for r, c in roots.most_common(10):
            print(f"  {c:4d}  {r}")
        return

    # 启动心跳线程（单 leader 选举）
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    log("=" * 60)
    log("WorkBuddy 跨设备同步守护进程 v2.2 (单 leader + 自愈 + 卡死自愈) 启动")
    log("=" * 60)
    write_pid()
    try:
        watcher_loop()
    except KeyboardInterrupt:
        log("收到退出信号")
    finally:
        stop_event.set()
        cleanup_pid()
        log("守护进程已退出")


if __name__ == "__main__":
    main()
