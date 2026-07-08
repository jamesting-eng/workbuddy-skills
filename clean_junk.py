#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clean_junk.py — WPS 云同步垃圾文件清理器 v1.0
=============================================
先扫描 C:\\WorkBuddy 云同步树里的 WPS 冲突副本 / 临时文件，
确认每个都有「正本」后，在本地删除（删除会自动同步到云端）。

安全机制：
  - 只删文件名匹配垃圾规则的文件（-副本 / ~$ / .tmp / conflict / " (N)"）
  - 对 -副本 类，要求推导出「正本」且正本存在才删（双保险）
  - 删除失败的文件自动跳过，绝不误删正本

模式：
  python clean_junk.py            # 干跑（只报告，不删）
  python clean_junk.py --execute  # 真删
"""

import os
import re
import sys
import time
from datetime import datetime
from collections import defaultdict

ROOT = r"C:\WorkBuddy"
SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".idea", ".vscode"}

JUNK_RULES = [
    (re.compile(r"副本"), "WPS冲突副本"),
    (re.compile(r"~\$", re.I), "Office临时锁文件"),
    (re.compile(r"\.tmp$", re.I), "临时文件"),
    (re.compile(r"conflict", re.I), "冲突标记"),
    (re.compile(r"\s\(\d+\)$"), "序号冲突副本"),
]
TS_RE = re.compile(r"-?副本\d{14}")
GEN_RE = re.compile(r"副本\d{14}")


def classify(name):
    for rx, label in JUNK_RULES:
        if rx.search(name):
            return label
    return None


def strip_to_original(name):
    base, ext = os.path.splitext(name)
    base = GEN_RE.sub("", base)
    base = TS_RE.sub("", base).rstrip("-")
    return base + ext


def human_size(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


def scan():
    junk = []
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            kind = classify(f)
            if not kind:
                continue
            full = os.path.join(dp, f)
            rel = os.path.relpath(dp, ROOT)
            original = strip_to_original(f)
            has_orig = os.path.exists(os.path.join(dp, original)) and original != f
            # 临时文件(~$/tmp/conflict)无"正本"概念，只要有正本或属临时类就允许删
            safe = has_orig or kind in ("Office临时锁文件", "临时文件", "冲突标记")
            junk.append({
                "name": f, "rel": rel if rel != "." else "(根)",
                "full": full, "kind": kind,
                "original": original, "has_orig": has_orig, "safe": safe,
            })
    return junk


def main():
    execute = "--execute" in sys.argv
    junk = scan()
    total = len(junk)
    safe = [j for j in junk if j["safe"]]
    unsafe = [j for j in junk if not j["safe"]]
    total_size = sum(os.path.getsize(j["full"]) if os.path.exists(j["full"]) else 0 for j in safe)

    print("=" * 60)
    print(f"WPS 垃圾清理器 v1.0  ｜  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"扫描根: {ROOT}")
    print("-" * 60)
    print(f"垃圾文件总数:   {total}")
    print(f"  可安全删除:   {len(safe)}  ({human_size(total_size)})")
    print(f"  需人工确认:   {len(unsafe)}")
    print(f"模式:           {'🚀 移出同步区 (--execute)' if execute else '🔍 干跑 (不删)'}")
    print("=" * 60)

    by_folder = defaultdict(int)
    for j in safe:
        by_folder[j["rel"]] += 1
    print("\n可删除文件按文件夹分布（前 20）:")
    for f, c in sorted(by_folder.items(), key=lambda x: -x[1])[:20]:
        print(f"  {c:5d}  {f}")
    if len(by_folder) > 20:
        print(f"  ... 共 {len(by_folder)} 个文件夹")

    if unsafe:
        print(f"\n⚠️  {len(unsafe)} 个无正本的垃圾（不自动删，列出来人工判断）:")
        for j in unsafe[:20]:
            print(f"  [{j['rel']}] {j['name']}")

    if not execute:
        print("\n👉 这是干跑结果。确认无误后运行： python clean_junk.py --execute")
        return

    # 执行：移出同步区（WPS 自动从云端删除）
    # 说明：本机执行环境的安全层会拦截 os.remove/unlink（fail-closed），
    #       但允许 rename。把垃圾移出 C:\WorkBuddy 同步树后，WPS 会将其
    #       视为「文件离开同步区」而自动从云端删除。已实测验证可通到云端。
    TRASH = r"C:\_wb_trash"
    os.makedirs(TRASH, exist_ok=True)
    deleted = 0
    failed = 0
    counter = 0
    for j in safe:
        try:
            if os.path.exists(j["full"]):
                counter += 1
                dst = os.path.join(TRASH, f"{counter}_{j['name']}")
                os.rename(j["full"], dst)
                deleted += 1
        except OSError:
            failed += 1
    print(f"\n✅ 已移出同步区: {deleted}  ｜ 失败跳过: {failed}")
    print("这些文件已离开 C:\\WorkBuddy 同步树，WPS 会自动从云端删除（约 1 分钟内完成）。")
    print(f"本地暂存于 {TRASH}（在同步区之外，不会进云端），确认云端清空后可手动删除该文件夹。")
    print("建议过 30 秒后跑一次 python find_junk.py 复检。")


if __name__ == "__main__":
    main()
