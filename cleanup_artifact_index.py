r"""
artifact-index dead-reference cleaner (systematic root fix, 2026-09-07)
=======================================================================
Background: user screenshots showed 11+ zombie entries in the IDE artifact
panel (pointing at already-deleted temp scripts/reports under Temp /
.workbuddy/memory / outputs). Root cause:
  - WorkBuddy's artifact-index (one JSON per session, recording the absolute
    file:/// URIs of every Read/Write/present_files call) is symlinked into
    WPS cloud drive.
  - Even after the file is deleted from disk, the URI stays in the index.
  - Restarting the IDE does not clear it, because the JSON reference was never
    cleaned.
"Systematic root fix" = run this on every sync / watch_sync startup, so there
is no window in which a dead URI can be re-shown.

Usage:
  python cleanup_artifact_index.py                  # default: current user's ~/.workbuddy/artifact-index
  python cleanup_artifact_index.py --path <DIR>     # custom path
  python cleanup_artifact_index.py --all-sessions   # scan all sessions (default: active sessions only)
  python cleanup_artifact_index.py --dry-run        # report only, do not delete

Exit codes:
  0 = normal (regardless of whether anything was cleaned)
  1 = argument error
  2 = fatal error (e.g. path does not exist)

Integrated by: C:\WorkBuddy\_sync\sync_identity.py v3.8+.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path


DEFAULT_ARTIFACT_DIR = Path.home() / ".workbuddy" / "artifact-index"
WORKBUDDY_USER_DIR = Path.home() / ".workbuddy"


def uri_to_path(uri):
    """Convert file:///C:/path/file.txt to C:\\path\\file.txt (Windows)."""
    if not uri.startswith("file:///"):
        return None
    p = uri[8:]
    p = p.replace("%20", " ")
    if p.startswith("C:/"):
        p = p.replace("/", "\\")
        return p
    return None


def is_dead_ref(artifact):
    """Return True if the artifact's file URI points at a non-existent file."""
    uri = artifact.get("uri", "")
    path = uri_to_path(uri)
    if not path:
        return False
    return not os.path.exists(path)


def clean_one(json_path: Path, dry_run=False):
    """Clean dead refs in a single artifact-index JSON file.

    Returns (original_count, dead_count, alive_count, dead_names).
    """
    if not json_path.exists():
        return 0, 0, 0, []

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [warn] cannot read {json_path.name}: {e}")
        return 0, 0, 0, []

    arts = data.get("artifacts", [])
    original_count = len(arts)
    dead = [a for a in arts if is_dead_ref(a)]
    alive = [a for a in arts if not is_dead_ref(a)]
    dead_names = [a.get("name", "?") for a in dead]

    if dead and not dry_run:
        # Atomic write
        data["artifacts"] = alive
        data["lastUpdated"] = int(time.time() * 1000)
        tmp = json_path.with_suffix(json_path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, json_path)

    return original_count, len(dead), len(alive), dead_names


def find_artifact_index_dir(path_arg=None):
    """Locate the artifact-index directory. Returns None if not found."""
    if path_arg:
        p = Path(path_arg)
        return p if p.exists() else None
    if DEFAULT_ARTIFACT_DIR.exists():
        return DEFAULT_ARTIFACT_DIR
    return None


def main():
    parser = argparse.ArgumentParser(description="Clean dead references in artifact-index")
    parser.add_argument("--path", help="artifact-index directory (default ~/.workbuddy/artifact-index)")
    parser.add_argument("--all-sessions", action="store_true",
                        help="clean all sessions (default: only recently-updated active sessions)")
    parser.add_argument("--dry-run", action="store_true", help="report only, do not delete")
    parser.add_argument("--quiet", action="store_true", help="minimal output")
    args = parser.parse_args()

    artifact_dir = find_artifact_index_dir(args.path)
    if not artifact_dir:
        if not args.quiet:
            print(f"[skip] artifact-index directory not found: {args.path or DEFAULT_ARTIFACT_DIR}")
        return 0

    json_files = sorted(artifact_dir.glob("*.json"))
    if not json_files:
        if not args.quiet:
            print(f"[skip] no JSON files under {artifact_dir}")
        return 0

    # Default: only clean recently-updated active sessions (lastUpdated < 24h),
    # so historical sessions are left intact (avoids wiping other timepoints'
    # artifact records by mistake). With --all-sessions, clean everything.
    active_files = []
    if args.all_sessions:
        active_files = json_files
    else:
        now_ms = int(time.time() * 1000)
        one_day_ms = 24 * 60 * 60 * 1000
        for jf in json_files:
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    d = json.load(f)
                last = d.get("lastUpdated", 0)
                if now_ms - last < one_day_ms:
                    active_files.append(jf)
            except Exception:
                continue

    if not active_files:
        if not args.quiet:
            print("[skip] no active sessions (none updated within 24h)")
        return 0

    total_dead = 0
    total_alive = 0
    cleaned_files = 0

    if not args.quiet:
        print(f"[scan] {artifact_dir}")
        print(f"       active sessions: {len(active_files)} / total {len(json_files)}")
        print(f"       mode: {'all-sessions' if args.all_sessions else 'active-only'}{' (dry-run)' if args.dry_run else ''}")
        print()

    for jf in active_files:
        orig, dead, alive, dead_names = clean_one(jf, dry_run=args.dry_run)
        if dead > 0:
            cleaned_files += 1
            total_dead += dead
            if not args.quiet:
                print(f"  [{jf.name[:8]}...] {orig} -> {alive} (cleaned {dead} dead)")
                for n in dead_names[:5]:
                    print(f"      - {n}")
                if len(dead_names) > 5:
                    print(f"      ... +{len(dead_names) - 5} more")
        total_alive += alive

    if not args.quiet:
        print()
        print(f"[done] files with dead refs: {cleaned_files}/{len(active_files)}")
        print(f"       cleaned {total_dead} dead references, kept {total_alive} valid")
        if args.dry_run:
            print("       [dry-run] no files modified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
