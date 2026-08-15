#!/usr/bin/env python3
"""
WorkBuddy 跨设备身份 & 记忆同步脚本 v3.4
=============================================
通过 C:\\WorkBuddy\\_sync\\identity\\ 中转，实现跨设备同步。

v3.5 (2026-07-09):
  - [增强] 推送前清扫范围扩大到整个 _sync 树 + 各工作区 .workbuddy/memory/
    （根治 7/6 冲突风暴遗留的 1.1 万副本，并阻止将来垃圾上传到云）
  - [新增] 同步 find_junk.py（垃圾扫描器）/ clean_junk.py（垃圾清理器）到双端
  - [修复] .bat 文件改用 GBK 编码（修复 Windows CMD 乱码）

v3.6 (2026-08-02):
  - 【根治 MEMORY.md 跨工作区互覆污染】collect/distribute 仅允许 YYYY-MM-DD.md
    每日日志进入扁平用户级 memory/ 命名空间；项目身份文件(MEMORY.md/STATUS.md/
    DAILY_STATUS.md/HOME_WRAPUP.md/MORNING_BRIEF.md)按名同，压平会 mtime 较新者胜出
    互相覆盖并扇回所有工作区（7/24、7/30 两次事故）。修复后项目记忆不再被合并/扇出。

v3.4 (2026-07-08):
  - [修复] 自动清理 WPS 云盘冲突副本文件 (-副本)
  - [修复] 同步时跳过所有含"副本"的文件（防止同步风暴）

v3.3 (2026-07-06):
  - 同步守护进程脚本本身：watch_sync.py / start_sync.bat / AI_HANDOFF_GUIDE.md
    两台电脑自动共享守护进程和文档，避免配置漂移
  - 用户级 SOUL.md / USER.md 注入跨设备同步铁律

v3.2 (2026-07-06):
  - 【根治WPS云盘失效】把 HANDOFF.md 加入同步清单，走中转目录而非 WPS 云盘
  - _sync/HANDOFF.md 仍然由 workspace_sync.py 生成机器区、AI 手写
  - 但跨设备流转改走 _sync/identity/HANDOFF.md 中转

v3.1 (2026-06-19):
  - find_workspaces() 支持多工作区路径（公司/家里可能不同）
  - 自动探测：WORKSPACE_BASE、~/.workbuddy/ 旁的工作区目录、当前工作区

v3.0 (2026-06-19):
  - 用户级 memory/ 作为「唯一权威来源」，distribute 到所有本地工作区
  - pull 时自动将用户级记忆分发到各工作区 .workbuddy/memory/
  - push 时反向收集各工作区记忆合并到用户级 memory/

v2.0 (2026-06-18):
  - 同步各工作区的 .workbuddy/memory/ 到中转目录

用法:
  python sync_identity.py              # 双向同步 + 收集 + 分发
  python sync_identity.py push        # 强制推送（离开电脑前执行）
  python sync_identity.py pull        # 强制拉取 + 分发（到新电脑后执行）
"""

import json
import re
import shutil
import sys
from pathlib import Path

HOME = Path.home()
LOCAL = HOME / ".workbuddy"
SYNC = Path(r"C:\WorkBuddy\_sync\identity")
# HANDOFF.md 路径（与 _sync/identity/ 中转目录并列）
HANDOFF_LOCAL = Path(r"C:\WorkBuddy\_sync\HANDOFF.md")
HANDOFF_REMOTE = SYNC / "HANDOFF.md"

# 跳过 WPS 云盘冲突副本文件（防止同步风暴）
SKIP_PATTERNS = {"-副本", "副本"}

# 仅每日日志（YYYY-MM-DD.md）允许进入扁平用户级 memory/ 命名空间（v3.6）
_DAILY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")

# 工作区根路径（支持多个，公司/家里可能不同）
# 脚本会自动探测，此处为默认值
DEFAULT_WORKSPACE_BASES = [
    Path(r"C:\WorkBuddy"),                          # 公司电脑 & 家里经过配置的路径
    HOME / "WorkBuddy",                             # 家里默认路径
]


def detect_workspace_bases() -> list[Path]:
    """自动探测可能的工作区根路径列表。"""
    bases = []

    # 1. 从 workspace-state.json 读取最近使用的工作区路径
    state_file = LOCAL / "workspace-state.json"
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            # 尝试从 recentWorkspaces 字段提取路径
            for key in ("recentWorkspaces", "workspaces", "lastWorkspace"):
                if key in state and state[key]:
                    raw = state[key]
                    if isinstance(raw, str):
                        p = Path(raw)
                        if p.parent.exists():
                            bases.append(p.parent)
                    elif isinstance(raw, list):
                        for item in raw:
                            p = Path(item)
                            if p.exists() or p.parent.exists():
                                bases.append(p if p.is_dir() else p.parent)
        except Exception:
            pass

    # 2. 加入默认路径（去重）
    for b in DEFAULT_WORKSPACE_BASES:
        if b not in bases:
            bases.append(b)

    # 3. 过滤掉不存在的
    return [b for b in bases if b.exists()]


def find_workspaces(bases: list[Path] | None = None) -> list[Path]:
    """扫描所有工作区根路径，返回含 .workbuddy 目录的工作区列表（按名字去重）。"""
    if bases is None:
        bases = detect_workspace_bases()
    workspaces = []
    seen_names = set()
    for base in bases:
        if not base.exists():
            continue
        for child in sorted(base.iterdir()):
            if not child.is_dir():
                continue
            if child.name.startswith("."):
                continue
            wb_dir = child / ".workbuddy"
            if wb_dir.exists() and child.name not in seen_names:
                workspaces.append(child)
                seen_names.add(child.name)
    return workspaces


# ─── 文件同步工具 ─────────────────────────────────────────────────────────

def is_skip_file(name: str) -> bool:
    """检查文件名是否应该跳过（WPS冲突副本等）。"""
    for pat in SKIP_PATTERNS:
        if pat in name:
            return True
    return False


def is_daily_log(name: str) -> bool:
    """仅允许 YYYY-MM-DD.md 形式的每日日志进入扁平用户级 memory/ 命名空间。

    v3.6 (2026-08-02): 修复 MEMORY.md 跨工作区互覆污染事故根因。
    项目级身份文件（MEMORY.md / STATUS.md / DAILY_STATUS.md / HOME_WRAPUP.md /
    MORNING_BRIEF.md 等）在各工作区同名，若压平到同一用户级 memory/ 目录，
    会被 collect 按 mtime「较新者胜出」互相覆盖（7/24、7/30 两次污染事件），
    再由 distribute 扇回所有工作区 → 全部变成同一份错误内容。
    因此收集/分发流程严格限定只处理每日日志，项目身份文件由各工作区独立保留。
    """
    return bool(_DAILY_RE.match(name))


def cleanup_duplicates(dirs: list[Path]) -> int:
    """清理 WPS 云盘生成的 -副本 冲突文件。返回删除数量。"""
    cleaned = 0
    for d in dirs:
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if f.is_file() and is_skip_file(f.name):
                try:
                    f.unlink()
                    cleaned += 1
                except OSError:
                    pass
    if cleaned > 0:
        print(f"  [clean] Removed {cleaned} WPS conflict copies")
    return cleaned


def sync_file(local: Path, remote: Path, force: str | None) -> str:
    """同步单个文件，返回状态字符串。

    force=None  : 较新者胜出
    force="push": 强制本地 → 远程（本地有才推，没有跳过）
    force="pull": 强制远程 → 本地（远程有才拉，没有跳过）
    """
    le = local.exists()
    re = remote.exists()

    if force == "push":
        if le:
            shutil.copy2(local, remote)
            return "pushed"
        return "skipped"

    if force == "pull":
        if re:
            shutil.copy2(remote, local)
            return "pulled"
        return "skipped"

    # 双向模式：较新者胜出
    if not le and not re:
        return "none"
    if not le:
        shutil.copy2(remote, local)
        return "pulled"
    if not re:
        shutil.copy2(local, remote)
        return "pushed"
    lm = local.stat().st_mtime
    rm = remote.stat().st_mtime
    if lm > rm:
        shutil.copy2(local, remote)
        return "pushed"
    if rm > lm:
        shutil.copy2(remote, local)
        return "pulled"
    return "same"


def sync_dir(local_dir: Path, remote_dir: Path, force: str | None) -> dict:
    """同步目录（递归），返回统计。"""
    stats = {"pushed": 0, "pulled": 0, "skipped": 0}
    local_files: dict[Path, Path] = {}
    if local_dir.exists():
        for f in local_dir.rglob("*"):
            if f.is_file() and not is_skip_file(f.name):
                local_files[f.relative_to(local_dir)] = f
    remote_files: dict[Path, Path] = {}
    if remote_dir.exists():
        for f in remote_dir.rglob("*"):
            if f.is_file() and not is_skip_file(f.name):
                remote_files[f.relative_to(remote_dir)] = f
    for rel in set(local_files) | set(remote_files):
        r = sync_file(local_dir / rel, remote_dir / rel, force)
        if "push" in r:
            stats["pushed"] += 1
        elif "pull" in r:
            stats["pulled"] += 1
        else:
            stats["skipped"] += 1
    return stats


# ─── 工作区记忆同步（v2.0）───────────────────────────────────────────────

def sync_workspace_memories(bases: list[Path], force: str | None) -> dict:
    """各工作区 .workbuddy/memory/ ↔ 中转目录。"""
    total = {"pushed": 0, "pulled": 0, "skipped": 0, "workspaces": 0}
    workspaces = find_workspaces(bases)
    if not workspaces:
        print("  ℹ️  未找到任何工作区")
        return total

    for ws in workspaces:
        ws_name = ws.name
        local_mem = ws / ".workbuddy" / "memory"
        remote_mem = SYNC / "workspaces" / ws_name / "memory"
        remote_mem.mkdir(parents=True, exist_ok=True)
        s = sync_dir(local_mem, remote_mem, force)
        status_parts = []
        if s["pushed"]:
            status_parts.append(f"推送 {s['pushed']}")
        if s["pulled"]:
            status_parts.append(f"拉取 {s['pulled']}")
        if s["skipped"]:
            status_parts.append(f"跳过 {s['skipped']}")
        status = " | ".join(status_parts) if status_parts else "无变化"
        print(f"  📁 工作区 {ws_name}/.workbuddy/memory/: {status}")
        for k in ("pushed", "pulled", "skipped"):
            total[k] += s[k]
        total["workspaces"] += 1

    return total


# ─── v3.0：用户级 memory 分发 ──────────────────────────────────────────

def distribute_user_memory_to_workspaces(bases: list[Path]) -> int:
    """将用户级 ~/.workbuddy/memory/*.md 分发到所有本地工作区。

    用户级 memory/ 是唯一权威来源。
    每台电脑上的所有工作区都能读到同样的记忆。
    返回分发的文件数。
    """
    user_mem = LOCAL / "memory"
    if not user_mem.exists():
        return 0

    workspaces = find_workspaces(bases)
    if not workspaces:
        return 0

    distributed = 0
    for md_file in user_mem.glob("*.md"):
        if not md_file.is_file():
            continue
        if not is_daily_log(md_file.name):
            continue  # v3.6: 项目身份文件不得压平/扇出，避免跨工作区互覆污染
        for ws in workspaces:
            ws_mem = ws / ".workbuddy" / "memory"
            ws_mem.mkdir(parents=True, exist_ok=True)
            dest = ws_mem / md_file.name
            # 只有本地没有、或用户级更新时才复制
            if not dest.exists() or md_file.stat().st_mtime > dest.stat().st_mtime:
                shutil.copy2(md_file, dest)
                distributed += 1

    return distributed


def collect_workspace_memories_to_user(bases: list[Path]) -> int:
    """将各工作区的 memory/*.md 收集合并到用户级 memory/。

    离开电脑前执行，确保用户级有所有工作区的最新记忆。
    返回收集的文件数。
    """
    user_mem = LOCAL / "memory"
    user_mem.mkdir(parents=True, exist_ok=True)

    workspaces = find_workspaces(bases)
    if not workspaces:
        return 0

    collected = 0
    for ws in workspaces:
        ws_mem = ws / ".workbuddy" / "memory"
        if not ws_mem.exists():
            continue
        for md_file in ws_mem.glob("*.md"):
            if not md_file.is_file():
                continue
            if not is_daily_log(md_file.name):
                continue  # v3.6: 项目身份文件不得压平/扇出，避免跨工作区互覆污染
            dest = user_mem / md_file.name
            if not dest.exists() or md_file.stat().st_mtime > dest.stat().st_mtime:
                shutil.copy2(md_file, dest)
                collected += 1

    return collected


# ─── 主流程 ────────────────────────────────────────────────────────────────

def main():
    force = None
    if len(sys.argv) > 1:
        args = [a for a in sys.argv[1:] if not a.startswith("--")]
        if args:
            force = args[0].lower()
            if force not in ("push", "pull"):
                print(f"未知方向: {force}")
                sys.exit(1)

    SYNC.mkdir(parents=True, exist_ok=True)
    total = {"pushed": 0, "pulled": 0, "skipped": 0}

    # 自动探测工作区路径（提前，供清扫与同步复用）
    bases = detect_workspace_bases()

    # --- ① 清理 WPS 冲突副本文件（防止同步风暴 / 阻止垃圾上传到云） ---
    # 清扫范围：整个 _sync 传输树 + 各工作区 .workbuddy/memory/
    junk_roots = [SYNC]
    for ws in find_workspaces(bases):
        junk_roots.append(ws / ".workbuddy" / "memory")
    cleanup_duplicates(junk_roots)
    print("=" * 62)
    print(f"WorkBuddy 跨设备同步 v3.1")
    direction_label = {"push": "推送 (本地→共享)", "pull": "拉取 (共享→本地)"}.get(force, "双向同步 (较新者胜出)")
    print(f"模式: {direction_label}")
    print(f"工作区路径: {[str(b) for b in bases]}")
    print("=" * 62)

    step = 0

    # --- ① 离开电脑前：先收集各工作区记忆到用户级 ---
    if force in (None, "push"):
        step += 1
        print(f"\n[{step}] 收集：工作区记忆 → 用户级 memory/")
        n = collect_workspace_memories_to_user(bases)
        print(f"  收集 {n} 个文件")

    # --- ② 用户级文件同步 ---
    step += 1
    print(f"\n[{step}] 用户级：身份 & 记忆文件")
    for fname in [
        "IDENTITY.md", "SOUL.md", "USER.md",
        "MEMORY.md", "workspace-state.json",
    ]:
        r = sync_file(LOCAL / fname, SYNC / fname, force)
        arrow = {"pushed": "→", "pulled": "←"}.get(r, "·")
        print(f"  {arrow} {fname}: {r}")
        if "push" in r:
            total["pushed"] += 1
        elif "pull" in r:
            total["pulled"] += 1
        else:
            total["skipped"] += 1

    # --- ②b v3.2: HANDOFF.md 也走中转通道（绕开失效的 WPS 云盘） ---
    r = sync_file(HANDOFF_LOCAL, HANDOFF_REMOTE, force)
    arrow = {"pushed": "→", "pulled": "←"}.get(r, "·")
    print(f"  {arrow} HANDOFF.md (中转通道): {r}")
    if "push" in r:
        total["pushed"] += 1
    elif "pull" in r:
        total["pulled"] += 1
    else:
        total["skipped"] = total.get("skipped", 0) + 1

    # --- ②c v3.3: 同步守护进程和开机启动脚本（两台电脑自动同步 watch_sync 本身） ---
    SYNC_SELF_DIR = Path(r"C:\WorkBuddy\_sync")
    for self_fname in ["watch_sync.py", "start_sync.bat", "AI_HANDOFF_GUIDE.md",
                       "find_junk.py", "clean_junk.py", "sync_identity.py"]:
        r = sync_file(SYNC_SELF_DIR / self_fname, SYNC / self_fname, force)
        arrow = {"pushed": "→", "pulled": "←"}.get(r, "·")
        print(f"  {arrow} {self_fname} (守护进程): {r}")
        if "push" in r:
            total["pushed"] += 1
        elif "pull" in r:
            total["pulled"] += 1
        else:
            total["skipped"] = total.get("skipped", 0) + 1

    s = sync_dir(LOCAL / "memory", SYNC / "memory", force)
    print(f"  📁 memory/: 推送 {s['pushed']} | 拉取 {s['pulled']} | 跳过 {s['skipped']}")
    for k in total:
        total[k] += s[k]

    # --- ③ 工作区 memory 同步（v2.0） ---
    step += 1
    print(f"\n[{step}] 工作区级：各工作区 .workbuddy/memory/ ↔ 中转")
    ws_total = sync_workspace_memories(bases, force)
    for k in total:
        total[k] += ws_total[k]

    # --- ④ 到新电脑后：分发用户级记忆到所有工作区 ---
    if force in (None, "pull"):
        step += 1
        print(f"\n[{step}] 分发：用户级 memory/ → 各工作区")
        n = distribute_user_memory_to_workspaces(bases)
        ws_count = len(find_workspaces(bases))
        print(f"  {ws_count} 个工作区，共分发 {n} 个文件")

    # --- 汇总 ---
    print("-" * 62)
    parts = [f"推送 {total['pushed']}", f"拉取 {total['pulled']}", f"跳过 {total['skipped']}"]
    if ws_total.get("workspaces"):
        parts.append(f"工作区 {ws_total['workspaces']} 个")
    print(f"汇总: {', '.join(parts)}")
    print("=" * 62)


if __name__ == "__main__":
    main()
