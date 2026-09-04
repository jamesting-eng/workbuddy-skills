# Cross-Device Sync for WorkBuddy / CodeBuddy

Sync WorkBuddy seamlessly across multiple Windows computers — conversations created at the office continue at home; tasks started at home carry on at the office.

## What Is This?

> ℹ **Known issue (WorkBuddy 5.4.7)**: users on `5.4.7.37521366` will see **conversation bodies lost on restart** (the sidebar list is still there, but clicking in shows no content). This issue does not affect this skill — the skill is **disk-based** (HANDOFF.md / STATUS.md / logs / handoff notes), and is in fact the only reliable way to keep working through that period. For emergency handling, see the **Emergency Persistence: 5.4.7 IndexedDB Loss Era SOP** section in `SKILL.md`.

A [WorkBuddy](https://www.codebuddy.cn) skill that solves the problem of syncing WorkBuddy data across multiple Windows computers.

**Core pain point**: `workbuddy.db` (SQLite) cannot be read and written by two computers at the same time — conversation records would overwrite each other. Each computer's Windows user directory is also different, invalidating session file paths.

**Solution (v6 hybrid three-layer architecture)**:

- `workbuddy.db` stays local and independent on each machine (no overwriting)
- Subdirectories are symlinked into the WPS cloud drive for syncing
- Workspaces are unified as `C:\WorkBuddy\` via a Junction
- **Primary sync = WPS Junction**: the entire `C:\WorkBuddy` tree (including the hidden `.workbuddy`) is two-way synced automatically by the WPS cloud drive
- **Transit fallback = `sync_identity.py`**: precisely controls syncing of identity files / HANDOFF / memory via `_sync/identity/`, and cleans up WPS conflict copies
- **Automatic daemon = `watch_sync.py` v2.2 + `watchdog.bat`**: auto-push on any file change (single-leader election), self-healing from process crashes/hangs
- Cross-device task continuity via the `HANDOFF.md` handoff note + `AI_HANDOFF_GUIDE.md`

> 📌 **Architecture correction (v6)**: v3.2 once asserted that "direct Junction transfer fails; everything must go through transit". **Real-world testing in July proved this was a misdiagnosis** — the `C:\WorkBuddy` Junction has always been the working primary sync channel (the alleged "failure" was actually WPS sync delay plus the AI failing to write logs). The correct understanding is **three layers coexisting, each with its own role**: WPS Junction primary sync, transit channel as fallback with precise control, and the daemon making transit near-real-time. The transit channel is retained: it remains a necessary tool for cleaning up conflict copies, forcing alignment, and countering WPS sync laziness.

## What Changed in v6 (vs v5)

| Change | Description |
|--------|-------------|
| `sync_identity.py` v3.5 → **v3.6** | **Root-cure for cross-workspace MEMORY.md mutual-overwrite pollution**: collect/distribute only allows `YYYY-MM-DD.md` daily logs into the flat user-level namespace; project identity files (MEMORY.md/STATUS.md/DAILY_STATUS.md etc.) are always skipped, so they are no longer merged under "newest mtime wins" and fanned back out to all workspaces (two incidents on 7/24 and 7/30, where 14 workspaces' MEMORY.md files were overwritten with the same content) |
| `watch_sync.py` v2.0 → **v2.2** | v2.1 self-healing: try/except wrapper around the main loop so it never exits, automatic baseline rebuild + fallback pull after consecutive failures, PID file, heartbeat thread protection; v2.2 hang self-healing: all subprocesses launched with `-S` (bypasses sitecustomize's hijacking of unlink/rmtree on WPS paths — the root cause of a silent week-long hang since 7/13), and the main loop refreshes the `liveness_<machine-name>.txt` liveness signal every cycle |
| **New `watchdog.bat` (v2)** | Watchdog: PID absent (crashed/killed) **or** liveness not updated for over 240s (main loop blocked) → if either condition holds, force-kill and restart; the restart command includes `-S`. Put it in `shell:startup` for machine-reboot-level self-healing |
| `AI_HANDOFF_GUIDE.md` rewritten | Corrected the three-layer architecture understanding; added the "hard constraints for new workspaces" (first step must create `.workbuddy/memory/STATUS.md` + the day's daily log) and a "wrap-up checklist"; response latency honestly documented as 1-2s |

## Directory Structure

```
(this repo's root directory contains all files of this skill; no subdirectories needed)

├── SKILL.md                          # Skill definition & complete operation guide
├── README.md                         # This file
├── LICENSE                           # MIT
├── .gitignore                        # Excludes secret.txt / runtime logs / PID and other local artifacts
├── PUBLISH.md                        # GitHub publishing guide
├── manifest.yaml                     # SkillHub skill metadata (required for packaging)
├── package.py                        # One-click packaging into a SkillHub-compliant zip (auto validation + excludes sensitive files)
├── AI_HANDOFF_GUIDE.md               # AI cross-device handoff operation guide (read by both AIs)
├── sync_identity.py                  # User identity & memory & HANDOFF transit sync script (v3.6)
├── watch_sync.py                     # Auto-sync daemon (v2.2: single leader + self-healing + hang self-healing)
├── watchdog.bat                      # Watchdog (crash restart + force-kill on liveness hang; put in shell:startup)
├── find_junk.py                      # WPS conflict-copy scanner (generates an HTML report)
├── clean_junk.py                     # WPS conflict-copy cleaner (double safeguard; only deletes copies that have an original)
├── workspace_sync.py                 # Mechanical sync script (DB repair + handoff-note machine section generation)
├── secret.txt.example                # Sync passphrase template (copy to secret.txt; never commit the real value)
├── fix_db_isolation_v3.ps1           # Database isolation script (core, from v4)
├── fix_workspace_state_sync.ps1      # workspace-state sync fix (from v4)
├── push.bat                          # One-click push before leaving the computer (handoff + verify)
├── pull.bat                          # One-click pull-and-verify on the other computer
├── one-click-sync.bat                # Pull + start the daemon
├── start_sync.bat                    # Daemon launcher (spins up the watchdog chain)
├── sync_cli.py                       # Unified entry point: double-click = menu / pull / push / sync / verify
│                                     #   status / start / stop / startup-install (launch at boot)
│                                     #   Replaces the 4 .bat files (publishing channels reject .bat)
└── scripts/
    ├── fix_paths.py                  # Path repair script (four steps, from v4)
    └── restore_and_merge.py          # Session restore & merge tool (from v4)
```

## Prerequisites

- Windows 10/11
- WPS Office (with the cloud drive feature, synced locally)
- **Administrator privileges** (required to create a Junction)
- WorkBuddy installed on Windows

## Quick Start

### 1. Configure Sync (run once on each computer, about 15 minutes)

```powershell
# ① Database isolation: move workbuddy.db off the cloud drive to local storage
.\fix_db_isolation_v3.ps1

# ② workspace-state sync: newly created workspaces visible on both sides
.\fix_workspace_state_sync.ps1

# ③ Create the C:\WorkBuddy Junction to unify the working directory path
New-Item -ItemType Junction -Path "C:\WorkBuddy" `
    -Target "$env:USERPROFILE\Documents\WPSDrive\<id>\<WPS cloud drive folder>\WorkBuddy"
```

### 2. Fix Paths

```
# Run on each computer to unify all session paths
python scripts/fix_paths.py
```

The script automatically performs four steps: JSON repair → database repair → project cache merge → JSONL cwd path repair.

### 3. Start the Auto-Sync Daemon (v6 recommends watchdog.bat)

```
# Launch at boot (recommended): put watchdog.bat into shell:startup (Win+R → shell:startup)
# It launches watch_sync.py and keeps guarding it:
#   - Process absent (crashed/killed/machine rebooted) → restart within 30s
#   - liveness_<machine-name>.txt not updated for over 240s (main loop hung) → force-kill and restart
# Start manually once:
python -S watch_sync.py            # Long-running daemon (safe in single-leader mode; -S skips sitecustomize)
python -S watch_sync.py --status   # Show watch status + leader status + liveness thresholds
python -S watch_sync.py --once     # Run one sync pass and exit
```

> ⚠️ **Be sure to use the matching v2 `watchdog.bat`**. The old version only checks PID liveness and cannot detect a "process alive but blocked" hang (exactly the true cause of the silent week-long death since 7/13). Note that the `_sync` directory is not covered by auto-sync, so when upgrading you must manually copy the new `watch_sync.py` + `watchdog.bat` to the same path on the other computer.

The daemon watches source files for changes in the background (1s scan + 1s debounce ≈ 1-2 second latency) and pushes automatically; single-leader election ensures only one machine writes to the transit directory at a time, root-curing WPS conflict-copy storms.

### 4. Using Handoff Notes (cross-device task continuity)

**Before leaving the computer** — say "generate a handoff note" or "sync tasks":

- The AI automatically updates `C:\WorkBuddy\_sync\HANDOFF.md`
- It contains active projects, task progress, conversation summaries, and next steps
- Run `sync_identity.py push` to push to the transit channel (**wait until the push completes before leaving**)

**After arriving at the other computer** — say "pull sync" or "continue where we left off":

- The AI's first action: run `sync_identity.py pull` (iron rule, must not be skipped)
- It shows the previous work state and context
- Tasks continue seamlessly

> ⚠️ **WPS sync can be "lazy"**: an empty directory ≠ nothing was done. The WPS client has sync delay; to judge whether the other machine produced output, you must cross-check the `_sync/` handoff report against the actual paths on the other machine — never rely on the local directory alone.

## Caveats & Hard-Won Lessons

| Pitfall | Symptom | Cause | Fix |
|---------|---------|-------|-----|
| **db overwritten by sync** | Office conversations vanish; home conversations appear at the office | `workbuddy.db` sits in the WPS cloud drive, shared by two computers | Run `fix_db_isolation_v3.ps1` (core of the v3 architecture) |
| **New workspace not shown** | Workspace created at the office missing from the home sidebar | `workspace-state.json` is a local file and was not synced | Run `fix_workspace_state_sync.ps1` |
| **WAL not flushed** | Latest conversations lost after shutdown | WorkBuddy did not fully exit; WAL files remain | Confirm the process fully exits and WAL files disappear |
| **workspace-state.json empty** | Sidebar shows only 1 workspace | WPS synced an old version, or the client overwrote it | Rebuild workspace-state.json from the DB |
| **Sessions soft-deleted** | DB has records but the sidebar shows nothing | The WorkBuddy client marked deleted_at during sync | `UPDATE sessions SET deleted_at = NULL` |
| **Missing .workbuddy marker** | Workspace directory exists but the sidebar does not show it | Directory lacks the `.workbuddy/memory/` subdirectory | Create the marker directory manually (first step for every new workspace) |
| **Path separators** | Restored sessions not shown in the list | cwd used forward slashes `C:/...` | Must use backslashes `C:\...` |
| **user_id** | Same as above | `"default"` filled in the database | Must use a real UUID |
| **Timestamp year** | Shows "56 years ago" and content does not render | `created_at=0`, or seconds instead of milliseconds | Ensure milliseconds |
| **Conversations disappear** | History messages gone after path repair | Project cache split into two copies due to path change | `fix_paths.py` step 3 merges automatically |
| **deliver_attachments fails silently** | The recipient never receives sent files | `~/.workbuddy/` is a symlink path | `cp` files to `C:\WorkBuddy\` first, then deliver |
| **AI doesn't know to read the handoff note** | After switching computers the AI says "everything is synced" but shows no context | The AI was not instructed to read HANDOFF.md first | Updated SKILL.md with a mandatory rule (fixed in v4) |
| **WPS conflict-copy storm** | Thousands of `-copy` duplicate files | Two computers writing to the same WPS path at the same time | `watch_sync.py` single-leader election + `find_junk.py`/`clean_junk.py` cleanup |
| **Daemon silently dead for a week** | Twice (7/7, 7/13); transit sync stalled with no alert | ① sync timeout exceptions uncaught, direct exit; ② sitecustomize hijacked unlink/rmtree on WPS paths into a never-returning recycle bin subprocess → main process blocked but PID still alive | v2.1 process-level self-healing + v2.2 all subprocesses with `-S`; watchdog checks liveness (not just PID) |
| **Watchdog can't detect hangs** | Process alive but frozen; watchdog never restarts it | Old watchdog.bat only checked the PID via `tasklist` | v2 watchdog.bat: liveness stale over 240s → force-kill and restart |
| **MEMORY.md cross-workspace mutual-overwrite pollution** | 14 workspaces' MEMORY.md all became the same content (incidents on 7/24 and 7/30) | collect/distribute flattened same-named MEMORY.md files from all workspaces into the same user-level namespace, newest mtime won, then fanned them back out to all workspaces | **v3.6**: identity files never enter the flat transit; only `YYYY-MM-DD.md` daily logs go through transit |
| **Daily-log same-name residue risk** | A workspace's daily log fanned out to multiple workspaces (7/11: one NESPA log fanned out to 8 workspaces) | `YYYY-MM-DD.md` files with the same name across workspaces still overwrite each other | **Known, unfixed**: full isolation would require namespacing by workspace (a larger refactor) |
| **Garbled Chinese in .bat** | Chinese text turns to mojibake in CMD | .bat files saved as UTF-8 | .bat files containing Chinese must be GBK-encoded; pure-ASCII content is safe in any encoding |
| **Sandbox can't test .bat** | `cmd /c` and `Start-Process cmd` blocked in the AI sandbox | WorkBuddy sandbox security policy | .bat files can only be verified on a real machine; in the sandbox, simulate by directly spawning python processes |
| **WPS sync laziness** | Office files not visible at home; wrongly judged as "not done" | WPS client sync delay/incomplete sync | Manually refresh a few times; cross-machine emptiness checks must cross-check the `_sync/` handoff report against the other machine's actual paths |
| **Cross-machine attribution error** | Work synced over from the office machine credited as "done at home" | WPS silently mirrors work products | Before writing the wrap-up, assign machine provenance to each piece of work per the "partition convention" |

## Operating Conventions (Recommended)

- **AI partitioning**: each computer handles only one project (e.g., home = personal project, office = work project) to avoid memory confusion from discussing the same matter across machines
- **Hard constraints for new workspaces**: create `.workbuddy/memory/STATUS.md` + the day's daily log as the very first step, otherwise the narrative log will have gaps
- **Wrap-up iron rule**: if the AI finds a workspace "empty", it must not conclude "no output" outright — cross-check the handoff report first
- **Passphrase**: verify `secret.txt` matches after every pull; **never submit the real value in chats or documents**

## FAQ

**Q: After syncing, why can't I see the office computer's conversations at home?**

**This is by design.** `workbuddy.db` is stored independently on each computer; conversation history is not synced. This avoids two computers writing to the same database and overwriting each other. For cross-device task continuity, use "sync tasks" to generate the `HANDOFF.md` handoff note.

**Q: Why can't I see newly created workspaces on the other computer?**

Check whether `workspace-state.json` is a symlink pointing into the WPS cloud drive. If not, run `fix_workspace_state_sync.ps1`.

**Q: Could the conversations on the two computers be overwritten again?**

No. In the v3 architecture, `workbuddy.db` lives entirely locally; the WPS cloud drive does not contain this file at all.

**Q: Can I use a different cloud drive?**

In theory, yes. The core is symlinking `.workbuddy` into any cloud drive's sync directory. But the path-replacement logic needs corresponding adjustments. The WPS cloud drive is free and unmetered for users in China, and is the most recommended option.

**Q: Does this work on Mac?**

The scripts currently support Windows only (they depend on PowerShell Junctions and the `C:\` path convention). Mac users can create symlinks manually and adapt the path formats in the scripts. PRs welcome.

**Q: What if the daemon dies?**

With the v2.2 + watchdog.bat v2 combination: crash → auto-restart within 30s; hang (liveness stale over 240s) → auto force-kill and restart; machine reboots are covered by shell:startup. Manual check: `python -S watch_sync.py --status`; logs: `_sync/watch_sync.log`.

**Q: What if lots of `-copy` duplicate files appear?**

Run `python find_junk.py` to scan and generate a report; after confirming every copy has an original, clean up with `python clean_junk.py --execute`. The current single-leader mechanism already prevents new copies from appearing, so this is a one-time cleanup.

**Q: How do I recover polluted MEMORY.md files?**

v3.6 prevents recurrence. For already-overwritten files: there is no clean backup in the transit directory or the sync namespace, so you must go back to the corresponding workspace and **manually rebuild them selectively** from conversation history/project output (do not let the AI batch-rebuild automatically — it can easily write the polluted content back).

## Install as a WorkBuddy Skill

1. Clone this repository:

```
git clone https://github.com/jamesting-eng/workbuddy-skills.git
```

> If you forked this repository, just replace `jamesting-eng` with your own GitHub username when cloning.

2. Copy all files from the repository root into the WorkBuddy user skills directory:

```
# Target directory (user-level skills):
#   %USERPROFILE%\.workbuddy\skills\cross-device-sync\
# i.e. put this repo root's SKILL.md / *.py / *.bat / scripts/ etc. into it as a whole
```

3. In a WorkBuddy conversation, just say "cross-device sync" or "help me sync WorkBuddy across multiple computers" and this skill triggers automatically.

> The skill files live in the repository root (not a `cross-device-sync/` subdirectory). When installing, put the root directory's contents into `~/.workbuddy/skills/cross-device-sync/` accordingly.

## Installation

This skill is maintained by the author and published to SkillHub: search for **cross-device-sync** inside WorkBuddy to install.
Please do not republish this repository's contents through third-party channels; if you need to distribute it, follow the MIT license and keep attribution.

## License

MIT License — use, modify, and distribute freely.
