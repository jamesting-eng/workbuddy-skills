# Cross-Device Sync for WorkBuddy / CodeBuddy

**Local-first WorkBuddy continuity: live work stays on a local disk; WPS cloud is a weekly backup pipe only.**

## What Is This?

A [WorkBuddy](https://www.codebuddy.cn) skill for keeping work going across two or more Windows
computers. **v7 changes the default on purpose**: real-time cloud sync is fragile under dense
daily use (field incident 2026-11-24: conversation bodies + artifacts lost, byte-level manual
merge needed), so it is no longer the recommended path.

- **Recommended (v7)**: live workspaces and conversation bodies live on a LOCAL disk (e.g.
  `D:\WorkBuddy\...`). WPS cloud is used ONLY as a **weekly one-way incremental backup pipe**
  (`mtime`+`size` manifest, write-only, never delete cloud-side files). Cross-device handoff is
  explicit via `HANDOFF.md`.
- **Legacy (v6 and earlier, reference & recovery only)**: the three-layer architecture below —
  `workbuddy.db` local, subdirectories symlinked into WPS cloud, `C:\WorkBuddy` unified by Junction,
  `watch_sync.py` v2.2 + `watchdog.bat` auto-daemon, `sync_identity.py` transit channel. Kept for
  users still on it and for recovery — do NOT start new dense-development workspaces this way.

> ℹ WorkBuddy 5.4.7 users: conversation bodies lost on restart (list stays, content blank). The
> skill is disk-based so it still works through that period; see the "Emergency Persistence:
> 5.4.7 IndexedDB Loss Era SOP" section in `SKILL.md`.

**Core pain point (still valid)**: `workbuddy.db` (SQLite) cannot be written by two computers at
once — conversation records overwrite each other; each PC's `C:\Users\<name>` path also differs.

**Why real-time cloud sync fails (field-tested)**: `-副本<ts>` conflict copies (even from ONE
machine writing repeatedly), silent rollback that a write-then-read cannot catch, test files
pushed out of the runner's glob while tests still pass, deletions resurrected by the client,
junction re-upload / reverse-pull, daemon fights, ~1.45 MB/min bulk operations. See the full
failure-mode table in `SKILL.md` → "Why real-time cloud sync is NOT the default".

**Weekly backup rules**: seed the manifest from the cloud

**Run it (the tool is `weekly_backup.py`, shipped with this skill):**

```bash
# NEW INSTALL (cloud empty): preview, then first FULL backup
python weekly_backup.py --src "<local-workspace>" --dst "<cloud-backup-folder>" --dry-run
python weekly_backup.py --src "<local-workspace>" --dst "<cloud-backup-folder>" --confirm

# MIGRATED FROM LIVE SYNC (cloud already has files): seed baseline -> first run is incremental
python weekly_backup.py --src "<local-workspace>" --dst "<cloud-backup-folder>" --seed

# EVERY WEEK: preview then confirm; --status to inspect
python weekly_backup.py --src "<local-workspace>" --dst "<cloud-backup-folder>" --dry-run
python weekly_backup.py --src "<local-workspace>" --dst "<cloud-backup-folder>" --confirm
python weekly_backup.py --src "<local-workspace>" --dst "<cloud-backup-folder>" --status
```

It writes `weekly_backup_manifest.json` and `weekly_backup.log` into the cloud folder; a second
dry-run reporting `nothing changed - already up to date` means the backup is current. Every
error prints a plain-language hint ("source is not a directory", "manifest unreadable", ...),
with the full translation table in `SKILL.md` -> Troubleshooting.
 (so week one is incremental, not a full
recopy); copy only new/changed files; WRITE-ONLY to cloud, never read back, never delete cloud
files; skip `node_modules` / `.git` / `dist` / caches / `-副本*`; verify with a dry run (0 changes
right after a success).

## What Changed in v7 (vs v6)

| Change | Description |
|--------|-------------|
| **Doctrine reversal (MAJOR)** | v6's contract "WPS real-time sync = default" is inverted. v7 default = local-first live work + weekly one-way incremental cloud backup; real-time sync is documented as unsafe for dense work and demoted to legacy/reference. |
| **New opening chapters** | `SKILL.md` now starts with "Why real-time cloud sync is NOT the default" (failure-mode table) and "Recommended mode: local-first + weekly backup pipe" (architecture + 5 rules). Quick Start rewritten around the local-first path. |
| **Legacy clearly marked** | Old three-layer architecture under "Overview (legacy)", 7-step Workflow flagged LEGACY — for existing users and recovery only. |
| **Field knowledge preserved** | All hard-won pitfall sections (Three-Axe safe deletion, artifact-index zombie, state conflicts, file-count guard, 5.4.7/5.5.x recovery) and script resources kept unchanged — they apply to both modes. |
| **No script behavior change** | Pure usage-contract and documentation refactor; helpers unchanged. |

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
├── sync_identity.py                  # User identity & memory & HANDOFF transit sync script (v3.8: v3.6 MEMORY.md boundary + v3.7 write-back disabled + memory .md-only + artifact-index cleanup + v3.9 daily-log per-workspace namespacing)
├── cleanup_artifact_index.py         # Dead artifact-index URI cleaner (run manually, or via a daily WorkBuddy automation bound to the current workspace)
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

## D-Drive AI Scratch Area (Keeping the System Drive Lean)

The C: drive is the system drive. Full-scale test configs, temporary caches,
build artifacts, and script logs produced during AI coding all default to
writing there, which fills C: up fast. This skill ships with the following
conventions:

- **Iron rule**: never create new folders directly at the D: drive root; all
  AI artifacts go under `D:\WorkBuddy\<purpose>\`.
- **Standard entry-point examples**:
  - `D:\WorkBuddy\_cd\`: scripts and logs (including log-cleanup scripts)
  - `D:\WorkBuddy\_py\`: pip `--target` dependencies
  - `D:\WorkBuddy\tmp\`: temporary files
  - `D:\WorkBuddy\<test-workspace>\`: persistent full-test workspace (never
    run tests on C:)
  - `D:\WorkBuddy\<build-output>\`: build output
  - `D:\WorkBuddy\npm-cache\` / `D:\WorkBuddy\npm-global\`: Node/npm caches
  - `D:\WorkBuddy\backups\` / `D:\WorkBuddy\deploy\`: backups and deploy
    artifacts
- **Deliverable boundary**: final deliverables and workspace data still go to
  `C:\WorkBuddy\<workspace>\` (synced to the cloud drive via the WPS
  Junction); the test/cache/temp directories under `D:\WorkBuddy\` are **kept
  out of the WPS sync scope** to avoid polluting the cloud drive and wasting
  sync bandwidth.
- **Cleanup**: run the cleanup script periodically to delete expired logs and
  temp files under `D:\WorkBuddy\_cd\` and `D:\WorkBuddy\tmp\`. Always
  dry-run first to confirm.
- **Migration legacy**: if historic folders already exist at the D: root,
  move them wholesale under `D:\WorkBuddy\` and point scripts and shortcuts
  at the new paths.

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

### 3. Start the Auto-Sync Daemon (LEGACY real-time pipe — reference/recovery only)

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

v3.6 + v3.7 prevents recurrence. For already-overwritten files: there is no clean backup in the transit directory or the sync namespace, so you must go back to the corresponding workspace and **manually rebuild them selectively** from conversation history/project output (do not let the AI batch-rebuild automatically — it can easily write the polluted content back).

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
