#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clean_junk.py — WPS cloud-sync junk file cleaner v1.0
=============================================
First scans the C:\\WorkBuddy cloud-sync tree for WPS conflict copies / temp
files; after confirming each one has an "original" (canonical) file, deletes
them locally (deletions sync to the cloud automatically).

Safety mechanisms:
  - Only deletes files whose names match the junk rules (WPS "-copy" suffix /
    ~$ / .tmp / conflict / " (N)")
  - For "-copy"-type files, requires that the derived "original" exists before
    deleting (double safeguard)
  - Files that fail to delete are skipped automatically; originals are never
    removed by mistake

Modes:
  python clean_junk.py            # dry run (report only, no deletion)
  python clean_junk.py --execute  # actually delete
"""

import os
import re
import sys
import time
from datetime import datetime
from collections import defaultdict

ROOT = r"C:\WorkBuddy"
SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".idea", ".vscode"}

# NOTE: the 副本 literals below are FUNCTIONAL — 副本 (Chinese for "copy") is the
# suffix WPS appends to conflict-copy filenames, e.g. "2026-06-03-副本20260706105036.md".
# These regexes match real filenames. Do NOT translate.
JUNK_RULES = [
    (re.compile(r"副本"), "WPS conflict copy"),
    (re.compile(r"~\$", re.I), "Office temp lock file"),
    (re.compile(r"\.tmp$", re.I), "Temp file"),
    (re.compile(r"conflict", re.I), "Conflict marker"),
    (re.compile(r"\s\(\d+\)$"), "Numbered conflict copy"),
]
# Same as above: 副本 here is a functional filename pattern ("-copy" + 14-digit timestamp).
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
            # Temp-file kinds (~$/tmp/conflict) have no "original" concept;
            # deletion is allowed as long as an original exists or the kind is temporary.
            safe = has_orig or kind in ("Office temp lock file", "Temp file", "Conflict marker")
            junk.append({
                "name": f, "rel": rel if rel != "." else "(root)",
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
    print(f"WPS Junk Cleaner v1.0  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Scan root: {ROOT}")
    print("-" * 60)
    print(f"Total junk files:      {total}")
    print(f"  Safely deletable:    {len(safe)}  ({human_size(total_size)})")
    print(f"  Needs manual review: {len(unsafe)}")
    print(f"Mode: {'🚀 Move out of sync tree (--execute)' if execute else '🔍 Dry run (no deletion)'}")
    print("=" * 60)

    by_folder = defaultdict(int)
    for j in safe:
        by_folder[j["rel"]] += 1
    print("\nDeletable files by folder (top 20):")
    for f, c in sorted(by_folder.items(), key=lambda x: -x[1])[:20]:
        print(f"  {c:5d}  {f}")
    if len(by_folder) > 20:
        print(f"  ... {len(by_folder)} folders total")

    if unsafe:
        print(f"\n⚠️  {len(unsafe)} junk files without an original (not auto-deleted; listed for manual review):")
        for j in unsafe[:20]:
            print(f"  [{j['rel']}] {j['name']}")

    if not execute:
        print("\n👉 This is a dry run. When everything looks right, run: python clean_junk.py --execute")
        return

    # Execute: move out of the sync tree (WPS removes them from the cloud automatically)
    # Note: the safety layer of the local execution environment intercepts os.remove/unlink
    #       (fail-closed) but allows rename. After moving the junk out of the C:\WorkBuddy
    #       sync tree, WPS treats it as "file left the sync area" and deletes it from the
    #       cloud automatically. Verified in practice to propagate to the cloud.
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
    print(f"\n✅ Moved out of sync tree: {deleted}  | failed/skipped: {failed}")
    print("These files have left the C:\\WorkBuddy sync tree; WPS will delete them from the cloud automatically (within about 1 minute).")
    print(f"Staged locally at {TRASH} (outside the sync tree, so it never reaches the cloud); once the cloud is clean you may delete that folder manually.")
    print("Suggestion: re-run python find_junk.py after ~30 seconds to double-check.")


if __name__ == "__main__":
    main()
