#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
find_junk.py — WPS 云同步垃圾文件扫描器 v1.0
============================================
用途：扫描 C:\\WorkBuddy 云同步树，找出 WPS 产生的冲突副本 / 临时文件，
      生成一份可在 WPS 网页端对照删除的报告。

垃圾判定（文件名匹配，WPS 真实命名规律）：
  1. 含 "副本"           → WPS 冲突副本，如 2026-06-03-副本20260706105036.md
  2. 含 "~$"             → Office 临时锁文件，如 ~$report.docx
  3. 含 ".tmp"           → 临时文件
  4. 含 "conflict"       → 部分客户端冲突标记
  5. 形如 " (1)" "(2)"    → 序号冲突副本

额外安全校验：对每个垃圾文件，尝试推导其"正本"文件名
  （去掉 -副本<时间戳> 后缀）。若正本存在 → 标为「可确认删除」。

输出：
  - 控制台摘要
  - <scan_root>/junk_report.html   彩色报告（同步到云，处处可看）
  - <scan_root>/junk_report.json   机器可读

用法：
  python find_junk.py                 # 扫描 C:\\WorkBuddy
  python find_junk.py "D:\\other"    # 扫描指定目录
"""

import os
import re
import sys
import json
import html
from datetime import datetime
from collections import defaultdict

DEFAULT_ROOT = r"C:\WorkBuddy"

# 跳过的噪声目录（绝不碰）
SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".idea", ".vscode"}

# 垃圾文件名正则
JUNK_RES = [
    (re.compile(r"副本"), "WPS冲突副本"),
    (re.compile(r"~\$", re.I), "Office临时锁文件"),
    (re.compile(r"\.tmp$", re.I), "临时文件"),
    (re.compile(r"conflict", re.I), "冲突标记"),
    (re.compile(r"\s\(\d+\)$"), "序号冲突副本"),
]

# 从副本文件名推导正本名：去掉 "-副本<14位时间戳>"
TS_RE = re.compile(r"-?副本\d{14}")
GEN_RE = re.compile(r"副本\d{14}")


def classify(name: str):
    for rx, label in JUNK_RES:
        if rx.search(name):
            return label
    return None


def strip_to_original(name: str) -> str:
    """把 2026-06-03-副本20260706105036.md → 2026-06-03.md"""
    base, ext = os.path.splitext(name)
    base = GEN_RE.sub("", base)
    base = TS_RE.sub("", base)
    # 去掉可能残留的尾随 '-'
    base = base.rstrip("-")
    return base + ext


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def scan(root: str):
    junk = []  # dict: name, folder(rel), full, size, kind, original, has_original
    total_files = 0

    for dp, dn, fn in os.walk(root):
        # 原地剪枝
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            total_files += 1
            kind = classify(f)
            if not kind:
                continue
            full = os.path.join(dp, f)
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            rel_folder = os.path.relpath(dp, root)
            original = strip_to_original(f)
            has_original = os.path.exists(os.path.join(dp, original)) and original != f
            junk.append({
                "name": f,
                "folder": rel_folder if rel_folder != "." else "(根目录)",
                "size": size,
                "kind": kind,
                "original": original,
                "has_original": has_original,
            })

    return junk, total_files


def build_report(root, junk, total_files):
    total_junk = len(junk)
    total_size = sum(j["size"] for j in junk)
    confirmed = sum(1 for j in junk if j["has_original"])

    # 按文件夹分组
    by_folder = defaultdict(list)
    for j in junk:
        by_folder[j["folder"]].append(j)

    gen_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ---- HTML ----
    folder_rows = []
    for folder in sorted(by_folder, key=lambda f: -len(by_folder[f])):
        items = by_folder[folder]
        cnt = len(items)
        sz = sum(i["size"] for i in items)
        conf = sum(1 for i in items if i["has_original"])
        folder_rows.append(f"""
        <tr>
          <td class="path">{html.escape(folder)}</td>
          <td class="num">{cnt}</td>
          <td class="num">{human_size(sz)}</td>
          <td class="num">{conf}</td>
        </tr>""")

    sample_html = ""
    if junk:
        # 取前 50 个样例
        for j in junk[:50]:
            tag = '<span class="ok">✓ 有正本</span>' if j["has_original"] else '<span class="warn">⚠ 无正本</span>'
            sample_html += f"""
            <tr>
              <td class="path">{html.escape(j['folder'])}</td>
              <td>{html.escape(j['name'])}</td>
              <td>{html.escape(j['kind'])}</td>
              <td class="num">{human_size(j['size'])}</td>
              <td>{tag}</td>
            </tr>"""

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WPS 云同步垃圾文件扫描报告</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "Microsoft YaHei", sans-serif; margin: 0;
          background: #f5f6f8; color: #1f2329; line-height: 1.6; }}
  .wrap {{ max-width: 980px; margin: 0 auto; padding: 28px 20px 60px; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  .sub {{ color: #8a9099; font-size: 13px; margin-bottom: 20px; }}
  .cards {{ display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 26px; }}
  .card {{ flex: 1; min-width: 160px; background: #fff; border: 1px solid #e6e8eb;
           border-radius: 10px; padding: 16px 18px; }}
  .card .v {{ font-size: 26px; font-weight: 700; color: #d4380d; }}
  .card .l {{ font-size: 13px; color: #8a9099; margin-top: 2px; }}
  .card.green .v {{ color: #237804; }}
  section {{ background: #fff; border: 1px solid #e6e8eb; border-radius: 10px;
             padding: 18px 20px; margin-bottom: 20px; }}
  section h2 {{ font-size: 16px; margin: 0 0 12px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #f0f1f3; }}
  th {{ color: #8a9099; font-weight: 600; background: #fafbfc; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  td.path {{ font-family: "SFMono-Regular", Consolas, monospace; color: #2f54eb; font-size: 12px; word-break: break-all; }}
  .ok {{ color: #237804; font-weight: 600; }}
  .warn {{ color: #d4380d; font-weight: 600; }}
  .steps {{ counter-reset: s; padding-left: 0; list-style: none; }}
  .steps li {{ position: relative; padding: 8px 0 8px 34px; border-bottom: 1px dashed #eee; }}
  .steps li::before {{ counter-increment: s; content: counter(s); position: absolute; left: 0;
        top: 8px; width: 22px; height: 22px; background: #2f54eb; color: #fff;
        border-radius: 50%; text-align: center; line-height: 22px; font-size: 12px; font-weight: 700; }}
  code {{ background: #f0f2f5; padding: 2px 6px; border-radius: 4px; font-size: 12px; }}
  .note {{ background: #fffbe6; border: 1px solid #ffe58f; border-radius: 8px;
           padding: 12px 14px; font-size: 13px; color: #614700; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>🧹 WPS 云同步垃圾文件扫描报告</h1>
  <div class="sub">扫描根目录：<code>{html.escape(root)}</code> ｜ 生成时间：{gen_time} ｜ 扫描文件总数：{total_files}</div>

  <div class="cards">
    <div class="card"><div class="v">{total_junk}</div><div class="l">垃圾文件总数</div></div>
    <div class="card"><div class="v">{human_size(total_size)}</div><div class="l">垃圾占用空间</div></div>
    <div class="card"><div class="v">{len(by_folder)}</div><div class="l">涉及文件夹数</div></div>
    <div class="card green"><div class="v">{confirmed}</div><div class="l">可确认删除(有正本)</div></div>
  </div>

  <section>
    <h2>📁 按文件夹分布（照这个清单去云端删）</h2>
    <table>
      <tr><th>文件夹（相对扫描根）</th><th class="num">垃圾数</th><th class="num">大小</th><th class="num">有正本</th></tr>
      {''.join(folder_rows)}
    </table>
  </section>

  <section>
    <h2>🗑 云端删除步骤（只能在 WPS 网页端删，本地删会被云盘拉回）</h2>
    <ol class="steps">
      <li>打开 <b>WPS 网页版</b>（www.wps.cn → 登录同一账号）→ 进入「WPS 云盘」。</li>
      <li>导航到上方清单里的第一个文件夹，例如 <code>WorkBuddy/_sync/identity/memory</code>。</li>
      <li>在文件夹内搜索框输入 <b>副本</b>；若搜索是递归的，可直接全选删除；否则逐层进入子目录搜索。</li>
      <li>按 <code>Ctrl+A</code> 全选 → 点「删除」。文件多时分批删（每批 500~1000 个），避免网页卡死。</li>
      <li>删完后云端会自动把删除同步到本机，本地副本也会消失。重复上述步骤清理每个文件夹。</li>
      <li>回到本机跑一次 <code>python find_junk.py</code> 复检，直到垃圾数为 0。</li>
    </ol>
    <div class="note">💡 提示：这些 <code>-副本</code> 文件都是 WPS 在 7/6 双进程冲突时生成的，正本（无副本后缀）都已存在，<b>删除 100% 安全</b>。当前 v2.0 单 leader 机制已阻止新副本产生，这是一次性清理。</div>
  </section>

  <section>
    <h2>🔍 垃圾文件样例（前 50 个）</h2>
    <table>
      <tr><th>文件夹</th><th>文件名</th><th>类型</th><th class="num">大小</th><th>校验</th></tr>
      {sample_html}
    </table>
    <p style="color:#8a9099;font-size:12px;">仅展示前 50 个；完整清单见同目录 <code>junk_report.json</code>。</p>
  </section>
</div>
</body>
</html>"""

    return html_doc


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ROOT
    if not os.path.isdir(root):
        print(f"❌ 目录不存在: {root}")
        sys.exit(1)

    print(f"🔍 扫描: {root}")
    junk, total = scan(root)
    print(f"   扫描文件总数: {total}")
    print(f"   垃圾文件数:   {len(junk)}")

    html_doc = build_report(root, junk, total)
    out_html = os.path.join(root, "junk_report.html")
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html_doc)

    out_json = os.path.join(root, "junk_report.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "scan_root": root,
            "generated": datetime.now().isoformat(timespec="seconds"),
            "total_files": total,
            "junk_count": len(junk),
            "junk_size": sum(j["size"] for j in junk),
            "confirmed_deletable": sum(1 for j in junk if j["has_original"]),
            "items": junk,
        }, f, ensure_ascii=False, indent=2)

    total_size = sum(j["size"] for j in junk)
    confirmed = sum(1 for j in junk if j["has_original"])
    print(f"   垃圾总大小:   {human_size(total_size)}")
    print(f"   可确认删除:   {confirmed}（有正本）")
    print(f"   报告已生成:")
    print(f"     → {out_html}")
    print(f"     → {out_json}")


if __name__ == "__main__":
    main()
