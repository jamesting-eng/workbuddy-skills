---
name: sync-identity
description: |
  Cross-device user identity & memory sync script. Via the C:\WorkBuddy\_sync\identity\ transit
  directory, syncs user-level files such as ~/.workbuddy/memory/ between two computers.
  Trigger phrases: "pull sync", "push sync", "cross-device memory".
agent_created: true
---

# sync_identity.py — Cross-Device Identity & Memory Sync

## File Location

`C:\WorkBuddy\_sync\sync_identity.py` (synced across devices via the WPS cloud drive)

## Commands

| Command | Purpose |
|------|------|
| `python sync_identity.py` | Bidirectional sync (newer wins) |
| `python sync_identity.py push` | Force local → cloud drive (run before leaving the computer) |
| `python sync_identity.py pull` | Force cloud drive → local + distribute to all workspaces (run after arriving at the other computer) |

## Sync Scope (v3.1)

- `~/.workbuddy/memory/` ↔ `_sync/identity/memory/` (daily handoff notes, conversation memory)
- `~/.workbuddy/SOUL.md`, `IDENTITY.md`, `USER.md` ↔ `_sync/identity/`
- `~/.workbuddy/workspace-state.json` ↔ `_sync/identity/`
- Each workspace's `.workbuddy/memory/` ↔ `_sync/identity/workspaces/<name>/memory/`

## Usage Flow

### Before leaving the office computer
```bash
python C:\WorkBuddy\_sync\sync_identity.py push
```
After running it, close WorkBuddy, wait 5 seconds for the WAL to flush to disk, then shut down.

### After getting home and turning on the home computer
```bash
python C:\WorkBuddy\_sync\sync_identity.py pull
```
The script automatically distributes the memories on the cloud drive to all local workspaces.

## Verification After pull

Tell the AI: **"pull sync, check the handoff note"**
- It should be able to read the handoff note written on the office computer (`~/.workbuddy/memory/YYYY-MM-DD.md`)
- Each workspace's `.workbuddy/memory/` should contain the same content

## Relationship with workspace_sync.py

| Script | Sync Level | Description |
|------|-----------|------|
| `workspace_sync.py` | Workspace level | Scans C:\WorkBuddy, updates workspace-state.json, generates HANDOFF.md |
| `sync_identity.py` | User level | Syncs identity files such as ~/.workbuddy/memory and distributes them to each workspace |

**Run both for a complete cross-device experience.**

## Troubleshooting

### Handoff note still empty after pull
- Check whether the WPS cloud drive has finished syncing (check the web client for the latest files)
- Verify manually: `cat ~/.workbuddy/memory/2026-06-18.md`

### "File in use" error during push
- Close WorkBuddy first, wait 5 seconds, then retry

### New workspace opened on the home computer cannot read the office workspace's memory
- Fixed in v3.1: pull distributes user-level memory to all local workspaces
- If it still fails, copy manually: `cp ~/.workbuddy/memory/*.md <workspace>/.workbuddy/memory/`
