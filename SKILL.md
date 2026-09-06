---
name: cross-device-sync
slug: cross-device-sync
displayName: Cross-Device Sync for WorkBuddy
version: "6.3.8"
summary: Seamless WorkBuddy sync across Windows PCs (WPS cloud drive + handoff notes + auto daemon)
license: MIT
tags:
  - workbuddy
  - codebuddy
  - cross-device-sync
  - wps-cloud
  - windows
description: |
  Configure WorkBuddy for seamless synchronization across multiple Windows computers
  via WPS cloud drive (WPS). This skill should be used when the user wants
  to set up cross-device sync, migrate WorkBuddy data to cloud storage, fix "workspace
  deleted or renamed" errors when switching between computers with different Windows
  usernames, or unify session paths across devices. Triggers include phrases like
  "cross-device sync", "sync WorkBuddy", "sync across computers",
  "can't open old tasks on another computer", "workspace renamed or deleted error",
  "conversation history lost after update", "old chats disappeared after upgrading",
  "recover conversation history".
  One-time setup per computer (~15 min: Junction + DB isolation + path fix), then fully automatic.
agent_created: true
homepage: https://github.com/jamesting-eng/workbuddy-skills
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

## Emergency Persistence: 5.4.7 IndexedDB Loss Era SOP

> **When this applies**: User reports that conversation messages in
> WorkBuddy disappear after restart (the session sidebar still shows new
> sessions, but clicking into them shows no message body). This is the
> **WorkBuddy 5.4.7 IndexedDB regression** — introduced in build
> `5.4.7.37521366` (install-manifest generatedAt `2026-08-31T22:48:01`).
> The Chromium IndexedDB subsystem fails to initialize under `app/session`,
> so messages persist only in the renderer's memory and are lost on every
> WB restart. Other storage paths (`Local Storage`, `Session Storage`,
> `blob_storage`, `SharedStorage`) function normally — only IndexedDB is
> broken. The TIDB / `@tencent/ovb-indexed-db` storage backend silently
> falls back to in-memory storage. Diagnosis method and exclusion table:
> see `Reporting the Bug to WorkBuddy Official` at the bottom of this
chapter and the user's full bug-report markdown if attached.

### Why This Skill Is Still Your Best Tool

This skill is **disk-based by design** — `HANDOFF.md`, `MEMORY.md`,
`STATUS.md`, daily logs, and `sync_identity.py` all write to disk
out-of-band of IndexedDB. The 5.4.7 regression **does NOT break** the
cross-device sync architecture — in fact, this era makes the skill
**more critical** than usual:

- New WB sessions start with empty conversation context (chat history
  is gone)
- The only surviving context is what is on disk
- This skill's entire workflow IS that disk-based handoff

So: **do not deactivate this skill during 5.4.7 — activate it harder.**

### Mandatory Read Order at Session Start (5.4.7 era)

In addition to the normal "switch computer" workflow in Step 6, every
session (new conversation, restarted conversation, even same-machine
continuation) should begin with these reads in this exact order:

1. **`Read` `C:\WorkBuddy\_sync\HANDOFF.md`** — inter-machine handoff
2. **`Read` `<current workspace>/.workbuddy/memory/STATUS.md`** — workspace state
3. **`Read` `<current workspace>/.workbuddy/memory/YYYY-MM-DD.md`** (today + yesterday) — recent daily log
4. **`Read` `~/.workbuddy/MEMORY.md`** (if exists) — user-level long-term
5. **Then and only then** may you reply to the user

**Forbidden in 5.4.7 era**: any phrasing like "I remember we discussed…",
"as we agreed last time…", "based on what you told me…" that does NOT
come from one of the four reads above. If you have not read them, you
do not know — say so honestly.

### Mandatory Write Discipline (5.4.7 era)

Tighten the normal write rules (Step 6 already requires write-on-switch;
the 5.4.7 era requires write more often):

- **Every ~8 tool calls OR any decision affecting deliverables**:
  update current workspace's `STATUS.md` with: project goal / latest
  progress / current todos / recent conversation summary / key file paths.
- **End of every substantive work session** (even without switching
  computers): append today's `YYYY-MM-DD.md` with what was decided,
  what was created, what is blocked.
- **Any user-stated preference, hard constraint, or hard-coded value**
  in conversation → write to `STATUS.md` immediately. Do not rely on
  AI conversation memory.
- **Any reason to believe the WB conversation will lose content** (long
  session, complex multi-step task, before user mentions switching) →
  preemptively summarize to disk **before** responding.

### User-Facing Mitigations (5.4.7 era)

Until official fix:

- Close WB properly (right-click tray icon → Exit) so SQLite WAL
  checkpoints. Even IndexedDB-lost sessions still have updated row
  metadata in `workbuddy.db` (the list shows them, just the body is
  gone).
- Manually copy any critical conversation text into
  `<workspace>/.workbuddy/memory/YYYY-MM-DD.md` or an external file
  before closing WB.
- Disable auto-update in WB Settings (About -> Auto Update) — both to
  prevent being bumped onto future buggy builds and to prepare for
  the eventual 5.4.8 hotfix (you'll want to install it manually after
  it's vetted).
- Don't trust "the chat history remembers it" — always check disk.

### Recovery Workflow if a Session's Body Is Lost

When opening an apparently-empty session (list shows it, body is blank):

1. **`Read`** `workbuddy.db` sessions row for that session id → recover
   `cwd`, `created_at`, `last_activity_at` (intact even under 5.4.7).
2. **`Read`** `<cwd>/.workbuddy/memory/STATUS.md` → recent context.
3. **`Read`** `<cwd>/.workbuddy/memory/<that-day>.md` → that day's
   working log.
4. Reconstruct the conversation thread from those disk artifacts.
5. If critical content is recovered → paste into the session's JSONL
   via `scripts/restore_and_merge.py restore <session_id> <project_dir>`
   (see Advanced: Session Recovery), then restart WB.

**Never fabricate chat content.** If the disk artifacts don't tell you
what was said, say so honestly. The whole point of disk-based
persistence is that the truth lives on disk.

### Reporting the Bug to WorkBuddy Official

If the user wants to push back to WorkBuddy official:
- Recipient: `workbuddy_ai@tencent.com` (official bug-feedback channel; write the mail in Chinese)
- Subject: "[Bug] Conversation message persistence broken after the WorkBuddy 5.4.7 upgrade (IndexedDB subsystem not initialized)"
- Attach the bug-report markdown file (key sections are platform-independent)
- Expect 7 business days; do NOT mark P0 framing in body unless
  content loss is also blocking billing/legal/contract work

---

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
WPS conflict-copy files (`-副本*` — literal Chinese suffix, functional) only, and only when a pristine original exists.

## Workflow

### Step 1: Identify Cloud Drive Path

The WPS cloud drive typically syncs to:

```
%USERPROFILE%\Documents\WPSDrive\<numeric_id>\WPS云盘\
```

Verify the exact path by checking the WPS cloud drive settings (gear icon > cloud disk cache location).
The `<numeric_id>` varies per account — common values are `123456789`, but confirm on each machine.

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
4. Wait for the script's fix-completed message

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
3. Wait for the script's fix-completed message

This creates:
```
C:\Users\<user>\.workbuddy\workspace-state.json  →  WPS云盘\.workbuddy\workspace-state.json
```

Now when you create a new workspace on one computer, it appears in the sidebar on the other.

### Step 3: Unify Workspace Paths via C:\WorkBuddy Junction

WorkBuddy session files reference workspace directories by absolute path. Different computers
have different user names (`C:\Users\Alice\...` vs `C:\Users\Bob\...`). To solve this,
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

> NOTE: the marker lines inside this template are intentionally Chinese — they must match
> exactly what `workspace_sync.py` writes into the real HANDOFF.md. Do not translate them.

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

**When the user switches computers and says anything about syncing (spoken trigger phrases, in Chinese: "同步" sync / "拉取" pull / "接续" resume / "继续" continue / "看交接单" check the handoff):**

1. **FIRST ACTION (before ANY reply about task status)**: Read `C:\WorkBuddy\_sync\HANDOFF.md`
2. If the file exists and contains content → read it, tell the user what you found
3. If the file is missing or empty -> tell the user the handoff note is empty (the other computer may not have generated it yet) and ask what to do
4. **NEVER** rely on your own conversation memory to guess what the other AI did
5. **NEVER** claim "everything is already synced" without first reading HANDOFF.md — you DON'T know until you read it

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
   - What the next steps are
3. Write the updated file

**Triggers** (any of these = MUST update HANDOFF.md):
- User asks to generate/update the handoff note (spoken triggers, in Chinese: "生成交接单" / "写交接单" / "更新交接单" / "记得写交接单")
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

**Leaving a computer** — ask the AI to generate/update the handoff note at `C:\WorkBuddy\_sync\HANDOFF.md`,
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
   the one-click-sync launcher (`一键同步.bat` — actual filename on disk, kept in Chinese).

The transit directory is `C:\WorkBuddy\_sync\identity\`. `find_junk.py` / `clean_junk.py` clean
up any `-副本` conflict files that slip through (literal Chinese suffix, functional). `sync_identity.py` v3.6+ **only transits
`YYYY-MM-DD.md` daily logs** — project identity files (MEMORY.md/STATUS.md/...) stay
workspace-local to prevent cross-workspace overwrite pollution (7/24 & 7/30 incidents).
v3.7 disables write-back fan-out; v3.8 hard-bounds `memory/` to `.md` and purges stale IDE artifact-index URIs every cycle.

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
4. Trigger the sync-task skill to test handoff note generation
5. On the other computer, resume the last session to verify task continuity

**Note**: Conversations from one computer will NOT appear on the other (by design).
This is intentional — the `workbuddy.db` is per-computer to prevent overwrite conflicts.

## Recovering History "Lost" After 5.5.x Updates (Path Re-encoding)

**Symptom**: after upgrading WorkBuddy to 5.5.x, conversations older than a cutoff date
vanish from *some* workspaces, while workspaces untouched since the upgrade still show
their full history. Nothing was deleted — the bodies are still on disk.

**Root cause**: conversation bodies are stored per-session as JSONL at:

```
~/.workbuddy/projects/<encoded-cwd>/<session-uuid>.jsonl
```

The `<encoded-cwd>` directory name is derived from the workspace path. When the
`C:\WorkBuddy` junction is resolved to the real WPS cloud path (which 5.5.x started
doing), new messages are written into a *differently-encoded* sibling directory, e.g.:

```
c-WorkBuddy-2026-01-15-10-30-00                                          <- legacy
c-Users-Bob-WorkBuddy-2026-02-20-09-15-00                              <- legacy
C-Users-Bob-Documents-WPSDrive-...-WorkBuddy-2026-01-15-10-30-00 <- new (5.5.x)
```

The UI reads only the new directory, so everything written before the re-encoding looks
"lost". Untouched workspaces keep their legacy directory authoritative, so they display
fine. This is a *linking* failure, not data loss — no cloud restore, no WPS version
history, no official support ticket needed.

### Confirm this is your case

Pick an "affected" workspace, find its legacy `c-*-<workspace-suffix>` directory under
`~/.workbuddy/projects/`, and check that the `<uuid>.jsonl` files inside cover the
"missing" date range. If yes, recover. If no JSONL exists anywhere, fall back to the
Emergency Persistence SOP above instead.

### Recovery with scripts/recover_session_jsonl.py

```bash
# 0. Backup (always)
python -c "import shutil; shutil.copytree(r'C:\Users\<you>\.workbuddy\projects', r'D:\projects_backup')"

# 1. Preview what would be merged/copied
python scripts/recover_session_jsonl.py --dry-run

# 2. Execute: merges old+new JSONL per session (dedup by message id, old rows win),
#    copies legacy-only sessions into the new directory. Never deletes anything.
python scripts/recover_session_jsonl.py

# 3. Restart WorkBuddy and verify the history is back.
```

The script is idempotent (message-id dedup makes re-runs safe) and atomic per file
(tmp + `os.replace`). Sessions still being written to are retried; if a file stays
busy, the merged result is kept as `*.merge_tmp` and everything else completes.

**Relation to the 5.4.7 IndexedDB bug**: that bug (section below) broke *persistence of
new* messages; this re-encoding issue breaks *visibility of old* ones. Machines that
lived through both need both fixes. Since 5.5.2 repaired the IndexedDB side, this
script closes the remaining gap.

## Advanced: Session Recovery

When a session's complete message cache (`.jsonl`) is lost but cloud summaries exist:

### Recovery via Cloud Summaries

1. Call `conversation_search` to retrieve cloud summaries of the lost conversation
2. Check the project directory (e.g. `C:\WorkBuddy\2026-03-10-09-20-45\`) for surviving output documents
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

## Deleting Files Safely Under WPS Cloud Sync (Three-Axe Method)

When the workspace tree (`C:\WorkBuddy\...`) or skill/memory subdirs sit under WPS cloud-drive
sync, deleting files is unsafe by default — WPS may write a `-副本` (conflict-copy) sibling the
moment the original goes missing, and a naive `rm -rf` can deadlock on WPS file locks. Use this
three-axe method whenever you need to bulk-delete files under any WPS-synced path.

### Axe 1: run Python with `-S` (skip sitecustomize)

Many user environments register a `sitecustomize.py` that monkey-patches `os.unlink`,
`shutil.rmtree`, and friends into a "safe delete" / recycle-bin flow. On WPS-synced paths that
flow deadlocks (WPS holds the file open while the recycle-bin hook waits for the lock). `-S`
tells Python not to import `sitecustomize`, restoring stdlib behavior:

```bash
python -S your_delete_script.py
```

Or as a one-liner:
```bash
python -S -c "import os; os.remove(r'C:\\WorkBuddy\\_sync\\identity\\<file>.md')"
```

### Axe 2: only `os.remove` — never `ctypes.DeleteFileW`, `Path.unlink`, or `shutil.rmtree`

- OK: `os.remove(path)` — single file, stdlib, cleanest on WPS paths.
- NO: `ctypes.windll.kernel32.DeleteFileW(path)` — bypasses Python's high-level error handling;
  on WPS the file often reappears as a `-副本` conflict-copy because WPS sees the raw syscall
  and tries to "recover" by re-uploading from the other machine.
- NO: `pathlib.Path(path).unlink()` — same hijack surface as `os.unlink` under sitecustomize;
  even with `-S` it sometimes routes through `_NormalizePath` which WPS doesn't fully recognize.
- NO: `shutil.rmtree(path)` — recursively walks; on WPS any directory currently being uploaded
  creates a "directory in use" deadlock. Even with `-S`, prefer deleting files one-by-one (Axe 3)
  and letting the directory become empty, then `os.rmdir`.

### Axe 3: batch <= 40 files per process; loop "scan -> delete -> rescan" until zero

WPS can hold at most ~40 files open per directory for sync-upload at a time. A single process
that tries to delete 4000 files will hit lock contention and stall. Use multiprocessing with each
worker handling <= 40 files, then exiting:

```python
import os, multiprocessing as mp

def delete_batch(paths):
    deleted = []
    for p in paths:
        try:
            os.remove(p)  # single-file, stdlib, no sitecustomize (-S required at interpreter)
            deleted.append(p)
        except OSError:
            pass  # WPS may be holding it; will retry next round
    return deleted

def chunked(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

if __name__ == "__main__":
    target_dir = r"C:\\WorkBuddy\\_sync\\identity"
    while True:
        files = [os.path.join(target_dir, f) for f in os.listdir(target_dir)
                 if f.endswith(".md") and not f.startswith(".")]
        if not files:
            break
        # parallel delete, 40 files per worker
        with mp.Pool(processes=8) as pool:
            for batch in chunked(files, 40):
                pool.apply_async(delete_batch, (batch,))
            pool.close(); pool.join()
        # files that survived (WPS lock) get retried in next loop iteration
```

The "loop until zero" pattern means any file WPS is actively syncing just gets re-tried on the
next pass — eventually every reachable file is gone.

### When NOT to use this method

- Files under `~/.workbuddy/workbuddy.db*` (LOCAL, not synced) — use normal `os.remove` /
  `Path.unlink`; no WPS involvement.
- The user's Desktop / Downloads / Documents root — never bulk-delete here; use the OS Recycle
  Bin. This method is for *workspace tree* cleanup only.
- A single file delete — just call `os.remove` directly, no multiprocessing needed.

---
## Why Project State and Artifact Lists Sometimes Conflict (and How to Prevent It)

Because this skill **modifies WorkBuddy's default configuration** (per-machine `workbuddy.db`
isolation, `workspace-state.json` symlink, `_sync/` transit dir, HANDOFF.md handoff notes), the
cross-machine sync introduces state that vanilla WorkBuddy was never designed to share. The most
common conflict types and their fixes:

### Symptom 1: `workspace-state.json` shows different workspaces on each machine

**Cause**: the file is symlinked into WPS (via `fix_workspace_state_sync.ps1`), but WPS may
upload the change before the new workspace's first JSONL write completes — the other machine
sees the sidebar entry but clicking it opens an empty session.

**Fix**: after creating a new workspace, on the *other* machine:
1. Wait ~5 seconds for WPS to fully sync the new file
2. Right-click -> "Always keep on this device" on the workspace folder in WPS Explorer
3. Restart WorkBuddy so the sidebar re-reads `workspace-state.json`

### Symptom 2: a workspace's `MEMORY.md` is overwritten by another workspace's content

**Cause**: the "flat user-level namespace" collection in older `sync_identity.py` versions
fanned every workspace's `MEMORY.md` into a single `~/.workbuddy/memory/` directory on each
machine; on push, "newest mtime wins" merge then overwrote the local `MEMORY.md` of *every*
workspace with whichever one had been edited most recently. Two real incidents: **2026-07-24**
(14 workspaces polluted with one workspace's content) and **2026-07-30** (same shape, smaller
blast radius).

**Fix (already shipped in `sync_identity.py` v3.6)**:
- Only `YYYY-MM-DD.md` daily logs enter the user-level flat namespace.
- Project identity files (`MEMORY.md`, `STATUS.md`, `DAILY_STATUS.md`, `HOME_WRAPUP.md`,
  `MORNING_BRIEF.md`) are **workspace-local** — never collected, never distributed.
- Any pre-v3.6 polluted file must be restored from the workspace's own daily log
  (look for `### MEMORY.md overwrite on YYYY-MM-DD` headings).

### Symptom 3: STATUS.md / DAILY_STATUS.md missing or stale on one machine

**Cause**: project identity files are workspace-local (Symptom 2 fix); WPS does sync them via
the Junction, but if one machine was offline during the edit, it never received the new version.

**Fix**: when arriving at a machine, the AI's mandatory read order (Step 6) catches this:
1. Read `C:\WorkBuddy\_sync\HANDOFF.md` — has the latest status summary
2. Read `<workspace>/.workbuddy/memory/STATUS.md` — may be stale; if so, the AI reconstructs
   from the HANDOFF.md + recent daily log
3. Read `<workspace>/.workbuddy/memory/YYYY-MM-DD.md` (today + yesterday)

**Prevention**: every substantive work session writes both STATUS.md (workspace-local) **and**
updates HANDOFF.md (cross-machine). The HANDOFF.md is the canonical cross-machine state;
STATUS.md is the workspace-local cache.

### Symptom 4: two machines' daemons fight over the transit directory

**Cause**: if both `watch_sync.py` instances run their main loop at the same time and both see
"transit dir empty, I should push", they create `-副本` conflict-copy files.

**Fix (already shipped in `watch_sync.py` v2.0+)**:
- **Single-leader election** via per-machine heartbeat file: only one machine writes the
  transit dir at any moment.
- The election is observed by `find_junk.py` reports — if you see new `-副本` files, the leader
  election is broken; restart `watchdog.bat` on both machines.

### Symptom 5: automation `cwds` drift (already documented elsewhere)

This is not unique to cross-device sync but is exacerbated by it — see the "Automation Path
Drift" section above for the full runbook.

### Diagnostic one-liner

```bash
# Show the current sync state across both layers
python sync_cli.py status
# (prints: leader machine, transit dir mtime vs source mtime, last push/pull,
#  recent -副本 files, daemon liveness, watchdog liveness)
```

If `sync_cli.py status` reports anything other than "single leader, no conflict copies,
daemon alive", resolve that specific subsystem before assuming data loss.

---

## IDE Artifact-Index Zombie Resurrection (WPS Path vs Local Cache Conflict)

Even though `sync_identity.py` already prevents the `MEMORY.md` cross-overwrite pollution (v3.6) and daemon leader-election fights (v2.0+), a **third, deeper class of zombie resurrection** surfaced on 2026-09-06/07 during the C-drive WeChat cleanup: deleting a file locally did **not** remove it from the IDE's artifact panel, and — worse — the file kept coming **back** after a restart. Two independent root causes, both caused by the WPS path being a symlink while local caches/indices are not.

### Symptom A: `.workbuddy/memory/` gets polluted with non-`.md` junk that WPS re-pulls (cleanup -> reverse-pull loop)

**Cause**: During the C-drive cleanup, ~47 one-off scripts/reports (`.py`/`.txt`/`.log`) were written into `<workspace>/.workbuddy/memory/` — a directory symlinked into WPS cloud. `watch_sync` pushed them to WPS; on the next sync the WPS copy was pulled back. Every "delete locally" was undone by the reverse pull -> an endless zombie loop, and the junk polluted *every* machine through the shared cloud.

**Fix (shipped in `sync_identity.py` v3.8)**:
- New `cleanup_memory_non_md(dir)` runs **before** every sync on both the local and transit `memory/` dirs, deleting anything that is not `.md`.
- `.workbuddy/memory/` is now hard-bounded: only `YYYY-MM-DD.md` daily logs and project identity `.md` files (`MEMORY.md`, `STATUS.md`, `DAILY_STATUS.md`, `HOME_WRAPUP.md`, `MORNING_BRIEF.md`) are allowed. Any temp script/report is rejected at the boundary, so there is nothing for WPS to re-pull.

### Symptom B: IDE artifact panel shows dead entries for already-deleted files (survives restart)

**Cause**: WorkBuddy keeps a per-session **artifact-index** (`~/.workbuddy/artifact-index/*.json`, one JSON per session) recording the absolute `file:///` URIs of every Read/Write/present_files call. These JSONs are symlinked into WPS cloud too. Deleting the underlying file on disk does **not** remove its URI from the index, so the IDE artifact panel keeps rendering the zombie entry — and because the index itself is cloud-synced, it even survives a full IDE restart.

**Fix (shipped in `sync_identity.py` v3.8)**:
- New companion script `cleanup_artifact_index.py` resolves each artifact URI to a real path and drops entries whose file no longer exists (atomic rewrite via `.tmp` + `os.replace`).
- `sync_identity.py` `main()` now invokes `cleanup_artifact_index.py` on **every sync**, defaulting to *active-only* mode (sessions updated within the last 24h) so historical sessions are left untouched; pass `--all-sessions` to scrub everything.
- This makes the cleanup run automatically on every sync / daemon cycle — there is no window in which a dead URI can be re-shown.

### How to run the cleaners manually

```bash
# Scrub dead artifact-index URIs in the active session(s) only:
python cleanup_artifact_index.py
# Scrub ALL sessions (use after a big cleanup):
python cleanup_artifact_index.py --all-sessions --dry-run   # preview
python cleanup_artifact_index.py --all-sessions            # execute
```

### Why this is a "software-level" root fix (not a one-time cleanup)

An earlier Seller-Ops workspace hit the same artifact-panel zombie and only did a one-time `.bak-20260905` cleanup — it had **no persistent defense**, so the bug recurred in this workspace. The v3.8 fix is integrated into the sync engine itself, so every future sync re-asserts the boundary automatically. Combined with the v3.6 `MEMORY.md` boundary, the memory/artifact layers now have a closed defense on both sides: the WPS-symlink side (nothing junk to sync) and the local-index side (dead URIs purged each cycle).

---
## Known Limitations

### Archived Sessions

WorkBuddy currently has **NO UI filter for archived sessions**. The sidebar filter only shows:
In Progress | Completed | Failed | Pending | Planned | All

Once a session is archived (status=archived in DB), it becomes invisible in the UI.
To recover: manually change `status` back to `"working"` or `"completed"` in the database:

```sql
UPDATE sessions SET status = 'completed' WHERE id = '<session_id>';
```

### Timestamp "Year Bug"

Restored messages with incorrect timestamps (wrong year) will:
- Show as implausible dates in the UI (e.g. "56 years ago")
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

Automations (scheduled tasks, e.g. an end-of-day auto-archive) store a hardcoded `cwds` field
and may reference workspace paths in their `prompt` text. After path migration
or when the active workspace changes (new conversation = new timestamp-based dir),
automations silently point at the **old workspace** — they will run but write to
the wrong directory, or fail because the old workspace no longer exists.

**Symptoms**:
- Automation runs but output files appear in an old workspace
- Automation shows dates from weeks ago
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
ls -la ~/.workbuddy/skills   # should show -> .../WPSYun/WPS cloud dir/.workbuddy/skills (trailing dir is the literal WPS folder name)

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

### Restored content shows implausible dates ("56 years ago")

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

The pattern is always `%USERPROFILE%\Documents\WPSDrive\<id>\WPS云盘\` — only `<id>` varies (the trailing folder is the literal WPS cloud-drive folder name).

## Resources

### sync_identity.py (v3.8)

Bidirectional **transit-channel** sync. Collects each workspace's `.workbuddy/memory/` into
`C:\WorkBuddy\_sync\identity\`, and distributes transit memory back to workspaces on pull.
Also syncs HANDOFF.md / identity files. v3.4+ auto-cleans WPS conflict-copy files (literal suffix `-副本`, functional) and skips
any file containing that suffix to prevent sync storms; v3.5 sweeps junk before push.
**v3.6 (MEMORY.md boundary)** — only `YYYY-MM-DD.md` daily logs may enter the flat user-level namespace;
project identity files (MEMORY.md / STATUS.md / DAILY_STATUS.md / HOME_WRAPUP.md /
MORNING_BRIEF.md) are skipped — previously they collided across workspaces and "newest mtime
wins" merge fanned one workspace's content into ALL workspaces (two incidents: 7/24, 7/30,
14 workspaces polluted).
**v3.7 (write-back disabled, 2026-08-27)** — permanently disables `distribute_user_memory_to_workspaces()`,
sealing the second-stage fan-out path that could still push user-level memory/ back into
every workspace after the v3.6 boundary closed the merge step. Same shape of pollution cannot recur.
**v3.8 (artifact-index + memory-boundary defense, 2026-09-07)** — hard-bounds
`.workbuddy/memory/` to `.md` only via `cleanup_memory_non_md()` (kills the "clean locally → WPS
copy reverse-pulls it back" zombie loop surfaced during the 2026-09-06 C-drive cleanup), and
integrates the sibling `cleanup_artifact_index.py` so the IDE's per-session artifact-index dead
URIs are purged on every sync (active sessions by default, `--all-sessions` to scrub all).
See "IDE Artifact-Index Zombie Resurrection" below for the full story.

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
pristine original). Use after a sync storm or whenever thousands of conflict-copy (`-副本`) files appear.

### workspace_sync.py (v3.0)

Mechanical sync: scans `C:\WorkBuddy` workspaces, regenerates the HANDOFF.md machine section
(leaving the AI-written section untouched), and assists with conversation export + sync passcode.

### sync_cli.py (v6.1+)

Single launcher that replaces the four `.bat` wrappers (`push.bat`, `pull.bat`,
`start_sync.bat`, one-click sync). Double-click it for an interactive menu, or call
`sync_cli.py pull` / `push` / `sync` / `verify` / `status` / `start` / `stop` /
`startup-install`. `start` brings up the **watchdog** (which in turn supervises the
daemon) rather than the daemon directly, so crashes stay self-healing. Distribution
channels reject `.bat` files, so this is the only launcher that ships in the
published package.

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

### scripts/recover_session_jsonl.py (v6.3+)

Recovers conversation history that "disappeared" after a 5.5.x update caused workspace
paths to be re-encoded (junction resolved to the real WPS cloud path). Scans
`~/.workbuddy/projects/` for legacy/new encoded directory pairs, merges each session's
old+new JSONL with message-id dedup (old rows win), and copies legacy-only sessions
into the new directory. Idempotent, atomic per file, never deletes. See the
"Recovering History Lost After 5.5.x Updates" section for the full runbook.
