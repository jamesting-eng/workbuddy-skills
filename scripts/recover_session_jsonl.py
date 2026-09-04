#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
recover_session_jsonl.py — WorkBuddy 5.5.x "lost conversation history" recovery tool.

ROOT CAUSE IT FIXES
-------------------
WorkBuddy stores conversation bodies as JSONL at:
    ~/.workbuddy/projects/<encoded-cwd>/<session-uuid>.jsonl

Since 5.5.2, the app resolves the `C:\\WorkBuddy` junction to the real WPS
cloud path, so NEW messages are written into a NEW encoded directory:
    c-WorkBuddy-2026-06-03-12-41-29            (old, junction short path)
    C-Users-62588-Documents-WPSDrive-...-WorkBuddy-2026-06-03-12-41-29   (new)
The UI reads only the NEW directory, so pre-upgrade history seems "lost".
The old JSONL files are still intact on disk.

WHAT THIS SCRIPT DOES
---------------------
1. Scans `~/.workbuddy/projects/` for legacy-encoded dirs (starting with
   `c-`, lowercase) and their new-encoded counterparts (same workspace
   suffix, different prefix).
2. For each session UUID present in BOTH: merges old+new rows, dedup by
   message `id` (old rows win, keeping full timeline), writes atomically.
3. For sessions only in OLD dir: copies them (plus .meta.json) into the
   NEW dir so the UI can find them.
4. NEVER deletes anything. Originals stay untouched.

USAGE
-----
    python recover_session_jsonl.py [--projects-dir PATH] [--dry-run]

Always take a backup first:
    python -c "import shutil; shutil.copytree(r'C:\\Users\\<you>\\.workbuddy\\projects', r'D:\\projects_backup')"

Pure Python 3, no third-party deps. ASCII-only output (console-safe).
"""
import argparse
import json
import os
import shutil
import sys
import time


def load_rows(path):
    rows = []
    with open(path, "rb") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                rows.append({"_raw": line.decode("utf-8", errors="replace")})
    return rows


def merge_session(old_dir, new_dir, uuid, dry_run=False):
    old_f = os.path.join(old_dir, uuid + ".jsonl")
    new_f = os.path.join(new_dir, uuid + ".jsonl")
    if not os.path.exists(old_f):
        return "skip: no old jsonl"
    old_rows = load_rows(old_f)
    new_rows = load_rows(new_f) if os.path.exists(new_f) else []
    seen, merged, dup = set(), [], 0
    for r in old_rows + new_rows:
        rid = r.get("id") if isinstance(r, dict) else None
        if rid and rid in seen:
            dup += 1
            continue
        if rid:
            seen.add(rid)
        merged.append(r)
    tss = [r["timestamp"] for r in merged if isinstance(r, dict) and r.get("timestamp")]
    rng = "?"
    if tss:
        rng = "%s~%s" % (
            time.strftime("%m-%d", time.localtime(min(tss) / 1000)),
            time.strftime("%m-%d", time.localtime(max(tss) / 1000)),
        )
    if dry_run:
        return "dry-run: %d old + %d new -> %d (dup %d) %s" % (
            len(old_rows), len(new_rows), len(merged), dup, rng)
    tmp_f = new_f + ".merge_tmp"
    with open(tmp_f, "wb") as fh:
        for r in merged:
            if "_raw" in r:
                fh.write(r["_raw"].encode("utf-8") + b"\n")
            else:
                fh.write(json.dumps(r, ensure_ascii=False).encode("utf-8") + b"\n")
    for _ in range(3):
        try:
            os.replace(tmp_f, new_f)
            return "MERGED: %d old + %d new -> %d (dup %d), %s, %s" % (
                len(old_rows), len(new_rows), len(merged), dup,
                rng, format(os.path.getsize(new_f), ","))
        except PermissionError:
            time.sleep(1.5)
    return "REPLACE FAILED (file busy), tmp kept: " + tmp_f


def workspace_suffix(dirname):
    """Extract trailing workspace token like 2026-06-03-12-41-29 from an
    encoded projects dir name, tolerant of path separators."""
    parts = dirname.replace("\\", "-").replace("/", "-").split("-")
    # find last occurrence of pattern 2026-MM-DD-...
    for i in range(len(parts) - 5, -1, -1):
        if (len(parts[i]) == 4 and parts[i].isdigit() and parts[i].startswith("20")
                and all(p.isdigit() for p in parts[i + 1:i + 6])):
            return "-".join(parts[i:i + 6])
    return None


def main():
    ap = argparse.ArgumentParser(description="Recover WorkBuddy session JSONLs lost to cwd re-encoding")
    ap.add_argument("--projects-dir", default=os.path.join(os.path.expanduser("~"), ".workbuddy", "projects"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pj = args.projects_dir
    if not os.path.isdir(pj):
        print("projects dir not found:", pj)
        sys.exit(1)

    entries = [d for d in os.listdir(pj) if os.path.isdir(os.path.join(pj, d))]
    # legacy dirs: lowercase 'c-' prefix; new dirs: anything else containing the same workspace suffix
    legacy = [d for d in entries if d.startswith("c-") and "_" not in d]
    merged_n, copied_n, fail_n = 0, 0, 0

    for old_name in sorted(legacy):
        suffix = workspace_suffix(old_name)
        if not suffix:
            continue
        old_dir = os.path.join(pj, old_name)
        # find new-encoded counterpart: same suffix, not starting with lowercase 'c-'
        candidates = [d for d in entries
                      if d != old_name and suffix in d and workspace_suffix(d) == suffix]
        if not candidates:
            print("[%s] no new-encoded counterpart found, skip" % old_name)
            continue
        new_name = sorted(candidates, key=len)[0]  # shortest = closest match
        new_dir = os.path.join(pj, new_name)
        print("[%s] -> [%s]" % (old_name, new_name))
        for f in sorted(os.listdir(old_dir)):
            if not f.endswith(".jsonl"):
                continue
            uuid = f[:-6]
            old_f, new_f = os.path.join(old_dir, f), os.path.join(new_dir, f)
            if os.path.exists(new_f):
                res = merge_session(old_dir, new_dir, uuid, args.dry_run)
                print("   [merge] %s: %s" % (uuid[:8], res))
                if "MERGED" in res:
                    merged_n += 1
                elif "FAIL" in res:
                    fail_n += 1
            else:
                if args.dry_run:
                    print("   [copy ] %s: would copy" % uuid[:8])
                    copied_n += 1
                else:
                    shutil.copy2(old_f, new_f)
                    meta = os.path.join(old_dir, uuid + ".meta.json")
                    if os.path.exists(meta):
                        dst_meta = os.path.join(new_dir, uuid + ".meta.json")
                        if not os.path.exists(dst_meta):
                            shutil.copy2(meta, dst_meta)
                    print("   [copy ] %s: copied (%s)" % (uuid[:8], format(os.path.getsize(new_f), ",")))
                    copied_n += 1

    print("\nSUMMARY: merged=%d copied=%d failed=%d %s" % (
        merged_n, copied_n, fail_n, "(dry-run)" if args.dry_run else ""))
    print("Restart WorkBuddy to reload session history.")


if __name__ == "__main__":
    main()
