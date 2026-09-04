r"""
Fix session paths for WorkBuddy cross-device sync.

Unifies all session cwd paths to use C:\WorkBuddy\... and merges
duplicate project caches created after path migration.

Handles:
1. JSON session files (*.json) in .workbuddy/sessions/
2. SQLite database (workbuddy.db) sessions table
3. Project caches in .workbuddy/projects/ (merge old c-Users-* → c-WorkBuddy-*)
4. JSONL message cache cwd fields in .workbuddy/projects/c-WorkBuddy-*/
"""

import json
import os
import sqlite3
import glob


def find_sessions_dir():
    """Find the .workbuddy/sessions directory."""
    # Check symbolically linked location first (WPS cloud drive)
    candidates = [
        os.path.expanduser("~/.workbuddy/sessions"),
    ]

    # Also try common WPS cloud drive paths
    user_profile = os.environ.get("USERPROFILE", "")
    if user_profile:
        for wps_dir in [
            os.path.join(user_profile, "Documents", "WPSDrive"),
        ]:
            if os.path.isdir(wps_dir):
                # Find the actual numbered subdirectory
                for item in os.listdir(wps_dir):
                    # NOTE: "WPS云盘" is the literal WPS cloud-drive folder name on
                    # disk — functional path component, do NOT translate.
                    candidate = os.path.join(
                        user_profile, "Documents", "WPSDrive",
                        item, "WPS云盘", ".workbuddy", "sessions"
                    )
                    if os.path.isdir(candidate):
                        candidates.append(candidate)

    for c in candidates:
        if os.path.isdir(c):
            return os.path.dirname(c), c

    raise FileNotFoundError("Cannot find .workbuddy/sessions directory")


def fix_session_json_files(sessions_dir):
    """Replace user-specific paths in all JSON session files."""
    # Patterns to replace (in JSON-escaped form)
    old_patterns = []

    # Scan existing sessions to detect user-specific paths
    for fname in os.listdir(sessions_dir):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(sessions_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        if not content.strip():
            continue
        # Detect any \\Users\\<name>\\WorkBuddy paths
        import re
        matches = set(re.findall(r'C:\\\\Users\\\\([^\\\\]+)\\\\WorkBuddy', content))
        for user in matches:
            old_patterns.append(f"C:\\\\Users\\\\{user}\\\\WorkBuddy")

    if not old_patterns:
        print("No user-specific paths found in session JSON files.")
        return 0

    old_patterns = list(set(old_patterns))
    fixed = 0
    for fname in os.listdir(sessions_dir):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(sessions_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        if not content.strip():
            continue

        new_content = content
        for old in old_patterns:
            new_content = new_content.replace(old, "C:\\\\WorkBuddy")

        if new_content != content:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(new_content)
            fixed += 1
            print(f"Fixed JSON: {fname}")

    print(f"Fixed {fixed} session JSON files.")
    return fixed


def fix_database(db_path):
    """Replace user-specific paths in the SQLite database sessions table."""
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return 0

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Check if sessions table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
    if not cur.fetchone():
        print("No 'sessions' table found in database.")
        conn.close()
        return 0

    # Find all sessions with user-specific paths
    cur.execute("SELECT id, cwd FROM sessions WHERE cwd LIKE '%\\\\Users\\\\%\\\\WorkBuddy%'")
    rows = cur.fetchall()

    if not rows:
        print("No user-specific paths found in database.")
        conn.close()
        return 0

    print(f"Found {len(rows)} database sessions to fix:")

    # Collect unique old paths
    import re
    old_paths = set()
    for session_id, cwd in rows:
        if cwd:
            m = re.match(r'(C:\\Users\\[^\\]+\\WorkBuddy)', cwd)
            if m:
                old_paths.add(m.group(1))

    fixed = 0
    for old_path in old_paths:
        # Use REPLACE for simple string replacement in SQLite
        cur.execute(
            "UPDATE sessions SET cwd = REPLACE(cwd, ?, ?) WHERE cwd LIKE ?",
            (old_path, "C:\\WorkBuddy", f"{old_path}%")
        )
        count = cur.rowcount
        if count > 0:
            print(f"  Fixed {count} rows: {old_path} -> C:\\WorkBuddy")
            fixed += count

    conn.commit()

    # Verify
    cur.execute("SELECT id, cwd FROM sessions")
    for session_id, cwd in cur.fetchall():
        if cwd:
            exists = os.path.isdir(cwd)
            status = "OK" if exists else "MISSING"
            short = cwd if len(cwd) < 60 else "..." + cwd[-55:]
            print(f"  [{status}] {session_id[:8]}... -> {short}")

    conn.close()
    print(f"Fixed {fixed} database rows.")
    return fixed


def merge_project_caches(workbuddy_dir):
    """Merge old c-Users-*-WorkBuddy-* caches into c-WorkBuddy-* caches."""
    projects_dir = os.path.join(workbuddy_dir, "projects")
    if not os.path.isdir(projects_dir):
        print("No projects directory found, skipping cache merge.")
        return 0

    old_dirs = {}
    new_dirs = {}

    for name in os.listdir(projects_dir):
        full_path = os.path.join(projects_dir, name)
        if not os.path.isdir(full_path) or name.startswith("_"):
            continue
        if name.startswith("c-Users-") and "-WorkBuddy-" in name:
            parts = name.split("-WorkBuddy-", 1)
            if len(parts) == 2:
                old_dirs[parts[1]] = full_path
        elif name.startswith("c-WorkBuddy-"):
            timestamp = name[len("c-WorkBuddy-"):]
            new_dirs[timestamp] = full_path

    if not old_dirs:
        print("No old caches to merge.")
        return 0

    print(f"Old caches: {len(old_dirs)}, New caches: {len(new_dirs)}")

    backups_dir = os.path.join(projects_dir, "_merged_backups")
    os.makedirs(backups_dir, exist_ok=True)

    merged = 0
    skipped = 0
    import shutil

    for timestamp, old_dir in sorted(old_dirs.items()):
        if timestamp in new_dirs:
            new_dir = new_dirs[timestamp]
            print(f"  [{timestamp}] Merging -> {os.path.basename(new_dir)}")

            for fname in os.listdir(old_dir):
                if not fname.endswith(".jsonl"):
                    continue
                old_file = os.path.join(old_dir, fname)
                new_file = os.path.join(new_dir, fname)

                with open(old_file, "r", encoding="utf-8") as f:
                    old_lines = f.readlines()

                new_lines = []
                if os.path.exists(new_file):
                    with open(new_file, "r", encoding="utf-8") as f:
                        new_lines = f.readlines()

                # Deduplicate by message ID
                new_ids = set()
                for line in new_lines:
                    try:
                        msg = json.loads(line)
                        new_ids.add(msg.get("id", ""))
                    except json.JSONDecodeError:
                        pass

                unique_old = [l for l in old_lines if
                    (json.loads(l).get("id", "") if l.strip() else "") not in new_ids]

                if not unique_old:
                    skipped += 1
                    continue

                # Backup new file before overwriting
                if os.path.exists(new_file):
                    shutil.copy2(new_file, os.path.join(
                        backups_dir, f"{os.path.basename(new_dir)}_{fname}"))

                # Merge and sort by timestamp
                all_lines = unique_old + new_lines
                all_lines.sort(key=lambda l: json.loads(l).get("timestamp", 0))

                with open(new_file, "w", encoding="utf-8") as f:
                    f.writelines(all_lines)

                print(f"    {fname}: {len(unique_old)} old + {len(new_lines)} new = {len(all_lines)} msgs")
                merged += 1

            # Move old dir to backup
            shutil.move(old_dir, os.path.join(backups_dir, os.path.basename(old_dir)))
        else:
            # Rename old dir to new convention
            new_name = f"c-WorkBuddy-{timestamp}"
            new_path = os.path.join(projects_dir, new_name)
            if not os.path.exists(new_path):
                shutil.move(old_dir, new_path)
                print(f"  [{timestamp}] Renamed -> {new_name}")
                merged += 1

    print(f"Merged: {merged}, Skipped: {skipped}")
    return merged


def fix_jsonl_cwd_paths(projects_dir, workbuddy_dir):
    """Fix cwd field inside all JSONL message cache files.

    After path migration, the cwd field in each JSONL message may still
    contain user-specific paths like c:\\Users\\James Ting\\... instead
    of the unified C:\\WorkBuddy\\... path. This causes sessions to
    appear empty when opened from a different computer.

    Also normalizes lowercase 'c:' to uppercase 'C:' in JSONL cwd fields.
    """
    if not os.path.isdir(projects_dir):
        print("No projects directory found.")
        return 0

    import re

    # Patterns to detect in cwd fields (handles both C: and c:)
    old_pattern = re.compile(
        r'^[cC]:\\Users\\[^\\]+\\WorkBuddy\\(.+)$',
        re.IGNORECASE
    )

    fixed = 0
    for name in sorted(os.listdir(projects_dir)):
        full_path = os.path.join(projects_dir, name)
        if not os.path.isdir(full_path) or name.startswith("_"):
            continue

        # Only process c-WorkBuddy-* dirs
        if not name.startswith("c-WorkBuddy-"):
            continue

        for fname in os.listdir(full_path):
            if not fname.endswith(".jsonl"):
                continue
            fpath = os.path.join(full_path, fname)
            if os.path.getsize(fpath) == 0:
                continue

            with open(fpath, "r", encoding="utf-8") as f:
                lines = f.readlines()

            modified = False
            new_lines = []
            for line in lines:
                line = line.rstrip("\n\r")
                if not line.strip():
                    new_lines.append(line)
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    new_lines.append(line)
                    continue

                cwd = msg.get("cwd", "")
                if cwd:
                    m = old_pattern.match(cwd)
                    if m:
                        # Replace with unified path
                        new_cwd = "C:\\WorkBuddy\\" + m.group(1)
                        msg["cwd"] = new_cwd
                        modified = True

                new_lines.append(json.dumps(msg, ensure_ascii=False))

            if modified:
                # Backup before overwriting
                backup_dir = os.path.join(projects_dir, "_jsonl_backup")
                os.makedirs(backup_dir, exist_ok=True)
                import shutil
                shutil.copy2(fpath, os.path.join(backup_dir, f"{name}_{fname}"))

                with open(fpath, "w", encoding="utf-8") as f:
                    f.write("\n".join(new_lines) + "\n")
                fixed += 1
                print(f"  Fixed JSONL: {name}/{fname}")

    return fixed


def main():
    print("=" * 60)
    print("WorkBuddy Cross-Device Sync - Path Fixer")
    print("=" * 60)
    print()

    try:
        workbuddy_dir, sessions_dir = find_sessions_dir()
        db_path = os.path.join(workbuddy_dir, "workbuddy.db")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Make sure .workbuddy is symlinked to your cloud storage.")
        return 1

    projects_dir = os.path.join(workbuddy_dir, "projects")

    print(f"Sessions dir:  {sessions_dir}")
    print(f"Database:      {db_path}")
    print(f"Projects dir:  {projects_dir}")
    print()

    # Step 1: Fix JSON session files
    print("--- Step 1: Fixing JSON session files ---")
    json_fixed = fix_session_json_files(sessions_dir)
    print()

    # Step 2: Fix SQLite database
    print("--- Step 2: Fixing SQLite database ---")
    db_fixed = fix_database(db_path)
    print()

    # Step 3: Merge project caches
    print("--- Step 3: Merging project caches ---")
    cache_fixed = merge_project_caches(workbuddy_dir)
    print()

    # Step 4: Fix JSONL cwd paths
    print("--- Step 4: Fixing JSONL cwd paths ---")
    jsonl_fixed = fix_jsonl_cwd_paths(projects_dir, workbuddy_dir)
    print()

    print("=" * 60)
    print(f"Summary: {json_fixed} JSON + {db_fixed} DB rows + {cache_fixed} caches + {jsonl_fixed} JSONL cwds fixed")
    print("=" * 60)
    print()
    print("Next: Restart WorkBuddy and verify old sessions can be opened.")

    return 0


if __name__ == "__main__":
    exit(main())
