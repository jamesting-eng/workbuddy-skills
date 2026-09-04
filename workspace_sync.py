#!/usr/bin/env python3
r"""
Cross-device workspace sync script v3.0
- Scans C:\WorkBuddy disk workspaces and updates workspace_sync
- Generates/updates the machine-generated section of HANDOFF.md (keeps the AI-written section)
- Conversation export helper
- New: sync passphrase management + sync verification
"""

import sqlite3, os, json, time, re
from datetime import datetime

WORKBUDDY_ROOT = r"C:\WorkBuddy"
HANDOFF_DIR = os.path.join(WORKBUDDY_ROOT, "_sync")
HANDOFF_FILE = os.path.join(HANDOFF_DIR, "HANDOFF.md")
CONVERSATIONS_DIR = os.path.join(HANDOFF_DIR, "conversations")
SECRET_FILE = os.path.join(HANDOFF_DIR, "secret.txt")

# HANDOFF.md section markers.
# NOTE: DELIM_START / DELIM_MID are FUNCTIONAL — read_ai_section() does
# content.find(DELIM_MID) against on-disk HANDOFF.md files that were written
# with these exact Chinese markers. Do NOT translate.
DELIM_START = "<!-- ⚙️ 以下为机器生成区"
DELIM_MID = "<!-- ✅ 以下为 AI 手写区"


def find_db():
    home = os.path.expanduser("~")
    db_path = os.path.join(home, ".workbuddy", "workbuddy.db")
    if os.path.exists(db_path):
        return db_path
    raise FileNotFoundError(f"workbuddy.db not found: {db_path}")


def get_db_workspaces(db_path):
    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT w.path, w.last_opened_at,
               COUNT(CASE WHEN s.deleted_at IS NULL THEN 1 END) as active,
               MAX(s.created_at) as last_session
        FROM workspaces w
        LEFT JOIN sessions s ON s.cwd = w.path
        GROUP BY w.path ORDER BY w.path
    """).fetchall()
    conn.close()
    return rows


def get_disk_workspaces():
    result = []
    for d in os.listdir(WORKBUDDY_ROOT):
        full = os.path.join(WORKBUDDY_ROOT, d)
        wb = os.path.join(full, ".workbuddy")
        if os.path.isdir(full) and os.path.isdir(wb):
            result.append(full)
    return sorted(result)


def read_ai_section():
    """Read the AI-written section of HANDOFF.md (kept, never overwritten)."""
    if not os.path.exists(HANDOFF_FILE):
        return None
    with open(HANDOFF_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    idx = content.find(DELIM_MID)
    if idx == -1:
        return content  # no section marker: keep the whole file
    return content[idx:]


def update_secret(new_secret):
    """
    Update the sync passphrase (writes it into several files).
    Called by the AI when generating the handoff sheet.
    """
    print(f"🔐 Updating sync passphrase to: {new_secret}")

    # 1. Update the machine-generated section of HANDOFF.md
    if os.path.exists(HANDOFF_FILE):
        with open(HANDOFF_FILE, 'r', encoding='utf-8') as f:
            content = f.read()

        # Replace the passphrase line.
        # NOTE: the 暗号 ("passphrase") pattern below is FUNCTIONAL — it matches the
        # existing on-disk HANDOFF.md format shared across devices. Do NOT translate.
        pattern = r'> \*\*暗号：.*?\*\*'
        replacement = f'> **暗号：{new_secret}**'
        new_content = re.sub(pattern, replacement, content)

        if new_content != content:
            with open(HANDOFF_FILE, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"  ✅ HANDOFF.md passphrase updated")
        else:
            print(f"  ⚠️ HANDOFF.md passphrase unchanged (may already be up to date)")

    # 2. Update secret.txt (plain-text backup)
    os.makedirs(HANDOFF_DIR, exist_ok=True)
    with open(SECRET_FILE, 'w', encoding='utf-8') as f:
        f.write(f"# Sync verification passphrase backup\n\n")
        f.write(f"**Last updated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        # NOTE: "**当前暗号**:" ("current passphrase") is FUNCTIONAL — verify_sync()
        # reads it back from on-disk secret.txt files with a regex. Do NOT translate.
        f.write(f"**当前暗号**: {new_secret}\n\n")
        f.write(f"**How to verify**: \n")
        f.write(f"1. Read this file and confirm the passphrase matches\n")
        f.write(f"2. If it does not match, sync has failed; manually refresh the WPS cloud drive\n\n")
        f.write(f"**Historical passphrases**:\n")
        # NOTE: the lines below are historical passphrase VALUES (functional data) — kept verbatim.
        f.write(f"- 端午安康 (on or before 2026-06-18)\n")
        f.write(f"- 我不爱吃榴莲 (updated sometime on 2026-06-25)\n")
        f.write(f"- 🍑 我喜欢吃水蜜桃！ (2026-06-25 18:30)\n")
        f.write(f"- {new_secret} (current)\n")
    print(f"  ✅ secret.txt passphrase updated")

    # 3. Update AI_HANDOFF_GUIDE.md
    guide_file = os.path.join(HANDOFF_DIR, "AI_HANDOFF_GUIDE.md")
    if os.path.exists(guide_file):
        with open(guide_file, 'r', encoding='utf-8') as f:
            guide_content = f.read()

        # Replace the passphrase-check note.
        # NOTE: FUNCTIONAL pattern — matches the existing Chinese wording in
        # AI_HANDOFF_GUIDE.md on disk. Do NOT translate.
        pattern = r'检查同步暗号（.*?）'
        replacement = f'检查同步暗号（{new_secret}）'
        new_guide = re.sub(pattern, replacement, guide_content)

        if new_guide != guide_content:
            with open(guide_file, 'w', encoding='utf-8') as f:
                f.write(new_guide)
            print(f"  ✅ AI_HANDOFF_GUIDE.md passphrase updated")

    print(f"\n✅ Passphrase synced to 3 files; cross-device verification is reliable")
    return True


def verify_sync():
    """
    Verify sync status: check that the passphrases match.
    Called by the AI when pulling the sync.
    """
    print("=" * 50)
    print("[Verify] Sync verification")
    print("=" * 50)

    # Read secret.txt
    secret_phrase = "(not found)"
    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        # Functional pattern: matches the "**当前暗号**:" line written by update_secret().
        match = re.search(r'\*\*当前暗号\*\*: (.*)', content)
        if match:
            secret_phrase = match.group(1)

    # Read HANDOFF.md
    handoff_phrase = "(not found)"
    if os.path.exists(HANDOFF_FILE):
        with open(HANDOFF_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        # Functional pattern: matches the "> **暗号：...**" line in HANDOFF.md.
        match = re.search(r'> \*\*暗号：(.*?)\*\*', content)
        if match:
            handoff_phrase = match.group(1)

    print(f"  secret.txt passphrase: {secret_phrase}")
    print(f"  HANDOFF.md passphrase: {handoff_phrase}")

    if secret_phrase == handoff_phrase and secret_phrase != "(not found)":
        print("\n  [OK] Passphrases match — sync is healthy!")
        return True
    else:
        print("\n  [WARN] Passphrases differ — WPS may not have finished syncing yet")
        print("     Suggestion: manually refresh the WPS cloud drive, or wait a few minutes and retry")
        return False


def generate_handoff(db_path, secret_phrase="我是你爸爸"):
    # NOTE: the default secret_phrase above is a passphrase VALUE (functional data) — do not translate.
    """Generate the machine-generated section, keeping the AI-written section."""
    os.makedirs(HANDOFF_DIR, exist_ok=True)
    os.makedirs(CONVERSATIONS_DIR, exist_ok=True)

    conn = sqlite3.connect(db_path)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    computer = os.environ.get('COMPUTERNAME', 'Unknown')

    # Workspace data
    db_ws = get_db_workspaces(db_path)

    # Build the machine-generated section.
    # NOTE: the HTML comment marker below is part of the on-disk HANDOFF.md format
    # (mirrors DELIM_START) and the "> **暗号：...**" passphrase line format is matched
    # by update_secret()/verify_sync() regexes — FUNCTIONAL literals, do NOT translate.
    ws_rows = []
    for path, last_op, active, last_session in db_ws:
        name = os.path.basename(path)
        if last_op and last_op > 0 and last_op < 9999999999999:
            ts = time.strftime('%Y-%m-%d', time.localtime(last_op / 1000))
        elif last_session and last_session > 0:
            ts = time.strftime('%Y-%m-%d', time.localtime(last_session / 1000))
        else:
            ts = 'unknown'
        ws_rows.append(f"| {name} | {active} | {ts} |")

    ws_table = '\n'.join(ws_rows) if ws_rows else '| (none) | - | - |'

    machine_section = f"""# 🔄 Cross-Device Handoff

> **Last updated**: {now} | **Computer**: {computer} | **User**: Xiaobai

---

<!-- ⚙️ 以下为机器生成区，workspace_sync.py 自动更新，AI 请勿手改 -->

## 📂 Active Workspaces

| Workspace | Sessions | Last activity |
|--------|--------|----------|
{ws_table}

## 🧪 Sync Link Check

> **暗号：{secret_phrase}** ← If you can read this on the other computer, HANDOFF.md cross-device sync is working ✅

---

"""

    # Read the existing AI-written section
    ai_section = read_ai_section()
    if ai_section and DELIM_MID in ai_section:
        pass  # keep existing content
    elif ai_section:
        # First time creating the AI-written section (old-format file)
        ai_section = f"""{DELIM_MID}, workspace_sync.py will not overwrite this; the AI maintains it manually -->

## 📋 Task Progress

### 🏗 Cross-device sync system
- **Status**: core infrastructure done
- [ ] Real-world testing

### 🎴 "Dream Postman" e-commerce project
- **Status**: pending restart
- [ ] Market research
- [ ] Indiegogo crowdfunding
- [ ] B2C independent site
- [ ] B2B back office

---

## 💬 Recent conversation summaries

*(none yet; the AI writes these at the end of sessions)*

---

## 📎 Exported conversations

*(none yet)*

---

## ⚠️ Switching computers

1. Close WorkBuddy → wait 5 seconds → confirm no processes remain
2. Open WorkBuddy on the other computer
3. Tell the AI: **"Pull the sync and check the handoff"**

---

*This file is shared across devices via the `C:\\WorkBuddy` junction → WPS cloud drive*
"""
    else:
        # No existing file; create the initial template
        ai_section = f"""{DELIM_MID}, workspace_sync.py will not overwrite this; the AI maintains it manually -->

## 📋 Task Progress

*(the AI maintains this section during sessions)*

---

## 💬 Recent conversation summaries

*(none yet)*

---

## 📎 Exported conversations

*(none yet)*

---

## ⚠️ Switching computers

1. Close WorkBuddy → wait 5 seconds → confirm no processes remain
2. Open WorkBuddy on the other computer
3. Tell the AI: **"Pull the sync and check the handoff"**

---

*This file is shared across devices via the `C:\\WorkBuddy` junction → WPS cloud drive*
"""

    full_content = machine_section + ai_section

    with open(HANDOFF_FILE, 'w', encoding='utf-8') as f:
        f.write(full_content)

    conn.close()
    print(f"✅ Handoff sheet updated: {HANDOFF_FILE}")
    print(f"   → machine-generated section refreshed")
    print(f"   → AI-written section preserved")
    print(f"   → passphrase: {secret_phrase}")


def export_conversation_text(topic, text, source_computer=None):
    """
    Export a full conversation to _sync/conversations/.
    Called by the AI; users should not run it manually.
    """
    os.makedirs(CONVERSATIONS_DIR, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    safe_topic = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff_-]', '-', topic)[:40]
    filename = f"{date_str}-{safe_topic}.md"
    filepath = os.path.join(CONVERSATIONS_DIR, filename)

    computer = source_computer or os.environ.get('COMPUTERNAME', 'Unknown')

    content = f"""# {topic}

> Exported at: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Computer: {computer}

---

{text}
"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✅ Conversation exported: {filepath}")
    return filepath


def sync_all():
    db_path = find_db()

    conn = sqlite3.connect(db_path)

    disk = get_disk_workspaces()
    print(f"📂 Found {len(disk)} workspaces under C:\\WorkBuddy")

    existing = set(r[0] for r in conn.execute("SELECT path FROM workspaces").fetchall())
    added = 0
    now_ms = int(time.time() * 1000)

    for w in disk:
        if w not in existing:
            conn.execute("INSERT OR IGNORE INTO workspaces (path, last_opened_at) VALUES (?, ?)", (w, now_ms))
            added += 1
            print(f"  ➕ Added: {os.path.basename(w)}")

    conn.execute("UPDATE sessions SET deleted_at = NULL WHERE deleted_at IS NOT NULL AND cwd LIKE 'C:\\\\WorkBuddy\\\\%'")
    restored = conn.execute("SELECT changes()").fetchone()[0]

    conn.execute("UPDATE workspaces SET last_opened_at = ? WHERE last_opened_at = 0", (now_ms,))

    conn.commit()
    conn.close()

    print(f"\n📊 Result: +{added} workspaces, +{restored} sessions restored")

    generate_handoff(db_path)

    print("\n" + "=" * 50)
    print("⚠️  Notes:")
    print("  1. Fully quit WorkBuddy, then reopen it")
    print("  2. HANDOFF.md lives at C:\\WorkBuddy\\_sync\\")
    print("  3. The AI-written section will not be overwritten")
    print("  4. Conversations are exported to _sync/conversations/")


if __name__ == '__main__':
    import sys
    if '--handoff' in sys.argv:
        db_path = find_db()
        generate_handoff(db_path)
    elif '--export' in sys.argv and len(sys.argv) >= 4:
        # Usage: python workspace_sync.py --export "topic" "text content"
        topic = sys.argv[2]
        text = sys.argv[3]
        export_conversation_text(topic, text)
    elif '--update-secret' in sys.argv and len(sys.argv) >= 3:
        # Usage: python workspace_sync.py --update-secret "new passphrase"
        new_secret = sys.argv[2]
        update_secret(new_secret)
    elif '--verify' in sys.argv:
        # Usage: python workspace_sync.py --verify
        verify_sync()
    else:
        sync_all()
