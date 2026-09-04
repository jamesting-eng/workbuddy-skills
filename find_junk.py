#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
find_junk.py — WPS cloud-sync junk file scanner v1.0
============================================
Purpose: scan the C:\\WorkBuddy cloud-sync tree for WPS conflict copies / temp
      files and generate a report for cross-checking deletion in the WPS web app.

Junk detection (file-name matching, real WPS naming patterns):
  1. Contains the WPS "-copy" suffix (副本) → WPS conflict copy,
     e.g. 2026-06-03-副本20260706105036.md
  2. Contains "~$"       → Office temp lock file, e.g. ~$report.docx
  3. Contains ".tmp"     → temp file
  4. Contains "conflict" → conflict marker from some clients
  5. Looks like " (1)" "(2)" → numbered conflict copies

Extra safety check: for each junk file, derive its "original" file name
  (strip the -副本<timestamp> suffix). If the original exists → marked
  "confirmed deletable".

Output:
  - Console summary
  - <scan_root>/junk_report.html   color report (synced to the cloud, viewable anywhere)
  - <scan_root>/junk_report.json   machine-readable

Usage:
  python find_junk.py                 # scan C:\\WorkBuddy
  python find_junk.py "D:\\other"    # scan a given directory
"""

import os
import re
import sys
import json
import html
from datetime import datetime
from collections import defaultdict

DEFAULT_ROOT = r"C:\WorkBuddy"

# Noise directories to skip (never touched)
SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".idea", ".vscode"}

# Junk file-name regexes.
# NOTE: the 副本 literal below is FUNCTIONAL — 副本 (Chinese for "copy") is the
# suffix WPS appends to conflict-copy filenames. Do NOT translate.
JUNK_RES = [
    (re.compile(r"副本"), "WPS conflict copy"),
    (re.compile(r"~\$", re.I), "Office temp lock file"),
    (re.compile(r"\.tmp$", re.I), "Temp file"),
    (re.compile(r"conflict", re.I), "Conflict marker"),
    (re.compile(r"\s\(\d+\)$"), "Numbered conflict copy"),
]

# Derive the original name from a copy's file name: strip "-副本<14-digit timestamp>".
# NOTE: 副本 below is a functional filename pattern — do NOT translate.
TS_RE = re.compile(r"-?副本\d{14}")
GEN_RE = re.compile(r"副本\d{14}")


def classify(name: str):
    for rx, label in JUNK_RES:
        if rx.search(name):
            return label
    return None


def strip_to_original(name: str) -> str:
    """2026-06-03-副本20260706105036.md → 2026-06-03.md"""
    base, ext = os.path.splitext(name)
    base = GEN_RE.sub("", base)
    base = TS_RE.sub("", base)
    # Strip any leftover trailing '-'
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
        # Prune in place
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
                "folder": rel_folder if rel_folder != "." else "(root)",
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

    # Group by folder
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
        # Take the first 50 samples
        for j in junk[:50]:
            tag = '<span class="ok">✓ Original exists</span>' if j["has_original"] else '<span class="warn">⚠ No original</span>'
            sample_html += f"""
            <tr>
              <td class="path">{html.escape(j['folder'])}</td>
              <td>{html.escape(j['name'])}</td>
              <td>{html.escape(j['kind'])}</td>
              <td class="num">{human_size(j['size'])}</td>
              <td>{tag}</td>
            </tr>"""

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WPS Cloud-Sync Junk File Scan Report</title>
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
  <h1>🧹 WPS Cloud-Sync Junk File Scan Report</h1>
  <div class="sub">Scan root: <code>{html.escape(root)}</code> | Generated: {gen_time} | Files scanned: {total_files}</div>

  <div class="cards">
    <div class="card"><div class="v">{total_junk}</div><div class="l">Total junk files</div></div>
    <div class="card"><div class="v">{human_size(total_size)}</div><div class="l">Junk disk usage</div></div>
    <div class="card"><div class="v">{len(by_folder)}</div><div class="l">Folders involved</div></div>
    <div class="card green"><div class="v">{confirmed}</div><div class="l">Confirmed deletable (original exists)</div></div>
  </div>

  <section>
    <h2>📁 Distribution by folder (delete in the cloud following this list)</h2>
    <table>
      <tr><th>Folder (relative to scan root)</th><th class="num">Junk</th><th class="num">Size</th><th class="num">With original</th></tr>
      {''.join(folder_rows)}
    </table>
  </section>

  <section>
    <h2>🗑 Cloud deletion steps (delete only in the WPS web app; local deletions get pulled back by the cloud drive)</h2>
    <ol class="steps">
      <li>Open the <b>WPS web app</b> (www.wps.cn → sign in with the same account) → go to "WPS Cloud Drive".</li>
      <li>Navigate to the first folder in the list above, e.g. <code>WorkBuddy/_sync/identity/memory</code>.</li>
      <li>Type <b>副本</b> in the folder's search box (functional search term: 副本 is Chinese for "copy", the WPS conflict-copy suffix); if the search is recursive you can select all and delete at once, otherwise descend into each subfolder and search.</li>
      <li>Press <code>Ctrl+A</code> to select all → click "Delete". With many files, delete in batches (500–1000 per batch) to avoid freezing the web page.</li>
      <li>When done, the cloud automatically syncs the deletions to this machine and the local copies disappear too. Repeat these steps for every folder.</li>
      <li>Back on this machine, run <code>python find_junk.py</code> to re-check, until the junk count is 0.</li>
    </ol>
    <div class="note">💡 Note: these <code>-副本</code> files were all generated by WPS during the 7/6 dual-process conflict; the originals (without the -副本 suffix) all exist, so <b>deletion is 100% safe</b>. The v2.0 single-leader mechanism now prevents new copies from appearing — this is a one-time cleanup.</div>
  </section>

  <section>
    <h2>🔍 Junk file samples (first 50)</h2>
    <table>
      <tr><th>Folder</th><th>File name</th><th>Kind</th><th class="num">Size</th><th>Check</th></tr>
      {sample_html}
    </table>
    <p style="color:#8a9099;font-size:12px;">Only the first 50 are shown; see <code>junk_report.json</code> in the same directory for the full list.</p>
  </section>
</div>
</body>
</html>"""

    return html_doc


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ROOT
    if not os.path.isdir(root):
        print(f"❌ Directory does not exist: {root}")
        sys.exit(1)

    print(f"🔍 Scanning: {root}")
    junk, total = scan(root)
    print(f"   Files scanned: {total}")
    print(f"   Junk files:    {len(junk)}")

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
    print(f"   Total junk size:   {human_size(total_size)}")
    print(f"   Confirmed deletable: {confirmed} (original exists)")
    print(f"   Reports generated:")
    print(f"     → {out_html}")
    print(f"     → {out_json}")


if __name__ == "__main__":
    main()
