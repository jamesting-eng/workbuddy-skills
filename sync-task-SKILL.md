---
name: sync-task
description: Smart sync for WorkBuddy sessions. Automatically detects which computer you are on and performs backup (work PC) or restore (home PC).
agent_created: true
triggers:
  - "sync task"
  - "sync now"
  - "backup task"
  - "restore task"
  - "task handoff"
  - "generate handoff note"
  - "resume task"
  - "continue last time"
  - "pull sync"
  - "show handoff note"
  - "sync"
  - "continue"
  - "where did we leave off"
  - "pick up where I left off"
  - "back to before"
  - "wrap up"
  - "off work"
  - "switch computer"
---

# Sync Task Skill

## Background

WorkBuddy's database (workbuddy.db) is independent on each of the two computers; conversation history does not sync across devices.
The correct way to continue work across devices is: use the **central handoff note HANDOFF.md** to record current progress, then read it on the other computer to resume work.

**Central handoff note location (single fixed point)**: `C:\WorkBuddy\_sync\HANDOFF.md`

Because `C:\WorkBuddy` is a Windows Junction → WPS cloud drive, this file is the **same physical file** on both computers.

---

## ⚠️ Mandatory Rules (CRITICAL — the AI on both computers must follow these)

### Rule 1: After switching computers, the first action must be reading HANDOFF.md

When the user says "pull sync", "continue last time", "show handoff note", "resume task", or anything implying "I just switched computers":

```
Step 1 (tool call): Read C:\WorkBuddy\_sync\HANDOFF.md
Step 2: Reply to the user based on the file content
```

**Strictly forbidden** to reply with anything about task status before Step 1.
**Strictly forbidden** to say "already synced" or "both sides are configured" without having read HANDOFF.md.

### Rule 2: If you don't know, say you don't know

If you did not see something in HANDOFF.md, say "the handoff note does not mention this; the previous computer may not have recorded it".
**Do not** fill in or guess from your own conversation memory.

### Rule 3: Handoff notes must be complete

When generating HANDOFF.md, it must include:
- Current time, computer name
- Active projects and their status
- Key decisions
- Clear next steps
- Any test message/passphrase the user asked to include

### Rule 4: HANDOFF.md must be updated after any substantive work (added 2026-06-25)

**This rule was long missing — it caused repeated cross-device sync failures.**

After completing any of the following, the AI must immediately update the AI-written section of `C:\WorkBuddy\_sync\HANDOFF.md`:
- Generated new files (reports, code, design drafts, etc.)
- Made key decisions (technology choice, plan change, milestone confirmation)
- Completed a multi-step task (8+ tool calls)
- The user explicitly said "note this down" / "write it to the handoff note"
- The session is about to end and there are substantive outputs

**Do not wait for the user to say "generate handoff note" before updating** — finishing work means proactively pushing to HANDOFF.md.
This is the only shared information channel between the two AIs; not updating it = the AI on the other computer is blind.

### Rule 5: When entering any workspace, you must read the workspace status (added 2026-06-25)

**This closes two blind spots: "returning to an old workspace without knowing where things left off" and "starting a new conversation in the same workspace from scratch".**

When any of the following happens, the AI **must immediately** read the workspace status (no exceptions):
- The user says "continue", "where did we leave off", "pick up where I left off", or "back to before" in a new conversation
- The user switches to another workspace directory
- **The user starts any new conversation within the same workspace (regardless of whether a specific task was mentioned)**
- ⚠️ **The working_memory injected by the system is an outdated static snapshot and cannot replace reading STATUS.md**

**Key principle: for every new conversation in the same workspace, the first tool call must be reading the status file. No exceptions.**

**Mandatory reading order when entering a workspace** (by priority):
```
Step 1: Read {current workspace}/.workbuddy/memory/STATUS.md    ← workspace status snapshot
Step 2: Read {current workspace}/.workbuddy/memory/MEMORY.md     ← workspace long-term memory
Step 3: Read {current workspace}/.workbuddy/memory/{last 3 days}.md  ← recent daily logs
Step 4: Read C:\WorkBuddy\_sync\HANDOFF.md               ← global cross-device handoff
```

If STATUS.md does not exist, at minimum read MEMORY.md + the most recent daily log + HANDOFF.md.
If everything read is empty or outdated, tell the user "no recent status records were found for this workspace".

**Strictly forbidden** to guess "where things left off" without reading the files above.

### Rule 6: When leaving a workspace / after finishing work, the workspace STATUS.md must be updated (added 2026-06-25)

**This is the workspace-level companion to Rule 4 — Rule 4 updates the global HANDOFF.md; Rule 6 updates the current workspace's STATUS.md.**

After completing any of the following, the AI must immediately update `{current workspace}/.workbuddy/memory/STATUS.md`:
- Generated new files or modified important files
- Made key decisions
- Completed a multi-step task (8+ tool calls)
- The user said "wrap up" / "off work" / "switch computer" / "that's about it for today"
- The session is about to end and there are substantive outputs

STATUS.md format (lightweight; key information only):
```markdown
# Workspace Status — {project name}

> Last updated: {time} | Computer: {computer name}

## Project Goal
{one sentence}

## Latest Progress
- {point 1}
- {point 2}
- {point 3}

## Current TODOs
- [ ] {todo 1}

## Recent Conversation Summary
| Date | Computer | What was done |
|------|----------|---------------|

## Key Files
- `{path}` — {description}
```

**If STATUS.md does not exist, create it.**
**If file paths differ across computers (venv, etc.), note both computers' paths.**

---

## Detection Logic

1. **Check the computer name** (via the `hostname` command):
   - Work PC: `DESKTOP-JB3DUCH` (username 62588)
   - Home PC: `LAPTOP-5RNP9DN3` (username James Ting)

2. **Perform the corresponding action**:
   - About to leave the current computer → Action A: generate handoff note
   - Arrived at the new computer → Action B: read handoff note

---

## Action A: Generate Task Handoff Note (before leaving the computer)

When the user says "sync task", "backup task", "generate handoff note", etc., perform the following steps:

### Step 1: Gather information

Organize from the current conversation context:
- What project/task is currently in progress?
- What step has it reached?
- Key decisions and file paths
- What is planned next?
- Did the user ask to include a test message/passphrase?

### Step 2: Write to the central handoff note

**Single path**: `C:\WorkBuddy\_sync\HANDOFF.md`

```markdown
# Cross-Device Handoff Note

**Generated at**: {current time}
**Generated on**: {current computer name}

---

## {user-requested test content/passphrase (if any)}

---

## Active Projects

{list projects and their status}

## Current Task

{task title and brief description}

## Completed

{what has been done}

## Next Steps

{what to continue doing after switching computers}

## Important Information

{file paths, key variables, caveats}

---
*This file is shared across devices via C:\WorkBuddy Junction → WPS cloud drive*
```

### Step 3: Prompt the user

```
✅ Handoff note generated: C:\WorkBuddy\_sync\HANDOFF.md

You can now:
1. Wait for the WPS cloud drive to finish syncing (green checkmark visible)
2. Close WorkBuddy
3. Switch to the other computer and say "pull sync" to resume
```

---

## Action B: Read Handoff Note (after arriving at the new computer)

### Step 1 (must be the first tool call): Read the central handoff note

```
Read C:\WorkBuddy\_sync\HANDOFF.md
```

### Step 2: Present the content

Show the handoff note content to the user, including:
- Generation time and computer
- Active projects and their status
- Current task and progress
- Next steps
- Any test passphrase (if present)

### Step 3: Ask whether to continue

```
I found the handoff note left by {computer name} at {time}.

{summary}

Continue?
```

---

## Notes

1. **There is only one HANDOFF.md**: `C:\WorkBuddy\_sync\HANDOFF.md`; it is not inside any workspace directory
2. **No need to sync workbuddy.db**: each computer having its own independent database is normal
3. **If the file cannot be read**: prompt the user to check whether the WPS cloud drive has synced (wait for the green checkmark), or to generate the handoff note on the previous computer first
4. **Conversation history does not cross devices**: only information recorded in the handoff note can be carried over
5. **STATUS.md is the workspace-level relay baton**: each workspace's `.workbuddy/memory/STATUS.md` is maintained independently and does not overwrite each other
6. **Multiple conversations in the same workspace**: the AI in every conversation reads and writes the same STATUS.md, so a new conversation can pick up right where things left off by reading STATUS.md
7. **⚠️ working_memory is unreliable (highest-priority warning)**

   Each conversation round, the system automatically injects `working_memory` (project background, recent activity, etc.).
   **This is a static snapshot and may reflect state from days or even weeks ago.**

   - Wrong: skipping reading STATUS.md because working_memory contains project info
   - Correct: **unconditionally read the on-disk files first** (STATUS.md > daily log > HANDOFF.md)

   Judging progress from outdated working_memory = navigating with an old map = guaranteed failure.

   **This rule has the highest priority and overrides all other rules.**

---

## Action C: Workspace Switching — Status Handoff (entering an old workspace / starting a new conversation)

When the user says "continue" / "where did we leave off" / "pick up where I left off" within a workspace, or **the user starts any new conversation within the same workspace**:

### Step 1: Read the workspace status (**must be the first tool call**, no exceptions)

⚠️ Do not skip this step just because the system injected working_memory. working_memory is outdated.

Read in priority order:

```
1. Read {current workspace}/.workbuddy/memory/STATUS.md
2. Read {current workspace}/.workbuddy/memory/MEMORY.md
3. List the daily logs under {current workspace}/.workbuddy/memory/ and read the last 3 days
4. Read C:\WorkBuddy\_sync\HANDOFF.md
```

### Step 2: Present a status summary

```
📋 {workspace name} status summary

Last active: {time} | {computer}
Latest progress:
  - {point 1}
  - {point 2}
Current TODOs:
  - [ ] {todo 1}

Continue, or start a new task?
```

### Step 3: Act based on the user's reply

- "Continue" → pick up from the TODOs / latest progress
- "Start a new task" → add a new entry to STATUS.md (without affecting previous progress)
- The user specified what to do → do it directly

---

## Action D: Leaving a Workspace — Update Status (wrapping up / off work / switching computers)

When the user says "wrap up" / "off work" / "switch computer" / "that's about it for today", or the session is about to end:

### Step 1: Update the workspace STATUS.md

```
Read {current workspace}/.workbuddy/memory/STATUS.md  (if it exists)
Write/Edit STATUS.md → update:
  - Last updated time
  - Latest progress (add this conversation's outputs)
  - Current TODOs (completed → check off; new ones → add)
  - Append a row to the recent conversation summary table
```

### Step 2: Update the global HANDOFF.md

```
Read C:\WorkBuddy\_sync\HANDOFF.md
Edit → update the AI-written section (current project status + recent conversation summary)
```

### Step 3: Prompt the user

```
✅ Status saved
  - Workspace STATUS.md: {path}
  - Global HANDOFF.md: C:\WorkBuddy\_sync\HANDOFF.md

Next time you open this workspace on any computer, just say "continue" to pick up.
```
