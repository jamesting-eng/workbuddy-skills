# AI Cross-Device Handoff Guide

> The AI on both computers must read this.

---

## Architecture Overview (verified in practice on 2026-07-13, important)

```
C:\WorkBuddy\                       ← WPS cloud drive Junction on both home/office machines (same physical files)
├── <workspace>\.workbuddy\memory\  ← workspace memory (includes hidden dirs, carried automatically by WPS main sync)
└── _sync\
    ├── HANDOFF.md                  ← handoff note (machine-generated zone + AI handwritten zone), physically shared via WPS
    ├── AI_HANDOFF_GUIDE.md         ← this file
    ├── conversations\              ← full exports of important conversations
    ├── workspace_sync.py           ← machine-zone generation script
    ├── sync_identity.py            ← transit channel bidirectional sync script (fallback + precise control)
    ├── watch_sync.py               ← daemon v2.2 (self-healing + blocked-state self-healing)
    ├── watchdog.bat                ← watchdog (restarts within 30s of a crash + force-kills liveness-stalled processes)
    └── identity\                   ← transit directory (used by sync_identity.py, not the main channel)
```

**Three sync layers with different responsibilities:**

| Layer | Mechanism | Role | Required |
|----|------|------|----------|
| **Main sync** | `C:\WorkBuddy` is a WPS cloud drive Junction; the whole tree (including hidden `.workbuddy`) syncs bidirectionally automatically | **Default channel** for workspace files + memory | ✅ Always on |
| **Transit fallback** | `sync_identity.py` uses the `_sync/identity\` transit directory | Forced push/pull, cleaning WPS conflict copies, precise cross-machine control | Optional (manual / daemon-automated) |
| **Auto guard** | `watch_sync.py` watches source file changes → auto-triggers transit push | Keeps the transit channel up to date in real time; single-leader election prevents duplicate copies | Enhancement (v2.2 self-healing + blocked-state self-healing) |

**Core principle**: DBs are forked; conversation history is not shared. Task continuity is achieved via HANDOFF.md + conversations/ + workspace memory.

> ⚠️ **Historical pitfall (fixed)**: Earlier documentation stated "WPS cloud drive deprecated, HANDOFF.md goes through the transit channel" —
> that was written on 2026-07-06 when WPS briefly failed on the office machine and **does not match home-machine testing**. Testing confirmed that
> `C:\WorkBuddy` on the home machine is indeed a WPS junction and WPS is the main sync (including hidden `.workbuddy`). This file + HANDOFF.md are authoritative.

---

## 📤 Push Flow (before leaving the computer)

**Trigger phrases**: "getting ready to switch computers" / "wrapping up for tonight" / "write the handoff note" / "getting ready to leave work"

### What the AI must do:

1. **Update the task progress zone of HANDOFF.md**
   - Locate content after `<!-- ✅ AI handwritten zone below -->`
   - Update the status and checkboxes of each item under `## 📋 Task Progress`
   - Add or modify task items

2. **Append a conversation summary**
   - Add a new entry under `## 💬 Recent Conversation Summaries`
   - Format:
     ```markdown
     ### [date time] Topic name — current computer
     - **Summary**: 1-3 sentences
     - **Key decisions**: list
     - **Deliverables**: list
     ```

3. **Export important conversations** (if there was substantive discussion)
   - Write the full content of the current conversation to `_sync/conversations/YYYY-MM-DD-topic.md`
   - The format must include: topic, time, full conversation transcript
   - Add a row to the `## 📎 Exported Conversations` table in HANDOFF.md

4. **Update the header timestamp**
   - The `**Last Updated**` time at the top of HANDOFF.md

5. **(Recommended) Run sync_identity.py push as a fallback**
   ```bash
   python C:\WorkBuddy\_sync\sync_identity.py push
   ```
   - WPS main sync is usually running, but a manual push ensures the transit channel is also up to date, so the other machine gets it immediately via `pull`.
   - Seeing "HANDOFF.md (transit channel): pushed" means success.

---

## 📥 Pull Flow (after arriving at the other computer)

**Trigger phrases**: "pull sync" / "check the handoff note" / "continue" / "is the home computer done"

### ⚠️ Important: sync pull is a mandatory action, not a suggestion

When the user says "pull sync", you **must** actually run the sync_identity.py pull command and **must not skip it**.
Just reading the docs/memory files is not enough, because the transit directory may contain new content not yet distributed to the workspace.

### What the AI must do:

0. **Run sync_identity.py pull** (iron rule)
   ```bash
   python C:\WorkBuddy\_sync\sync_identity.py pull
   ```
   - Pulls HANDOFF.md / identity files / workspace memory from the transit directory
   - Seeing "HANDOFF.md (transit channel): pulled" means success
   - **If it fails**: clearly tell the user "sync failed, X error"; do not pretend it succeeded

1. **Read HANDOFF.md** (C:\WorkBuddy\_sync\HANDOFF.md)
   - Check the sync passphrase (verify whether the passphrase left by the other computer is visible)
   - Understand current task progress
   - Read recent conversation summaries

2. **Check exported conversations**
   - Look at the `## 📎 Exported Conversations` table
   - Read new files in `_sync/conversations/`
   - Get the full context

3. **Read project memory**
   - `C:\WorkBuddy\{workspace}\.workbuddy\memory\MEMORY.md`
   - `C:\WorkBuddy\{workspace}\.workbuddy\memory\YYYY-MM-DD.md`

4. **Report to the user**
   - Whether the sync passphrase check passed
   - Overview of current task progress
   - Key points of the most recent conversation
   - Ask whether to continue

---

## 🆕 New-Workspace Hard Requirements (locked in v3.3, preventing the 7/11 gap)

> **Root-cause review (2026-07-11)**: The user created a new workspace at the office and did a large amount of Axistar work there, but the AI neither created
> `.workbuddy/memory` for that workspace nor updated HANDOFF.md. As a result, the **narrative logs of that batch of work were never synced over**
> (the work products arrived via WPS main sync, but the AI logs were zero). This was a rules gap, not a sync failure.

**After a new workspace is created, the AI must do the following first (order is mandatory):**

1. **Create the status file** `.workbuddy/memory/STATUS.md`
   - Contains: project identity, current phase, key constraints, pending decisions
   - This is the workspace's "ID card"; WPS main sync will carry it automatically
2. **Create the day's log** `.workbuddy/memory/YYYY-MM-DD.md`
   - Record what was done and what was decided in this opening session
3. **Run sync pull once** (pull the other computers' state from transit to avoid working blindly in an empty workspace)
4. **Tell the user**: "New workspace created, memory/STATUS established, latest state pulled from transit"

**After each session of substantive work, you must (see the wrap-up checklist below):**
- Write/update project memory (MEMORY.md long-term + the day's dated log)
- Update the handwritten zone of HANDOFF.md (task progress + conversation summary)
- Once these are written to the files, WPS main sync syncs them automatically and the other machine sees them

---

## 🔚 Wrap-Up Checklist (before leaving the computer, AI self-check)

```
□ Project memory updated? (MEMORY.md or the day's YYYY-MM-DD.md)
□ HANDOFF.md handwritten zone updated? (task progress + conversation summary + header timestamp)
□ Important conversations exported to conversations/? (if there was substantive discussion)
□ sync_identity.py push run? (recommended, ensures the transit is also up to date)
□ User told "you can switch computers now"?
```
> If any item is incomplete → do not say "handoff complete". WPS main sync relies on **files actually existing**;
> if the AI does not write files, the other side will never see them, regardless of whether the daemon is alive.

---

## 🤖 watch_sync Daemon (v2.2, self-healing + blocked-state self-healing)

- **Purpose**: watches for source file changes in `C:\WorkBuddy` + `~/.workbuddy` in the background and auto-triggers transit push
- **Single-leader election**: each machine writes `heartbeat_<machinename>.txt`; only the uniquely active machine pushes, preventing concurrent duplicate writes
- **Response latency**: 1s scan + 1s debounce ≈ auto-push **1-2 seconds** after a change (the 0.3s/500ms in older docs was exaggerated)
- **v2.1 self-healing (fixes the 7/7 silent death)**:
  - Process level: try/except around the main loop; any exception is only logged + baseline rebuilt after 10s and re-entered; the process **never exits**
  - run_sync self-healing: consecutive-failure counter; at threshold (3), rebuilds baseline + fallback pull
  - Heartbeat thread exception protection
- **v2.2 blocked-state self-healing (fixes "process alive but blocked" since 7/13)**:
  - Root cause: WorkBuddy's sitecustomize.py hijacks unlink/rmtree on WPS paths into "a never-returning recycle-bin subprocess" → zombie state
  - All subprocess calls use `-S` (skipping sitecustomize), eliminating the deadlock at the root
  - The main loop updates `liveness_<machinename>.txt` on every scan; the watchdog uses this to detect a stall (>240s without update → force-kill and restart)
  - ⚠️ The watchdog must use the matching v2 `watchdog.bat` (checks both PID liveness + liveness freshness, starts with `-S`);
    the old version only checks PID, cannot detect blocked state, and v2.2's blocked-state self-healing would fail
- **Startup**: auto-start `watchdog.bat` at boot (place in shell:startup, recommended); or the `start_sync.bat` launches the watchdog chain
- **So the user does not need to run sync manually**, except for proactive requests like "pull sync"; running push.bat once before leaving is double insurance

---

## ⚠️ Rules

1. **Do not overwrite the machine-generated zone**: content between `<!-- ⚙️ -->` and `<!-- ✅ -->` is maintained by workspace_sync.py
2. **Do not modify the structure of the AI handwritten zone**: keep the three main headings `## 📋` / `## 💬` / `## 📎`
   > NOTE: the heading TEXT inside the real HANDOFF.md is in Chinese (e.g. `## 📋 任务进度`, `## 💬 近期对话摘要`, `## 📎 导出对话`) because it is generated by workspace_sync.py. The English renderings above are documentation-only — match the emoji + structure, not the wording.
3. **Keep conversation summaries concise**: about 3-5 lines each, with key information clearly stated
4. **Do not write back after pulling**: when pulling, only read HANDOFF.md, do not modify it. Only write during push.
5. **Archive old summaries**: move summaries older than 7 days to `_sync/conversations/archive/` (optional)
6. **Security**: do not export conversation content containing passwords, tokens, or personal private information
7. **Every new workspace must get memory created**: see the "New-Workspace Hard Requirements" section; this is not optional

---

## 🔧 workspace_sync.py Behavior

- When running `python workspace_sync.py`:
  - Updates the content between `<!-- ⚙️ -->` and `<!-- ✅ -->` in HANDOFF.md
  - Does not touch content after `<!-- ✅ -->` (the AI handwritten zone is safe)
- Recommended to run at least once per day (automation already exists)

---

---

## ⚠️ 5.4.7 IndexedDB Loss Era Addendum (from 2026-09)

> Scope: after installing WorkBuddy `5.4.7.37521366`, **conversation bodies are lost on restart** (sessions appear in the sidebar but have no content when opened). The root cause is that the Chromium IndexedDB subsystem is not initialized under `app/session`, so messages only land in memory. **This is unrelated to WPS cloud sync**, cannot be fixed locally, and requires an official hotfix.

### This guide is even more critical during this period

- Conversation context cannot be trusted; **the disk is the source of truth**.
- All mechanisms in this guide (HANDOFF.md / STATUS.md / logs / transit channel) are disk writes and **are unaffected by the IndexedDB regression**.
- Therefore: during this period **do not disable this skill**; execute it even more strictly.

### Push side (before leaving the computer)

1. First write this conversation's key decisions / deliverables into `<workspace>/.workbuddy/memory/YYYY-MM-DD.md` and `STATUS.md`
2. Then run `sync_identity.py push` (or double-click `sync_cli.py` and choose push)
3. Confirm that the WPS cloud shows HANDOFF.md synced

### Pull side (after switching computers)

1. **Read the disk first**: HANDOFF.md → STATUS.md → today's / yesterday's logs → user-level MEMORY.md
2. **Then speak**: statements like "I remember we said last time…" that do not come from the four reading steps above are forbidden
3. Then run `sync_identity.py pull`

### Recovery when conversation bodies are lost

1. Check the `cwd` / time of that session in `workbuddy.db` (list metadata is intact)
2. Read `<cwd>/.workbuddy/memory/STATUS.md` and the day's log to rebuild context
3. **Fabricating conversation content is strictly forbidden**: if it is not written on disk, honestly say "I don't know"

> For the full emergency SOP, see the *Emergency Persistence: 5.4.7 IndexedDB Loss Era SOP* section of `SKILL.md`.

*This file is physically shared via the WPS junction (`C:\WorkBuddy` is a cloud drive Junction); the AI on both computers sees the same physical file.*
