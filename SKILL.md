---
name: cross-device-sync
description: |
  Configure WorkBuddy for seamless synchronization across multiple Windows computers
  via WPS cloud drive (金山文档/WPS云盘). This skill should be used when the user wants
  to set up cross-device sync, migrate WorkBuddy data to cloud storage, fix "workspace
  deleted or renamed" errors when switching between computers with different Windows
  usernames, or unify session paths across devices. Triggers include phrases like
  "cross-device sync", "跨设备同步", "sync WorkBuddy", "sync across computers",
  "can't open old tasks on another computer", "workspace renamed or deleted error".
agent_created: true
---

# Cross-Device Sync

## Overview

Set up WorkBuddy to sync cross-device through WPS cloud drive.

**Core insight**: `workbuddy.db` (SQLite) CANNOT be synced — two computers writing the same
database file will overwrite each other's conversation history. Instead, this skill sets up a
**hybrid architecture** where:

- **`workbuddy.db`** stays local on each computer (never synced, no overwrites)
- **Skills, scripts, memory, configs** sync via WPS cloud (symbolic links)
- **Workspace directories** (`C:\WorkBuddy\`) sync via Windows Junction
- **`workspace-state.json`** syncs via file symbolic link (tiny file, safe to share)
- **Cross-device task continuity** is handled via `HANDOFF.md` handoff notes, not db sync

This also addresses the core problem: each computer has a different `C:\Users\<name>` path,
which breaks session references when switching devices.

## Prerequisites

- WPS Office with cloud drive enabled, syncing to a known local folder
- Administrator access on both computers (required for creating Junctions)
- PowerShell 5.1+ on both computers

## Why This Skill Needs Elevated Access (for platform review)

This skill operates **entirely on the user's local machines** — no network calls,
no telemetry, no external services. The PowerShell scripts, Python daemons and
elevated operations exist for exactly these reasons:

| Operation | Why it is needed |
|-----------|------------------|
| Administrator / `New-Item -ItemType Junction` | Creates `C:\WorkBuddy` as a Junction pointing into the WPS cloud folder so both computers share one canonical workspace path (Windows username differs per machine) |
| `fix_db_isolation_v3.ps1` | Moves `workbuddy.db` (SQLite) OUT of the cloud-synced folder to a local dir — prevents two computers from overwriting each other's conversation DB. Read/modify local WorkBuddy app data only |
| `fix_workspace_state_sync.ps1` | Symlinks `workspace-state.json` (a few KB) so newly created workspaces appear in the other computer's sidebar |
| `scripts/fix_paths.py` | Rewrites stale `C:\Users\<old-name>` path references in the user's own session JSON / SQLite / caches after the path unification |
| `watch_sync.py` daemon | Local file watcher (stdlib only, polling mtime). Watches the user's own memory/handoff files and copies them into a transit folder when they change. Single-leader election via local heartbeat files avoids concurrent writes. No network I/O |
| `watchdog.bat` | Restarts the local daemon if it crashes or hangs (checks a local PID file and a liveness file). Runs at user logon via `shell:startup` |
| `secret.txt.example` | Template for a user-chosen sync passcode to verify both machines see the same shared folder. The real `secret.txt` is deliberately excluded from git and from the packaged zip (enforced by `package.py`) |

Nothing here reads credentials, browses the network, or modifies anything outside
the user's own WorkBuddy / WPS directories. All deletions (`clean_junk.py`) target
WPS conflict-copy files (`-副本*`) only, and only when a pristine original exists.

## Workflow

### Step 1: Identify Cloud Drive Path

The WPS cloud drive typically syncs to:

```
%USERPROFILE%\Documents\WPSDrive\<numeric_id>\WPS云盘\
```

Verify the exact path by checking the WPS cloud drive settings (gear icon > cloud disk cache location).
The `<numeric_id>` varies per account — common values are `358659758`, but confirm on each machine.

On each computer, note the full paths:
- Cloud drive root: `C:\Users\<username>\Documents\WPSDrive\<id>\WPS云盘\`
- Target WorkBuddy location on cloud: `<cloud_root>\.workbuddy\`
- Target workspace location on cloud: `<cloud_root>\WorkBuddy\`

### Step 2: Migrate .workbuddy to Hybrid Architecture (BOTH Computers)

> ⚠️ This step REPLACES the old "symlink .workbuddy to cloud" approach.
> The old approach caused `workbuddy.db` to be shared and overwritten between computers.
> The new approach keeps the db local and only syncs subdirectories.

**On EACH computer**, run `fix_db_isolation_v3.ps1`:

1. **Close WorkBuddy completely** (right-click tray icon → exit)
2. Find the script in the project workspace (synced via `C:\WorkBuddy` Junction):
   ```
   C:\WorkBuddy\<project>\fix_db_isolation_v3.ps1
   ```
3. Right-click → "Run with PowerShell"
4. Wait for "修复完成"

What the script does:
- Detects if `.workbuddy` is a symlink → removes it, creates a real local directory
- Copies all subdirectories to WPS cloud (if not already there)
- Creates symbolic links for each subdirectory: local → WPS cloud
- Keeps `workbuddy.db` / `workbuddy.db-wal` / `workbuddy.db-shm` local (not synced)
- Preserves the old symlink as `.workbuddy.bak` backup

Resulting architecture:
```
C:\Users\<user>\.workbuddy\          ← LOCAL real directory
  ├── workbuddy.db                  ← LOCAL (never synced)
  ├── workbuddy.db-wal              ← LOCAL
  ├── workspace-state.json  → WPS   ← SYMLINK (synced)
  ├── skills/               → WPS   ← SYMLINK (synced)
  ├── scripts/              → WPS   ← SYMLINK (synced)
  ├── blobs/                → WPS   ← SYMLINK (synced)
  ├── memory/               → WPS   ← SYMLINK (synced)
  └── ...all other dirs...  → WPS   ← SYMLINK (synced)
```

### Step 2b: Sync workspace-state.json (BOTH Computers)

After running the v3 script, `workspace-state.json` may still be a local file.
To sync the workspace sidebar list across devices, make it a symlink too:

On **each computer**, run `fix_workspace_state_sync.ps1`:
1. Find in the project workspace: `C:\WorkBuddy\<project>\fix_workspace_state_sync.ps1`
2. Right-click → "Run with PowerShell" (no need to close WorkBuddy)
3. Wait for "修复完成"

This creates:
```
C:\Users\<user>\.workbuddy\workspace-state.json  →  WPS云盘\.workbuddy\workspace-state.json
```

Now when you create a new workspace on one computer, it appears in the sidebar on the other.

### Step 3: Unify Workspace Paths via C:\WorkBuddy Junction

WorkBuddy session files reference workspace directories by absolute path. Different computers
have different user names (`C:\Users\James Ting\...` vs `C:\Users\62588\...`). To solve this,
create a `C:\WorkBuddy` Junction pointing to a cloud-synced workspace directory.

**On EACH computer**, run as Administrator in PowerShell:

1. Move workspace directories into the cloud drive:
   ```powershell
   robocopy "$env:USERPROFILE\WorkBuddy" "$env:USERPROFILE\Documents\WPSDrive\<id>\WPS云盘\WorkBuddy" /E /COPYALL /MT:4 /R:1 /W:1
   ```

   > **IMPORTANT**: Use `/E` (not `/MIR`). `/MIR` would delete existing cloud files from other computers.

2. Create the Junction:
   ```powershell
   New-Item -ItemType Junction -Path "C:\WorkBuddy" -Target "$env:USERPROFILE\Documents\WPSDrive\<id>\WPS云盘\WorkBuddy"
   ```

### Step 4: Fix Session Paths

Run the bundled fix script to unify all session paths in both JSON files and the database:

```bash
python scripts/fix_paths.py
```

This script handles 4 fix steps:

1. **Session JSON files** — replaces `C:\Users\<name>\WorkBuddy` with `C:\WorkBuddy`
   in `.workbuddy/sessions/*.json`
2. **SQLite database** — updates the `sessions` table cwd column to use unified paths
3. **Project cache merge** — merges old `c-Users-*-WorkBuddy-*` caches into
   `c-WorkBuddy-*` (prevents "conversation messages disappearing" after migration)
4. **JSONL cwd fields** — fixes the `cwd` field inside every message in
   `.workbuddy/projects/c-WorkBuddy-*/*.jsonl` files. This is CRITICAL for
   cross-device compatibility: if JSONL messages still contain user-specific
   paths, they may not render correctly when opened from another computer.
   Also normalizes lowercase `c:` to uppercase `C:`.

Reports which files were fixed and verifies directory accessibility.

After running, restart WorkBuddy on both computers. Old sessions should now open correctly.

### Step 5: Close WorkBuddy Before Switching Computers

**IMPORTANT**: Before leaving one computer and going to another, close WorkBuddy completely.

Even though `workbuddy.db` is now local (not synced), WorkBuddy uses SQLite WAL mode
(`workbuddy.db-wal`). Uncommitted WAL data won't be written to the main `.db` until
WorkBuddy exits. If you force-quit or the computer crashes, you may lose the latest
session data.

Also, the WPS cloud drive sync client may lock files that WorkBuddy is actively writing,
causing sync conflicts for skills/scripts/memory directories.

**How to close properly:**
1. Close all WorkBuddy windows
2. Wait 5 seconds for WAL checkpoint
3. Verify no `WorkBuddy.exe` processes remain:
   ```powershell
   tasklist | findstr WorkBuddy
   ```
   Should return nothing.
4. Check that `workbuddy.db-wal` file is gone or very small
5. Only then leave the computer

### Step 6: Cross-Device Task Continuity (HANDOFF.md) — MANDATORY

Since conversations are NOT synced between computers (each has its own local `workbuddy.db`),
use handoff notes to pass task context between devices.

**The HANDOFF.md file lives at**: `C:\WorkBuddy\_sync\HANDOFF.md`

> 📌 **Architecture note (v6 correction, 2026-08)**: the v3.2 claim that "Junction live-sync is
> broken" was a **misdiagnosis**. `C:\WorkBuddy` (WPS Junction) IS the primary always-on sync
> channel — the whole tree including hidden `.workbuddy` dirs syncs automatically. What actually
> happened in July: WPS sync latency + AI forgetting to write logs were mistaken for a broken
> link. Current architecture is **three layers, each with a job**:
>
> 1. **Primary**: WPS Junction auto-sync of `C:\WorkBuddy` (workspace files + memory)
> 2. **Transit fallback**: `sync_identity.py` via `_sync\identity\` — precise control, forced
>    push/pull, conflict-copy cleanup, protection against WPS laziness
> 3. **Daemon**: `watch_sync.py` v2.2 (single-leader) auto-triggers transit pushes ~1-2s after
>    file changes; self-heals crashes AND blocked/hung states; kept alive by `watchdog.bat` v2
>
> HANDOFF.md itself lives on the WPS-shared path AND is mirrored through the transit channel.

---

#### HANDOFF.md v2 Structure (machine section + AI section)

The file has two sections separated by HTML comments:

```
# 跨设备交接单
...

<!-- ⚙️ 以下为机器生成区，workspace_sync.py 自动更新，AI 请勿手改 -->
## 📂 活跃工作区
## 🧪 同步链路检测
<!-- ✅ 以下为 AI 手写区，workspace_sync.py 不会覆盖，AI 自行维护 -->
## 📋 任务进度
## 💬 近期对话摘要
## 📎 导出对话
```

- **Machine section** (`⚙️` → `✅`): Auto-updated by `workspace_sync.py`, contains workspace list and test passcodes. AI must NOT edit this section.
- **AI section** (`✅` → end): Maintained by the AI. Update task progress, conversation summaries, and exported conversations here.

---

#### ⚠️ CRITICAL — For the AI (BOTH computers must follow this):

**When the user switches computers and says anything about "同步", "拉取", "接续", "继续", "看交接单":**

1. **FIRST ACTION (before ANY reply about task status)**: Read `C:\WorkBuddy\_sync\HANDOFF.md`
2. If the file exists and contains content → read it, tell the user what you found
3. If the file is missing or empty → say "交接单为空，可能上一台电脑没有生成" and ask what to do
4. **NEVER** rely on your own conversation memory to guess what the other AI did
5. **NEVER** say "已经同步好了" without first reading HANDOFF.md — you DON'T know until you read it

**Why this is mandatory**: Each computer's AI has its own conversation history (separate `workbuddy.db`).
The ONLY way to know what happened on the other computer is through HANDOFF.md.
Without reading it, you are BLIND to the other computer's work.

---

#### ⚠️ MANDATORY: Update HANDOFF.md After EVERY Substantive Work Session

**This is the rule that was missing — and why cross-device sync kept breaking.**

After completing ANY substantive work (generating files, making decisions, fixing bugs, creating reports,
writing code, designing assets, etc.), the AI MUST update `C:\WorkBuddy\_sync\HANDOFF.md`:

1. Read the current `C:\WorkBuddy\_sync\HANDOFF.md` file
2. Update the AI section (`✅` → end of file) with:
   - What was accomplished in this session (project, files created, key decisions)
   - What the current status is (e.g., "GDD v0.3 complete, ready for review")
   - What the next steps are (e.g., "待对方确认后推进众筹页面设计")
3. Write the updated file

**Triggers** (any of these = MUST update HANDOFF.md):
- User says "生成交接单" / "写交接单" / "更新交接单" / "同步" / "记得写交接单"
- Session is ending and substantive work was done
- User is about to switch computers (explicitly or implicitly)
- Any multi-step task (8+ tool calls) has been completed
- The AI detects that "important decisions were made this session"

**Do NOT wait for the user to remind you.** If you did real work, update HANDOFF.md.

**What to include** (key = the other AI needs to understand what happened WITHOUT asking):
- Date/time and computer name
- Which project(s) were worked on
- Specific files created/modified with paths
- Key decisions and their rationale
- Current blockers or questions
- Explicit next steps

---

**Leaving a computer** — say "生成交接单" to create/update `C:\WorkBuddy\_sync\HANDOFF.md`,
recording what was done, what's next, key decisions, and any test messages the user wants to verify.

When generating HANDOFF.md, ALWAYS include:
- Current date/time and computer name
- Active projects and their status
- Key decisions made in this session
- Explicit next steps for the other computer
- Any test messages the user asks to include

**Arriving at a computer** — as the AI, your FIRST tool call MUST be `Read` on `C:\WorkBuddy\_sync\HANDOFF.md`.
Then tell the user what the other computer's AI left for them.

The `sync-task` skill (installed alongside this skill) implements this workflow automatically.
If `sync-task` is loaded, it handles the read/generate cycle.

### Step 6b: Ongoing Sync — three layers (v6)

The primary sync is the **WPS Junction itself** (auto, always on). The transit channel adds
precise control and cleanup. Two mechanisms on top:

1. **Daemon (recommended, hands-off)** — `watch_sync.py` v2.2 runs at startup (via `watchdog.bat`
   in `shell:startup`). It watches **SOURCE files only** (user-level memory, per-workspace memory,
   HANDOFF.md / secret.txt / AI_HANDOFF_GUIDE.md) and auto-pushes to the transit dir on change
   (~1-2s latency). A **single-leader election** (per-machine heartbeat file) ensures only ONE
   active machine writes the transit dir at a time — this is what ended the `-副本` conflict
   storm. It deliberately does NOT watch the transit dir itself, preventing
   download→push→download loops. Machine-independent (`sys.executable`), safe to run on both
   computers simultaneously.

   **Self-healing (v2.1)**: process-level try/except (never exits), consecutive-failure counter
   with baseline rebuild + fallback pull, protected heartbeat thread, PID file.
   **Hang-healing (v2.2)**: all subprocess calls use `-S` (skips sitecustomize hijack of
   unlink/rmtree on WPS paths — the root cause of a week-long silent hang); the main loop
   refreshes `liveness_<machine>.txt` every scan. `watchdog.bat` v2 restarts the daemon if the
   PID dies **or** liveness is older than 240s (blocked). Use the matched v2 watchdog — an
   old PID-only watchdog cannot detect a hung process.

2. **Manual push/pull (fallback)** — run `sync_identity.py push` before leaving a computer, and
   `sync_identity.py pull` after arriving at the other. `.bat` wrappers: `push.bat`, `pull.bat`,
   `一键同步.bat`.

The transit directory is `C:\WorkBuddy\_sync\identity\`. `find_junk.py` / `clean_junk.py` clean
up any `-副本` conflict files that slip through. `sync_identity.py` v3.6 **only transits
`YYYY-MM-DD.md` daily logs** — project identity files (MEMORY.md/STATUS.md/...) stay
workspace-local to prevent cross-workspace overwrite pollution (7/24 & 7/30 incidents).

> ⚠️ `_sync` is not in the daemon's watch list — script upgrades (watch_sync.py / watchdog.bat)
> must be **manually copied** to the other machine.

#### Workspace-Level STATUS.md (2026-06-25 — fills the "old workspace blind spot")

In addition to the global HANDOFF.md, each workspace now has its own status file:
`.workbuddy/memory/STATUS.md`

This solves two critical blind spots:
1. **Returning to an old workspace** (e.g. worked on Project A on 5/20, came back on 6/5) — the AI reads STATUS.md and knows exactly where things were left off
2. **New conversation in same workspace** (e.g. conversation A did image processing, conversation B continues GDD) — new conversation's AI reads STATUS.md and picks up where A left off

**When entering a workspace**: AI reads STATUS.md → MEMORY.md → recent daily logs (rules in sync-task skill)
**When leaving a workspace**: AI updates STATUS.md with latest progress (rules in sync-task skill)

STATUS.md format is lightweight — project goal, latest progress, current todos, recent conversation summary, key file paths. See `sync-task` skill for the full read/write protocol.

### Step 7: Verify

On each computer:
1. Open WorkBuddy
2. Check that the sidebar shows the same workspaces (via synced `workspace-state.json`)
3. Click on a workspace — it should open normally (work files synced via Junction)
4. Say "同步任务" to test handoff note generation
5. Say "继续上次" on the other computer to verify task continuity

**Note**: Conversations from one computer will NOT appear on the other (by design).
This is intentional — the `workbuddy.db` is per-computer to prevent overwrite conflicts.

## Advanced: Session Recovery

When a session's complete message cache (`.jsonl`) is lost but cloud summaries exist:

### Recovery via Cloud Summaries

1. Call `conversation_search` to retrieve cloud summaries of the lost conversation
2. Check the project directory (e.g. `C:\WorkBuddy\2026-06-01-10-12-31\`) for surviving output documents
3. Run the recovery script to rebuild a proper cache:
   ```bash
   python scripts/restore_and_merge.py restore <session_id> <project_dir>
   ```

### Critical JSONL Format Requirements

Restored messages MUST follow the exact WorkBuddy format. Missing any field = message invisible:

```json
{
  "id": "<uuid>",
  "type": "message",
  "role": "user|assistant",
  "sessionId": "<session_uuid>",
  "cwd": "C:\\WorkBuddy\\<project>",
  "content": [
    {"type": "input_text", "text": "..."}
  ],
  "providerData": {},
  "timestamp": <unix_ms>,
  "parentId": "<prev_message_id>"
}
```

Key pitfalls:
- `cwd` MUST use backslashes `C:\...` — forward slashes cause path mismatch
- `sessionId` uses camelCase (not `session_id`)
- `content` is an array of `{type, text}` objects (not plain string)
- `providerData` must be present: `{}` for user, `{"agent":"cli"}` for assistant
- `timestamp` is milliseconds since epoch — ensure correct YEAR

### Critical DB Field Requirements

When registering a restored session in the database:

- `user_id` MUST match the actual user UUID (e.g. `f205e23a-...`), NOT `"default"`
- `cwd` MUST use backslash path separators
- `created_at` and `last_activity_at` are in **milliseconds** (not seconds)

> Retrieve the correct `user_id` by querying any existing session first.

## Advanced: Session Merging

Merge multiple related sessions into one to consolidate scattered discussions:

### Merge via Script

```bash
python scripts/restore_and_merge.py merge <source_id> <target_id>
```

This handles:
1. **Deduplication** by message ID — shared messages (e.g. file-history-snapshot) won't duplicate
2. **Timestamp sorting** — all messages sorted chronologically after merge
3. **Time gap padding** — merged messages get minimum 60s gaps to avoid collisions
4. **Pre-merge backup** — cached in `_merge_backup_<timestamp>/`
5. **Source soft-delete** — source session marked deleted in DB, disappears from sidebar

### Manual Merge Checklist

If doing manually, verify after merge:
- Total messages = target lines + (source lines - duplicates)
- Time ordering: older content appears before newer
- Non-duplicated source messages have correct `sessionId` (must match target!)
- Source session is soft-deleted in DB

## Known Limitations

### Archived Sessions

WorkBuddy currently has **NO UI filter for archived sessions**. The sidebar filter only shows:
进行中 | 已完成 | 失败 | 待处理 | 规划中 | 全部状态

Once a session is archived (status=archived in DB), it becomes invisible in the UI.
To recover: manually change `status` back to `"working"` or `"completed"` in the database:

```sql
UPDATE sessions SET status = 'completed' WHERE id = '<session_id>';
```

### Timestamp "Year Bug"

Restored messages with incorrect timestamps (wrong year) will:
- Show as implausible dates in the UI (e.g. "56年前")
- May be filtered out entirely by WorkBuddy's rendering logic

When restoring, always verify timestamps fall in the expected date range.
A year offset of +31536000000ms (365 days in ms) is the typical fix when the
wrong year was used.

### Deliver Attachments & Symlink Paths

After setting up cross-device sync, `deliver_attachments` may silently fail for files
under `~/.workbuddy/` because that directory is now a symlink to WPS cloud.
WorkBuddy's attachment delivery resolves symlinks differently from native paths.

**Workaround**: Copy files to the current workspace (`C:\WorkBuddy\<project>\`)
before calling `deliver_attachments`. Files under `C:\WorkBuddy\` (a Junction, not
a symlink) resolve correctly.

```python
# Before delivering, copy to workspace:
import shutil
workspace = 'C:/WorkBuddy/<project>/'
shutil.copy(file_path, workspace + 'filename.md')
# Then deliver from workspace path
```

### Automation Path Drift

Automations (scheduled tasks like "下班自动存档") store a hardcoded `cwds` field
and may reference workspace paths in their `prompt` text. After path migration
or when the active workspace changes (new conversation = new timestamp-based dir),
automations silently point at the **old workspace** — they will run but write to
the wrong directory, or fail because the old workspace no longer exists.

**Symptoms**:
- Automation runs but output files appear in an old workspace
- Automation shows dates from weeks ago ("5月30号")
- `DAILY_STATUS.md` never updates in the current workspace

**Root cause**: Automations are **bound to the session** in which they were created.
Updating `cwds` and `prompt` is NOT sufficient — the automation runner still
executes in the original session's context and writes to the original workspace.

**Only reliable fix: DELETE + RECREATE**:

```
# 1. Delete old automations
automation_update(mode="delete", id="automation-OLDID")

# 2. Recreate in current session
automation_update(mode="create", name="...", cwds="C:\\WorkBuddy\\CURRENT-WS", ...)
```

**Prompt path best practice**: Use relative paths like `.workbuddy/memory/`
instead of absolute paths like `C:\\WorkBuddy\\2026-06-03\\...`. This way
when you recreate in a new session, the prompt text doesn't need rewriting.

**Prevention**: After starting a new "main" conversation, delete and recreate
all automations in that session. Do NOT rely on `automation_update(mode="update")`
to change workspace binding — it doesn't work.

## Troubleshooting

### Conversations being overwritten between computers

**Symptoms**: Company computer conversations disappear after syncing; home computer conversations appear on the company computer instead.

**Cause**: `workbuddy.db` is being shared/synced via WPS cloud drive. Two computers writing the same SQLite database file will overwrite each other.

**Fix**: Run `fix_db_isolation_v3.ps1` on BOTH computers. This converts `.workbuddy` from a cloud-synced symlink to a local real directory, keeping `workbuddy.db` local and only syncing subdirectories.

### New workspaces not appearing on other computer

**Symptoms**: Created a new workspace on one computer, but the other computer's sidebar doesn't show it.

**Cause**: `workspace-state.json` is a local file (not synced).

**Fix**: Run `fix_workspace_state_sync.ps1` on both computers. This creates a file symbolic link so `workspace-state.json` is stored in WPS cloud and synced automatically.

### Diagnostic Script

Use `home_check.py` (or `final_check.py` on the primary computer) for a full system audit:

```bash
python home_check.py
```

Checks: symlink targets, Junction targets, workspace-state.json, DB integrity, active/deleted sessions, timestamps, path formats, WAL files, and .jsonl consistency.

### Post-Setup Verification Checklist

Run this after initial setup or whenever something seems off:

```
# 1. .workbuddy is a local real directory (NOT a symlink to cloud)?
ls -la ~/.workbuddy   # should be drwxr-xr-x, NOT lrwxrwxrwx -> WPS

# 2. workbuddy.db is local?
python -c "import os; p=os.path.expanduser('~/.workbuddy/workbuddy.db'); print('OK' if os.path.exists(p) and not os.path.islink(p) else 'PROBLEM')"

# 3. Subdirectories are symlinked to WPS cloud?
ls -la ~/.workbuddy/skills   # should show -> ...WPS云盘/.workbuddy/skills

# 4. workspace-state.json is a symlink?
python -c "import os; p=os.path.expanduser('~/.workbuddy/workspace-state.json'); print('SYNCED' if os.path.islink(p) else 'LOCAL ONLY')"

# 5. Junction intact?
cmd /c "dir C:\ /AL" | findstr WorkBuddy   # should show <JUNCTION>

# 6. DB paths unified?
sqlite3 ~/.workbuddy/workbuddy.db "SELECT COUNT(*) FROM sessions WHERE cwd LIKE '%Users%';"
# Should return 0

# 7. Each workspace has .workbuddy/memory/ marker?
ls -d C:/WorkBuddy/*/.workbuddy/memory/   # should list all workspaces
```

### "Workspace renamed or deleted" error persists

1. Verify the Junction exists: `cmd /c "dir C:\ /AL" | findstr WorkBuddy` should show `<JUNCTION>`
2. Verify the cloud drive is fully synced — WPS may show files as placeholders that haven't been downloaded. Right-click the WorkBuddy folder in WPS and select "Always keep on this device"
3. Verify project directories have `.workbuddy` subdirectories — each workspace needs `.workbuddy/memory/`
4. Re-run `scripts/fix_paths.py` and check the output for MISSING entries

### "Workspaces" sidebar shows fewer items than expected

WorkBuddy reads the workspace list from `workspace-state.json`, not directly from the database. If this file is empty or stale:

**Symptoms**: Database has 8 sessions but sidebar shows only 1 workspace.

**Fix**: Rebuild `workspace-state.json` from the database:

```python
import sqlite3, json, os

db = os.path.expanduser('~/.workbuddy/workbuddy.db')
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute('SELECT DISTINCT cwd FROM sessions WHERE deleted_at IS NULL')
workspaces = [{'path': r[0], 'lastOpenedAt': 0} for r in cur.fetchall()]
conn.close()

state = {'version': 1, 'workspaces': workspaces}
with open(os.path.expanduser('~/.workbuddy/workspace-state.json'), 'w', encoding='utf-8') as f:
    json.dump(state, f, indent=2, ensure_ascii=False)
```

Restart WorkBuddy after rebuilding.

### Sessions appear in DB but not in sidebar (soft-deleted)

**Symptoms**: `SELECT COUNT(*) FROM sessions` returns 10, but sidebar shows fewer.

**Check**: Some sessions may have `deleted_at IS NOT NULL` (soft-deleted by WorkBuddy client during sync).

**Fix**:
```sql
UPDATE sessions SET deleted_at = NULL WHERE deleted_at IS NOT NULL;
```

Then rebuild `workspace-state.json` (see above) and restart WorkBuddy.

### Missing `.workbuddy` marker in workspace directories

**Symptoms**: A workspace directory exists in `C:\WorkBuddy\` but doesn't appear in the sidebar, even though the database and `workspace-state.json` are correct.

**Cause**: WorkBuddy requires a `.workbuddy\` subdirectory (even empty) inside each workspace directory to recognize it as a valid workspace.

**Fix**:
```powershell
New-Item -ItemType Directory -Path "C:\WorkBuddy\<project>\.workbuddy\memory" -Force
```

### Path slash inconsistency (`C:/` vs `C:\`)

**Symptoms**: Sessions restored on one computer don't appear on another, or messages render incorrectly.

**Cause**: Forward slashes (`C:/WorkBuddy/...`) in `cwd` fields cause path mismatch on Windows.

**Fix**: All `cwd` fields (in DB and JSONL) MUST use backslashes:
```python
# Fix all forward slashes in DB
cur.execute("UPDATE sessions SET cwd = REPLACE(cwd, '/', '\\\\') WHERE cwd LIKE 'C:/%'")
```

The `fix_paths.py` script includes this normalization step.

### "Conversation messages disappear" after path fix

This happens when `projects/` directory has BOTH `c-Users-*-WorkBuddy-*` and
`c-WorkBuddy-*` caches for the same workspace. WorkBuddy only loads the cache
matching the current cwd, leaving old messages "lost" in the old cache.

Re-run `scripts/fix_paths.py` — the script now includes Step 3 (merge project
caches) which merges all old caches into the new ones and renames orphaned caches.

### Symlink creation fails

If `New-Item -ItemType SymbolicLink` fails with permission errors:
- Ensure PowerShell is running as Administrator
- On Windows Home editions, symbolic links may require Developer Mode to be enabled

### Restored session not appearing in sidebar

Triple-check these three things (all must be correct):
1. **`user_id` in DB** — must match real user UUID, NOT `"default"`. Query any existing session to find it.
2. **`cwd` path separators** — must use backslashes (`C:\WorkBuddy\...`), NOT forward slashes.
3. **JSONL format** — verify `type`, `sessionId` (camelCase), `content` as array of `{type, text}`, `providerData` are all present.

### Restored content shows implausible dates / "56年前"

**Cause 1 (most common)**: `created_at` or `timestamp` was set to `0` (epoch 1970-01-01).

**Cause 2**: Seconds were used instead of milliseconds (value is 1000x too small, showing a date in 1970).

**Fix**:
```sql
-- Fix created_at = 0 (set from first JSONL message timestamp)
UPDATE sessions SET created_at = <correct_ms>, updated_at = <correct_ms>, last_activity_at = <correct_ms> WHERE created_at = 0;
```

For JSONL messages with wrong year, adjust by year offset:
- 365 days = 31536000000 ms
- 366 days = 31622400000 ms (leap year)

Always verify timestamps fall in the expected date range after restoration.

### Cloud drive path differs

If the WPS cloud drive path is different from the default, check WPS settings:
WPS app > Settings > Cloud Document > Cache Location

The pattern is always `%USERPROFILE%\Documents\WPSDrive\<id>\WPS云盘\` — only `<id>` varies.

## Resources

### sync_identity.py (v3.6)

Bidirectional **transit-channel** sync. Collects each workspace's `.workbuddy/memory/` into
`C:\WorkBuddy\_sync\identity\`, and distributes transit memory back to workspaces on pull.
Also syncs HANDOFF.md / identity files. v3.4+ auto-cleans WPS `-副本` conflict files and skips
any file containing "副本" to prevent sync storms; v3.5 sweeps junk before push.
**v3.6 (critical)**: only `YYYY-MM-DD.md` daily logs may enter the flat user-level namespace;
project identity files (MEMORY.md / STATUS.md / DAILY_STATUS.md / HOME_WRAPUP.md /
MORNING_BRIEF.md) are skipped — previously they collided across workspaces and "newest mtime
wins" merge fanned one workspace's content into ALL workspaces (two incidents: 7/24, 7/30,
14 workspaces polluted).

### watch_sync.py (v2.2)

Background daemon with single-leader election. Watches source files, auto-pushes on change
(~1-2s latency). Machine-independent (`sys.executable`), safe to run on both computers
simultaneously. v2.1 self-healing: never-exit main loop, failure-counter recovery, PID file.
v2.2 hang-healing: `-S` on all subprocess calls (defeats sitecustomize hijack of unlink/rmtree
on WPS paths), plus a `liveness_<machine>.txt` heartbeat refreshed every scan.

### watchdog.bat (v2)

Watchdog loop (30s interval). Restarts the daemon when its PID vanishes (crash/kill/reboot)
**or** when liveness is older than 240s (main loop blocked while PID alive). Restart command
uses `-S`. Put it (or a shortcut) in `shell:startup`. Must stay matched with watch_sync.py
v2.2 — an old PID-only watchdog cannot detect a hung daemon.

### find_junk.py / clean_junk.py

WPS conflict-copy scanner (generates an HTML report) and cleaner (only deletes copies that have a
pristine original). Use after a sync storm or whenever thousands of `-副本` files appear.

### workspace_sync.py (v3.0)

Mechanical sync: scans `C:\WorkBuddy` workspaces, regenerates the HANDOFF.md machine section
(leaving the AI-written section untouched), and assists with conversation export + sync passcode.

### scripts/fix_paths.py

Automated fix script that unifies session paths across JSON files and SQLite database.
Run this after setting up Junctions on all computers. It auto-detects the `.workbuddy`
location (handles symlinks) and user-specific paths to replace.

### scripts/restore_and_merge.py

Session recovery and merging tool. Two modes:

**Restore**: Rebuild a lost session's JSONL cache from structured data.
Requires correct `user_id`, backslash cwd, and proper JSONL format.
Use this when cloud summaries exist but local message cache is gone.

**Merge**: Combine two sessions into one with deduplication, timestamp sorting,
and source soft-deletion. Backs up target before merging.
