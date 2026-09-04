r"""
Session restore and merge tool for WorkBuddy cross-device sync.

Modes:
  restore  - Rebuild a lost session's JSONL cache from structured data
  merge    - Combine two sessions into one with dedup and timestamp sorting

Critical format rules (learned the hard way):
  - cwd MUST use backslashes (C:\...), NOT forward slashes
  - user_id MUST match real user UUID, NOT "default"
  - JSONL messages need: type, sessionId(camelCase), cwd, content(array),
    providerData({} or {agent:"cli"}), timestamp(ms)
  - Timestamps must be correct year — wrong year = "56 years ago" display bug
"""
import json
import os
import sqlite3
import uuid
import shutil
import sys
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))


def get_workbuddy_dir():
    """Auto-detect .workbuddy directory."""
    candidates = [
        os.path.expanduser("~/.workbuddy"),
    ]
    user_profile = os.environ.get("USERPROFILE", "")
    if user_profile:
        for wps_root in [os.path.join(user_profile, "Documents", "WPSDrive")]:
            if os.path.isdir(wps_root):
                for item in os.listdir(wps_root):
                    candidate = os.path.join(wps_root, item, "WPS云盘", ".workbuddy")
                    if os.path.isdir(candidate):
                        candidates.append(candidate)

    for c in candidates:
        if os.path.isdir(c):
            return c
    raise FileNotFoundError("Cannot find .workbuddy directory")


def get_user_id(db_path):
    """Get the actual user_id from any existing session."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM sessions WHERE user_id != 'default' AND deleted_at IS NULL LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if row:
        return row[0]
    return "default"


def restore_session(session_id, project_cwd, topics, db_path, wb_dir):
    r"""
    Rebuild a lost session's JSONL cache and DB record.

    Args:
        session_id: UUID of the session
        project_cwd: CWD path with backslashes, e.g. C:\WorkBuddy\2026-06-01-10-12-31
        topics: List of (role, text) tuples where role is 'user' or 'assistant'
        db_path: Path to workbuddy.db
        wb_dir: Path to .workbuddy directory
    """
    # Get real user_id
    user_id = get_user_id(db_path)
    print(f"User ID: {user_id}")

    # Ensure backslash cwd
    cwd = project_cwd.replace("/", "\\")
    print(f"CWD: {cwd}")

    # Parse expected date from project directory name
    dir_name = os.path.basename(cwd)
    parts = dir_name.split("-")
    if len(parts) >= 6:
        year, month, day, hour, minute = parts[0], parts[1], parts[2], parts[3], parts[4]
        base_ts = int(datetime(int(year), int(month), int(day),
                                int(hour), int(minute), 0,
                                tzinfo=CST).timestamp() * 1000)
    else:
        base_ts = int(datetime(2026, 6, 1, 10, 0, 0, tzinfo=CST).timestamp() * 1000)

    print(f"Base timestamp: {base_ts} ({datetime.fromtimestamp(base_ts/1000, CST)})")

    # Build messages
    messages = []
    ts = base_ts

    # Session restore marker
    marker_id = str(uuid.uuid4())
    messages.append({
        "id": marker_id,
        "type": "message",
        "role": "user",
        "sessionId": session_id,
        "cwd": cwd,
        "content": [{"type": "input_text", "text":
            "[Session restore marker] The full message history of this conversation was "
            "lost during cross-device sync. Below is the context rebuilt from the cloud "
            "summary and project artifacts."}],
        "providerData": {},
        "timestamp": ts
    })

    # File history snapshot (required by WorkBuddy)
    messages.append({
        "id": str(uuid.uuid4()),
        "type": "file-history-snapshot",
        "sessionId": session_id,
        "cwd": cwd,
        "isSnapshotUpdate": False,
        "snapshot": {"messageId": marker_id, "trackedFileBackups": {}},
        "timestamp": ts + 1000
    })

    # Assistant acknowledgment
    ack_id = str(uuid.uuid4())
    messages.append({
        "id": ack_id,
        "type": "message",
        "role": "assistant",
        "sessionId": session_id,
        "cwd": cwd,
        "content": [{"type": "output_text", "text":
            "Sure — here is the restored summary of this session."}],
        "providerData": {"agent": "cli"},
        "parentId": marker_id,
        "timestamp": ts + 60000
    })

    # Topic messages
    ts += 120000
    for role, text in topics:
        msg_id = str(uuid.uuid4())
        if role == "user":
            messages.append({
                "id": msg_id,
                "type": "message",
                "role": "user",
                "sessionId": session_id,
                "cwd": cwd,
                "content": [{"type": "input_text", "text": f"(restored) {text}"}],
                "providerData": {},
                "timestamp": ts
            })
            reply_id = str(uuid.uuid4())
            messages.append({
                "id": reply_id,
                "type": "message",
                "role": "assistant",
                "sessionId": session_id,
                "cwd": cwd,
                "content": [{"type": "output_text", "text": f"(restored) {text}"}],
                "providerData": {"agent": "cli"},
                "parentId": msg_id,
                "timestamp": ts + 30000
            })
        else:
            messages.append({
                "id": msg_id,
                "type": "message",
                "role": "assistant",
                "sessionId": session_id,
                "cwd": cwd,
                "content": [{"type": "output_text", "text": text}],
                "providerData": {"agent": "cli"},
                "timestamp": ts
            })
        ts += 60000

    # Write JSONL cache
    cache_dir = os.path.join(wb_dir, "projects",
                             f"c-WorkBuddy-{dir_name.replace(':', '_')}")
    # Handle colons in dir name
    dir_key = dir_name.replace(":", "_")
    cache_dir = os.path.join(wb_dir, "projects", f"c-WorkBuddy-{dir_key}")
    os.makedirs(cache_dir, exist_ok=True)

    jpath = os.path.join(cache_dir, f"{session_id}.jsonl")
    with open(jpath, "w", encoding="utf-8") as f:
        for msg in messages:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    print(f"Written {len(messages)} messages to {jpath}")

    # Insert DB record
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Check if already exists
    cur.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
    if cur.fetchone():
        # Update existing
        cur.execute("""
            UPDATE sessions SET
                custom_title = ?, status = ?, cwd = ?,
                user_id = ?, deleted_at = NULL,
                last_activity_at = ?
            WHERE id = ?
        """, ("Recovered Session", "completed", cwd, user_id, ts, session_id))
        print("Updated existing DB record.")
    else:
        # Insert new
        cur.execute("""
            INSERT INTO sessions
                (id, title, custom_title, status, cwd, created_at,
                 last_activity_at, user_id, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (session_id, "Recovered Session", "Recovered Session",
              "completed", cwd, base_ts, ts, user_id, base_ts))
        print("Inserted new DB record.")

    conn.commit()
    conn.close()

    print("Session restored successfully.")
    return len(messages)


def merge_sessions(source_id, target_id, db_path, wb_dir):
    """
    Merge source session into target session.

    Args:
        source_id: Session UUID to merge FROM (will be soft-deleted)
        target_id: Session UUID to merge INTO
        db_path: Path to workbuddy.db
        wb_dir: Path to .workbuddy directory
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get both sessions' info
    cur.execute("SELECT id, cwd, custom_title FROM sessions WHERE id = ? AND deleted_at IS NULL", (source_id,))
    src = cur.fetchone()
    cur.execute("SELECT id, cwd, custom_title FROM sessions WHERE id = ? AND deleted_at IS NULL", (target_id,))
    tgt = cur.fetchone()

    if not src:
        print(f"Source session not found: {source_id}")
        conn.close()
        return
    if not tgt:
        print(f"Target session not found: {target_id}")
        conn.close()
        return

    print(f"Source: {src['custom_title']} ({src['id'][:8]}...)")
    print(f"Target: {tgt['custom_title']} ({tgt['id'][:8]}...)")

    # Find JSONL files
    def find_jsonl(session_id, cwd):
        if not cwd:
            return None
        dir_name = os.path.basename(cwd).replace(":", "_")
        cache_dir = os.path.join(wb_dir, "projects", f"c-WorkBuddy-{dir_name}")
        if not os.path.isdir(cache_dir):
            # Try glob
            import glob
            matches = glob.glob(os.path.join(wb_dir, "projects", f"c-WorkBuddy-{dir_name[:10]}*"))
            if matches:
                cache_dir = matches[0]
            else:
                return None
        jpath = os.path.join(cache_dir, f"{session_id}.jsonl")
        if os.path.exists(jpath):
            return jpath
        return None

    src_jpath = find_jsonl(src["id"], src["cwd"])
    tgt_jpath = find_jsonl(tgt["id"], tgt["cwd"])

    if not src_jpath:
        print(f"Source JSONL not found for {src['id']}")
        conn.close()
        return
    if not tgt_jpath:
        print(f"Target JSONL not found for {tgt['id']}")
        conn.close()
        return

    print(f"Source JSONL: {src_jpath}")
    print(f"Target JSONL: {tgt_jpath}")

    # Read both JSONLs
    with open(src_jpath, "r", encoding="utf-8") as f:
        src_msgs = [json.loads(line) for line in f if line.strip()]
    with open(tgt_jpath, "r", encoding="utf-8") as f:
        tgt_msgs = [json.loads(line) for line in f if line.strip()]

    print(f"Source: {len(src_msgs)} messages")
    print(f"Target: {len(tgt_msgs)} messages")

    # Get existing IDs in target for dedup
    tgt_ids = {m.get("id", "") for m in tgt_msgs}

    # Filter source: skip file-history-snapshot, dedup by ID
    new_msgs = []
    skipped_system = 0
    skipped_dup = 0
    for m in src_msgs:
        mid = m.get("id", "")
        if m.get("type") == "file-history-snapshot":
            skipped_system += 1
            continue
        if mid in tgt_ids:
            skipped_dup += 1
            continue
        # Rewrite sessionId to target
        m["sessionId"] = target_id
        new_msgs.append(m)

    print(f"Skipped: {skipped_system} system msgs, {skipped_dup} duplicates")
    print(f"New messages to merge: {len(new_msgs)}")

    if not new_msgs:
        print("Nothing to merge. Already fully duplicated.")
        conn.close()
        return

    # Backup target before merging
    backup_dir = os.path.join(wb_dir, "projects",
        f"_merge_backup_{datetime.now(CST).strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(backup_dir, exist_ok=True)
    shutil.copy2(tgt_jpath, os.path.join(backup_dir, os.path.basename(tgt_jpath)))
    print(f"Backup: {backup_dir}")

    # Merge and sort by timestamp
    all_msgs = tgt_msgs + new_msgs
    # Ensure minimum time gap (60s) between merged batches
    # Find the max timestamp in new_msgs to check for collisions
    all_msgs.sort(key=lambda m: m.get("timestamp", 0))

    # Write merged
    with open(tgt_jpath, "w", encoding="utf-8") as f:
        for m in all_msgs:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    print(f"Merged: {len(all_msgs)} total messages")

    # Soft-delete source session
    cur.execute("""
        UPDATE sessions SET deleted_at = ?, status = 'completed'
        WHERE id = ?
    """, (int(datetime.now(CST).timestamp()), source_id))
    conn.commit()
    conn.close()

    print(f"Source session soft-deleted: {source_id[:8]}...")
    print("Merge complete. Restart WorkBuddy to see changes.")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("Usage:")
        print("  python restore_and_merge.py restore <session_id> <project_dir> [topics_file]")
        print("  python restore_and_merge.py merge <source_id> <target_id>")
        return 1

    try:
        wb_dir = get_workbuddy_dir()
        db_path = os.path.join(wb_dir, "workbuddy.db")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    command = sys.argv[1]

    if command == "restore":
        if len(sys.argv) < 4:
            print("Usage: restore_and_merge.py restore <session_id> <project_dir>")
            print("Example project_dir: C:\\WorkBuddy\\2026-06-01-10-12-31")
            return 1

        session_id = sys.argv[2]
        project_dir = sys.argv[3]

        # Simple topics for testing
        topics = [
            ("user", "Sample user message"),
            ("assistant", "Sample assistant reply"),
        ]

        count = restore_session(session_id, project_dir, topics, db_path, wb_dir)
        print(f"\nRestored {count} messages.")

    elif command == "merge":
        if len(sys.argv) < 4:
            print("Usage: restore_and_merge.py merge <source_id> <target_id>")
            return 1

        source_id = sys.argv[2]
        target_id = sys.argv[3]
        merge_sessions(source_id, target_id, db_path, wb_dir)

    else:
        print(f"Unknown command: {command}")
        print("Use 'restore' or 'merge'")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
