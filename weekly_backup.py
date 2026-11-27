#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
weekly_backup.py - the missing executable half of the v7 local-first doctrine.

Why this exists: SKILL.md recommends "local-first live work + a weekly one-way
incremental backup to the cloud", but until v7.1.0 there was NO tool that
actually performed that backup. This script is that tool. It is deliberately
WRITE-ONLY toward the cloud and never deletes or reads cloud files back.

Usage (all paths are arguments - no machine-specific path is hardcoded):
  python weekly_backup.py --src D:\WorkBuddy\projects --dst "C:\Users\<name>\WPS Cloud\backup" --dry-run
  python weekly_backup.py --src ... --dst ... --seed        # first run: baseline from cloud
  python weekly_backup.py --src ... --dst ... --confirm      # really copy changed files
  python weekly_backup.py --src ... --dst ... --status       # show manifest + last run

Safety rails:
  * default is DRY-RUN: nothing is copied unless --confirm is passed
  * never deletes anything on either side
  * never reads a cloud file back into the local workspace (one-way only)
  * excludes noise (node_modules, .git, dist, caches, __pycache__, conflict copies)
  * manifest keyed by relative path -> (size, mtime_ns); only new/changed copied
  * every action and every skip reason is logged to a UTF-8 run log
  * all console output is ASCII-only (Windows codepage-safe)
"""
import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# Directories and file names that are never worth backing up.
EXCLUDE_DIRS = {
    "node_modules", ".git", ".workbuddy", "__pycache__", "dist",
    ".cache", ".venv", "venv", "site-packages", ".next", "target", "build",
    ".edgeone", "tmp", "temp", ".pytest_cache", ".mypy_cache",
}
EXCLUDE_FILE_PREFIXES = ("liveness_", "heartbeat_", "~$")
EXCLUDE_FILE_SUFFIXES = (".pyc", ".log", ".pid", ".tmp", ".swp")
# WPS cloud conflict copies: new content renamed to <name>-copy<ts> (CN suffix too)
CONFLICT_MARKERS = ("-copy",)

DEFAULT_MANIFEST = "weekly_backup_manifest.json"
DEFAULT_LOG = "weekly_backup.log"


def ascii_safe(text):
    """Keep console output pure ASCII regardless of Windows code page."""
    return str(text).encode("ascii", "replace").decode("ascii")


def log(msg, log_path=None, quiet=False):
    line = "[%s] %s" % (datetime.now().strftime("%H:%M:%S"), ascii_safe(msg))
    if not quiet:
        print(line, flush=True)
    if log_path:
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError as e:
            print("WARN: cannot write run log: %s" % ascii_safe(e))


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return "%.1f%s" % (n, unit)
        n /= 1024.0


def excluded(name, is_dir):
    low = name.lower()
    # Windows reserved device names (nul, con, prn, aux, com1-9, lpt1-9).
    # os.walk may surface them as files; os.stat/relpath then resolve to
    # \\.\<name> on a different mount and relpath() raises ValueError.
    _stem = low.split('.', 1)[0]
    if _stem in {'nul', 'con', 'prn', 'aux'} or (
            len(_stem) == 4 and _stem[:3] in ('com', 'lpt') and _stem[3].isdigit()):
        return True
    if is_dir and low in EXCLUDE_DIRS:
        return True
    if any(low.startswith(p) for p in EXCLUDE_FILE_PREFIXES):
        return True
    if not is_dir and low.endswith(EXCLUDE_FILE_SUFFIXES):
        return True
    if not is_dir and any(m in low for m in CONFLICT_MARKERS):
        return True
    return False


def scan_tree(root):
    """Return {relative_path: (size, mtime_ns)} for all non-excluded files.
    No file-count cap: a capped walk has caused a 17GB -> 5GB misreport before."""
    out = {}
    if not root.is_dir():
        return out
    for dp, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not excluded(d, True)]
        for f in files:
            if excluded(f, False):
                continue
            p = os.path.join(dp, f)
            try:
                st = os.stat(p)
            except OSError:
                continue
            try:
                rel = os.path.relpath(p, str(root))
            except ValueError:
                # reserved device name resolved to a different mount - skip
                continue
            out[rel.replace("\\", "/")] = (st.st_size, st.st_mtime_ns)
    return out


def load_manifest(path):
    if not path.is_file():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("files", {})
    except (OSError, ValueError) as e:
        print("ERROR: manifest unreadable (%s). Use --seed to rebuild." % ascii_safe(e))
        sys.exit(2)


def save_manifest(path, files, note):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.now().isoformat(timespec="seconds"),
                   "note": note, "files": files}, f, ensure_ascii=False, indent=1)


def changed(src_snapshot, manifest):
    """Files new to the manifest or with a different (size, mtime_ns)."""
    return [rel for rel, meta in src_snapshot.items() if manifest.get(rel) != list(meta)]


def main():
    ap = argparse.ArgumentParser(description="Weekly one-way incremental backup to a cloud pipe.")
    ap.add_argument("--src", required=True, help="LOCAL live workspace (read-only source)")
    ap.add_argument("--dst", required=True, help="CLOUD backup destination (write-only target)")
    ap.add_argument("--manifest", default=None, help="manifest path (default: <dst>/%s)" % DEFAULT_MANIFEST)
    ap.add_argument("--log", default=None, help="run log path (default: <dst>/%s)" % DEFAULT_LOG)
    ap.add_argument("--dry-run", action="store_true", help="preview only (also the default when --confirm absent)")
    ap.add_argument("--seed", action="store_true", help="baseline manifest from CLOUD contents (migrated users)")
    ap.add_argument("--confirm", action="store_true", help="actually copy files")
    ap.add_argument("--status", action="store_true", help="print manifest summary and exit")
    args = ap.parse_args()

    src = Path(args.src).resolve()
    dst = Path(args.dst).resolve()
    manifest_path = Path(args.manifest) if args.manifest else dst / DEFAULT_MANIFEST
    log_path = Path(args.log) if args.log else dst / DEFAULT_LOG

    if not src.is_dir():
        print("ERROR: source is not a directory: %s" % ascii_safe(src))
        print("HINT: pass the LOCAL workspace root, not a file or a cloud path.")
        sys.exit(2)

    if args.status:
        m = load_manifest(manifest_path)
        print("manifest: %s" % ascii_safe(manifest_path))
        print("entries: %d" % len(m))
        if manifest_path.is_file():
            print("updated: %s" % datetime.fromtimestamp(manifest_path.stat().st_mtime).isoformat(timespec="seconds"))
        return 0

    manifest = load_manifest(manifest_path)
    src_snapshot = scan_tree(src)
    log("scan: %d local files (%s)" % (len(src_snapshot), human_size(sum(v[0] for v in src_snapshot.values()))), log_path)

    if args.seed:
        # Migrated from a live sync pipe: cloud already holds the files, so seed from cloud.
        cloud = scan_tree(dst)
        cloud.pop(DEFAULT_MANIFEST, None)
        cloud.pop(DEFAULT_LOG, None)
        if not cloud:
            print("ERROR: --seed found no files in cloud destination.")
            print("HINT: NEW install with an empty cloud must use the FULL first run instead:")
            print("      python weekly_backup.py --src ... --dst ... --confirm   (no --seed)")
            sys.exit(3)
        baseline = {rel: list(meta) for rel, meta in cloud.items()}
        save_manifest(manifest_path, baseline, "seeded from cloud at first run")
        log("SEEDED: %d entries from cloud; next run is incremental" % len(baseline), log_path)
        return 0

    todo = changed(src_snapshot, manifest)
    bytes_todo = sum(src_snapshot[r][0] for r in todo)
    log("plan: %d new/changed files (%s)" % (len(todo), human_size(bytes_todo)), log_path)
    if not todo:
        log("result: nothing changed - already up to date", log_path)
        return 0

    if not args.confirm:
        log("DRY-RUN: no files copied. Re-run with --confirm to execute.", log_path)
        for rel in todo[:20]:
            log("  would copy: %s" % rel, log_path)
        if len(todo) > 20:
            log("  ... and %d more" % (len(todo) - 20), log_path)
        return 0

    copied = 0
    failed = 0
    updated = dict((k, list(v)) for k, v in manifest.items())  # baseline: what was already backed up
    for rel in todo:
        s = src / rel.replace("/", os.sep)
        d = dst / rel.replace("/", os.sep)
        try:
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(s), str(d))  # write-only; never touch cloud source files
            copied += 1
            # Only a successful copy may advance the manifest entry. A failed
            # file keeps its OLD entry (or none), so the next run retries it.
            updated[rel] = list(src_snapshot[rel])
        except OSError as e:
            failed += 1
            log("FAIL %s : %s" % (rel, ascii_safe(e)), log_path)
    save_manifest(manifest_path, updated, "incremental backup %s" % datetime.now().strftime("%Y-%m-%d"))
    log("DONE: copied=%d failed=%d pending=%d manifest=%d" % (
        copied, failed, len(todo) - copied, len(updated)), log_path)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
