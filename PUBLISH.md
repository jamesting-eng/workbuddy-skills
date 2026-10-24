# GitHub Publishing Guide: workbuddy-skills / cross-device-sync

> Pure copy-paste, no thinking required. This skill's files **live directly in the `workbuddy-skills` repo root** (flat, no subdirectories), not as a standalone repo.

---

## Important Corrections (v6)

- Skill files are **flat in the `workbuddy-skills` repo root** (not a standalone repo, not a `cross-device-sync/` subdirectory).
- New in v6: `watchdog.bat` (watchdog v2, companion to watch_sync.py v2.2).
- `sync_identity.py` bumped to v3.6 (root fix for MEMORY.md cross-overwrite pollution), `watch_sync.py` bumped to v2.2 (hang self-heal).
- ⚠️ The `_sync/` directory is not covered by the daemon's watch scope: after upgrading the scripts, you **must manually** copy the new
  `watch_sync.py` + `watchdog.bat` to the same path under `C:\WorkBuddy\_sync\` on the other computer.
- ⚠️ Keep `watchdog.bat` pure ASCII (or GBK) encoded; UTF-8 Chinese text garbles in CMD.

## Security Reminder (PAT)

- **Never paste a GitHub PAT into any chat or commit**. If leaked, revoke it on GitHub immediately
  (Settings → Developer settings → Personal access tokens).
- If you need to use a PAT temporarily when pushing: embed the token in the clone URL → after the push completes, immediately
  strip it with `git remote set-url origin https://github.com/<user>/workbuddy-skills.git`.
- If the work machine's sandbox has no internet, first run `export http_proxy=http://127.0.0.1:7890 && export https_proxy=http://127.0.0.1:7890` (Clash).

---

## Step 1: Get the workbuddy-skills repo

If not cloned locally yet:

```powershell
cd C:\Users\$env:USERNAME\Documents\GitHub   # or any location you prefer
git clone https://github.com/<your-GitHub-username>/workbuddy-skills.git
cd workbuddy-skills
```

If already cloned, pull the latest first:

```powershell
cd <local path to workbuddy-skills>
git pull
```

---

## Step 2: Place the skill files

Copy/overwrite the latest skill files from the local `_sync/` into the repo root:

```
workbuddy-skills/            ← repo root = skill root
├── SKILL.md
├── README.md
├── PUBLISH.md
├── AI_HANDOFF_GUIDE.md
├── sync_identity.py
├── watch_sync.py
├── find_junk.py
├── clean_junk.py
├── workspace_sync.py
├── secret.txt.example
├── fix_db_isolation_v3.ps1
├── fix_workspace_state_sync.ps1
├── push.bat / pull.bat / one-click-sync.bat / start_sync.bat / watchdog.bat
└── scripts/
    ├── fix_paths.py
    └── restore_and_merge.py
```

> ⚠️ `secret.txt` contains the real passphrase; **do not commit it** (excluded via the .gitignore approach, or just don't `git add` it manually).

---

## Step 3: Commit and push

```powershell
git add -A
git commit -m "feat(cross-device-sync): v6 — sync_identity v3.6 (MEMORY.md pollution fix), watch_sync v2.2 (hang self-heal), watchdog.bat v2 (liveness check)"
git push origin main
```

---

## Step 4: Repo metadata (GitHub web UI; the API cannot change it, so it must be clicked once manually) ✅ Done (2026-08-15); no further action needed

1. Open https://github.com/jamesting-eng/workbuddy-skills
2. About section, top right → pencil icon ✏️
3. Fill in the Description:

```
Seamless sync of WorkBuddy / CodeBuddy across multiple Windows PCs — WPS cloud transit + handoff notes + automatic daemon
```

4. In the same dialog, enter Topics one by one (press Enter after each):

```
codebuddy  workbuddy  cross-device-sync  wps-cloud  sqlite  windows
```

> Effect: anyone searching `codebuddy` / `workbuddy` / `sync` will hit this repo; the search results make its purpose clear at a glance.

---

## Verification

After pushing, visit `https://github.com/<username>/workbuddy-skills` and confirm the files in the repo root
have all been updated (especially README.md, SKILL.md, watch_sync.py, find_junk.py, clean_junk.py).

---

## Step 5: Publish to SkillHub (recommended CLI channel; tested and working)

### One-time preparation

1. Register on skillhub.cn + complete identity verification; create an API Token (`skh_...`) in your personal center
2. Get the CLI (single-file Python, no installation needed):
   ```bash
   curl -fsSL https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/install/latest.tar.gz | tar -xz
   # This extracts cli/skills_store_cli.py; run it directly with the local python
   ```
3. Add the SkillHub-required fields to the SKILL.md frontmatter: `slug` / `displayName` / `version` / `summary` / `tags` / `license`

### Publishing flow (on Windows, remember `export PYTHONIOENCODING=utf-8` to avoid GBK encoding errors)

```bash
python skills_store_cli.py login --key skh_your-token --host https://api.skillhub.cn
python skills_store_cli.py publish ./publish-dir --dry-run     # pre-check
python skills_store_cli.py publish ./publish-dir --changelog "..." --json
# On success: ok:true + skillId returned; reviewStatus=pending, awaiting review (1-7 business days)
```

### ⚠️ Platform file-type whitelist (types that have actually been rejected)

| Rejected file | Handling |
|---|---|
| `.gitignore` | Exclude from the publish directory (repo artifact; not part of the skill package) |
| `LICENSE` (no extension) | Rename to `LICENSE.txt` (publish directory only; keep the extension-less `LICENSE` in the GitHub repo so it gets recognized) |
| `secret.txt.example` | Rename to `secret-example.txt`, and update all references in docs accordingly |
| **All `.bat` files** | Exclude; use **`watchdog.py`** (a Python port of watchdog.bat) for the watchdog, and python-equivalent commands for the other bat files (an explanation section exists in the README) |

`.py` / `.md` / `.ps1` / `.yaml` / `.txt` have been tested and pass. `dist/cross-device-sync/` is the currently compliant sample publish directory.

### After publishing

- Monitor: check the review status under "My Skills" in the developer console (security scan → content review → listing)
- Rejections come with a reason; fix it and publish again
- Iterating versions: bump `version` in `manifest.yaml` and SKILL.md, then publish again

## Future Updates (iron rule: GitHub and SkillHub must be released in sync, both ends)

> **Versions must match**: every version update must be released on both GitHub and SkillHub, with the same version number.
> Releasing on only one end = the release is incomplete. GitHub About/Topics are already configured (2026-08-15); no need to repeat that step.

### Dual Release Checklist (execute in order)

1. **Bump the version number (must be identical in both places)**: `version` in `manifest.yaml` + `version` in the SKILL.md frontmatter
2. **Update the publish directory**: sync changed files into `dist/cross-device-sync/` (mind the whitelist: no `.bat`, `LICENSE.txt`, `secret-example.txt`)
3. **GitHub end**:
   ```powershell
   git add -A
   git commit -m "feat(cross-device-sync): vX.Y — one-line change summary"
   git push origin main   # home machine needs the Clash proxy first; use a PAT once and discard it
   ```
4. **SkillHub end** (assuming the CLI is already logged in):
   ```bash
   export PYTHONIOENCODING=utf-8
   python skills_store_cli.py publish ./dist/cross-device-sync --changelog "..." --json
   ```
5. **Verify**: GitHub repo page version = SkillHub console "My Skills" version = `manifest.yaml` version; all three must match for the release to be complete
6. If the SkillHub review is rejected: fix per the reason and publish again, **adding the matching commit on the GitHub end** (e.g., doc/whitelist fixes) to keep both ends consistent

### Pre-publish full audit (one-shot correctness -- no repeat releases)

SkillHub has **no unpublish API**, so a sloppy release leaves permanent junk versions behind.
Before EVERY publish, walk all files and tick every box. Do not publish until all are ticked.

- [ ] **Language**: SkillHub tree = **100% Chinese**; GitHub tree = **100% English**. Scripts
      (`.py` / `.bat` / `.ps1` / `.cmd`) are NEVER translated. (Historic failure: an English
      SKILL.md was shipped to SkillHub twice, costing extra releases.)
- [ ] **Version string in 5 places, byte-identical**: `manifest.yaml` = `SKILL.md` frontmatter =
      `package.py` VERSION = GitHub commit message = SkillHub version.
- [ ] **Release notes / changelog**: read line by line -- right level, right version, **no typos**,
      no stale copy-paste from the previous release.
- [ ] **Changelog = real text, NO file names / paths**, passed inline (never `--changelog <path>`,
      never `@file`); read it back from SkillHub afterwards to confirm it is the text, not a path.
- [ ] **Read every changed file end-to-end** (not just `git diff --stat`).
- [ ] **File inventory**: packaged list matches the expected count (e.g. 23 files); confirm no
      `.gitignore` / `.bat` / extension-less `LICENSE` slipped in (SkillHub rejects those).
- [ ] **Privacy PII grep** across `.py` / `.md` / `.yaml` / `.ps1` / `.bat` / `.cmd` / `.txt`.
- [ ] **`py_compile`** every `.py`; **CRLF + pure ASCII** for every `.bat` / `.cmd`.
- [ ] **Smoke test** the changed script(s), at least `--dry-run`.

### ✅ Released 2026-10-02 as 6.4.0 (GitHub commit `f4cd941` · SkillHub versionId=394425, review pending)

> **Release-timing rule**: the cloud only ever receives a **stable** version. When more changes are
> still expected (e.g. waiting for the official reply to the 2026-09-17 ticket), accumulate them here.
> The local version fields are already bumped to **6.4.0** to record the truth; the cloud publish is
> deferred until the official fix lands, then shipped as a single **6.4.0** (no intermediate SkillHub
> versions).
>
> **Shipped 2026-10-02 (dual-release, both ends)**: GitHub `jamesting-eng/workbuddy-skills` `main` HEAD
> `f4cd941a4f406a83114f63e26d5db26f09f81da8` (59 files pushed; tree prefix `cross-device-sync/`, 63 files in
> subtree); SkillHub `skillId=156632` / `versionId=394425` with a fully-Chinese changelog (6 user-facing bullets,
> no filenames/paths). NOTE: the live repo layout is a `cross-device-sync/` **subdirectory**, not the flat-in-root
> layout described in the v6 corrections above — the publish script pushes to that prefix.

| Item | Level | Note |
|---|---|---|
| `recover_session_jsonl.py`: dedup keyed on `id` alone dropped 1481 legitimate rows | PATCH | now dedups on the full serialized row |
| `recover_session_jsonl.py`: candidate scan did not exclude legacy `c-` dirs | PATCH | could merge between two legacy dirs instead of the canonical `gen3` dir |
| `recover_session_jsonl.py`: new `--exclude <ws-suffix,...>` flag | MINOR | skip the live/current workspace during recovery |
| D:\WorkBuddy AI scratchpad convention + log-cleanup scripts | PATCH | Centralize AI-generated test configs, temp caches, build artifacts, and script logs under `D:\WorkBuddy\<purpose>\`; forbid new folders directly on D:\ root; deliverables still flow through `C:\WorkBuddy\` (WPS Junction); D:\WorkBuddy scratch dirs are excluded from WPS sync; includes log-cleanup scripts. |
| artifact-index zombie root-cause update + self-healing automation | PATCH | Document that the artifact-index directory itself is a WPS-cloud junction, so stale JSONs can be pushed back; note that the old cleanup only ran during sync, leaving a gap for users who rarely sync; add a "artifact-index self-healing cleanup" WorkBuddy automation config: daily, bound to current workspace, `-S` + `--all-sessions --quiet`, one-line output only. |
| .workbuddy data layout: 4 physical dirs (workspace / logs / edgeone-cache / changes-detail) migrated to D:\WorkBuddy\.workbuddy with junctions back; the 22 WPS junctions untouched | MINOR | Frees ~3.4 GB on C:; migration recipe + resumable script pattern documented in SKILL.md (new section after Disk-Space Strategy); documents the mixed layout (.workbuddy root = 22 WPS junctions + 4 physical dirs) and the rule "never relocate WPS-junctioned dirs". Migrated & verified live on the office machine 2026-09-29. |
| 8 WPS-junctioned runtime dirs field-tested as D: junctions + WPS-resurrection lesson + junction-detection pitfall | PATCH | On 2026-10-12 relocated binaries/vendor/blobs/traces/connectors-marketplace/cache/tmp/plugin-marketplace-state-new from WPS-cloud junctions to D:-local junctions. C: entry frees space (junction ~0 bytes) and WorkBuddy runs fine, BUT WPS re-uploads D: contents back to the cloud and a manual cloud delete is resurrected within minutes — confirming "never relocate WPS-junctioned dirs" and that the only clean C:-free path is moving the WPS sync-folder location itself to D: on both machines. Also documents the Python pitfall: `os.path.islink()` returns False for a Windows junction, so detection must use `GetFileAttributesW(p) & 0x400` (FILE_ATTRIBUTE_REPARSE_POINT). Recorded in SKILL.md `.workbuddy Data Layout` + migration recipe. |

**6.4.0 shipped 2026-10-02 (dual-release, both ends).** The first 6 rows above (recover_session
dedup / candidate-exclude / `--exclude` / D:-scratchpad / artifact-index self-heal / 4-physical-dir
migration) were all released in 6.4.0. The last row (8 WPS-junctioned runtime dirs field-test)
shipped as 6.4.1 documentation. 6.4.2 is the evaluation-driven documentation overhaul
(Quick Start / Capability Boundaries / FAQ / Worked Examples / trigger lookup table /
error lookup table) -- see the 6.4.2 entry below.

**Draft 6.4.2 changelog (user-facing -- copy as-is to SkillHub/GitHub, no raw filenames):**

> 6.4.2 — Documentation overhaul per quality evaluation
> - Added Quick Start: a five-step one-time setup checklist, a three-sentence daily routine, and a by-situation reading map, so new users reach a working sync without reading the full document.
> - Added Capability Boundaries: one consolidated section stating what is supported (Windows + WPS, verified in real use), what is not (macOS / Linux, non-WPS cloud drives), what is deliberately NOT synced (the conversation database -- anti-overwrite by design), and the complete list of manual steps.
> - Added FAQ: 10 common questions with direct answers, distilled from the troubleshooting chapters.
> - Added Worked Examples: a sanitized sample handoff note, a healthy sync-status output, and a complete machine-switch walkthrough.
> - Added a trigger lookup table (Step 6) and a Troubleshooting error lookup table, consolidating trigger phrases and error-to-section mappings that were previously scattered or duplicated.
> - Fixed a heading typo and a stale cross-reference. No behavior changes.

**Draft 6.4.0 changelog (user-facing -- copy as-is to SkillHub, no raw filenames):**

> 6.4.0 — Session-history recovery hardening + D-drive scratchpad + .workbuddy layout migration
> - Fixed session-history recovery dropping legitimate records when two sessions shared an ID; recovery now dedups on the full row.
> - Fixed recovery sometimes merging between two legacy path-encoding folders instead of the canonical one.
> - Added an option to skip the currently-active workspace during recovery, so live work is never disturbed.
> - Documented the D:\WorkBuddy scratchpad convention: AI-generated test configs, temp caches, and script logs now live under D:\WorkBuddy\<purpose>\ instead of scattered on the D: root; final deliverables still flow through C:\WorkBuddy (WPS Junction); the D: scratch area is excluded from WPS sync, with log-cleanup scripts provided.
> - Added a daily "artifact-index self-healing" automation recipe: bound to the current workspace, runs cleanup for all sessions, and keeps the IDE artifact panel free of dead entries even when you do not run a manual sync.
> - Moved the skill's four physical data directories (workspace / logs / edgeone-cache / changes-detail) under D:\WorkBuddy\.workbuddy with junctions pointing back, leaving the 22 WPS junctions untouched; frees ~3.4 GB on C: and documents the mixed-layout rule "never relocate WPS-junctioned dirs".

### Release History

| Version | Date | GitHub commit | SkillHub |
|---|---|---|---|
| 6.0.0 | 2026-08-15 | `71a0569` | skillId=156632 / versionId=238390, review pending |
| 6.1.1 | 2026-09-02 | `ceec8af` | skillId=156632; added 5.4.7 IndexedDB emergency persistence SOP + sync_cli.py unified entry point; also upgraded the SkillHub online package from the v5 file set to match GitHub v6 (added watchdog.py / manifest.yaml / LICENSE.txt / sync_identity v3.6 / watch_sync v2.2) |
| 6.3.0 | 2026-09-04 | `b9ad626` | Added the 5.5.x "path re-encoding breaks historical linkage" recovery SOP + `scripts/recover_session_jsonl.py` (id dedup merge, idempotent, atomic replacement); SkillHub changelog fully in Chinese (skillId=156632 / versionId=286824) |
| 6.3.1 | 2026-09-04 | (this commit) | Full English localization of all repo docs and Python comments (functional literals kept with notes); SkillHub side fully Sinicized |
| 6.3.3 | 2026-09-06 | (in-tree; bundled into 6.3.4) | New section "Deleting Files Safely Under WPS Cloud Sync (Three-Axe Method)" covering `python -S` bypass + `os.remove`-only rule + <=40-files-per-worker batch delete; new section "Why Project State and Artifact Lists Sometimes Conflict" covering workspace-state.json sync race, flat-namespace MEMORY.md pollution (7/24 & 7/30 incidents), STATUS.md staleness, daemon leader election; SkillHub changelog fully in Chinese |
| 6.3.4 | 2026-09-07 | (withdrawn, never pushed publicly) | Internal-only test build that inadvertently bundled real machine names, the user's Windows username, the WPS cloud-drive numeric ID, and the project name. Self-withdrawn before any external publish. Superseded by the de-anonymized 6.3.5 below; the 6.3.5 changelog documents what placeholders replaced what identifiers (OFFICE-PC / HOME-PC / Bob / Alice / 123456789 / MyProject etc.) |
| 6.3.5 | 2026-09-07 | (this commit) | v3.8 systematic root fix for the IDE artifact-panel zombie resurrection (WPS path vs local cache conflict): `sync_identity.py` now hard-bounds `.workbuddy/memory/` to `.md` only via `cleanup_memory_non_md()` (kills the "clean locally -> WPS copy reverse-pulls it back" loop), and integrates `cleanup_artifact_index.py` to purge dead artifact-index URIs on every sync (active-only by default, `--all-sessions` to scrub all); bundles the 6.3.3 work (Three-Axe safe deletion + artifact-conflict section). SkillHub changelog fully in Chinese |
| 6.3.6 | 2026-09-07 | (this commit) | SECURITY HARDENING - re-published to clear the 6.3.5 risk flag from the security scan: replaced every unconditional file deletion (cleanup_duplicates / cleanup_memory_non_md in sync_identity.py, temp/target unlink in sync_cli.py, daemon pidfile unlink in watchdog.py / watch_sync.py) with recoverable, opt-in safe_remove() (move-to-quarantine, never hard-delete; CDS_DRY_RUN=1 for audit-only). No change to sync behavior. SkillHub changelog fully in Chinese |
| 6.3.7 | 2026-09-07 | (this commit) | DOC + PUBLISH-HISTORY ALIGNMENT - aligns the SKILL.md / README.md overview sections and the PUBLISH.md release-history table with the actual `sync_identity.py` v3.8 code: the root `### sync_identity.py (v3.6)` heading and the v3.6-only changelog rows in README.md have been updated to walk through v3.6 (MEMORY.md boundary) -> v3.7 (write-back disabled) -> v3.8 (artifact-index + memory .md-only defense). The 6.3.4 row was added to the release-history table to document the internal privacy-leak self-withdrawn test build (de-anonymized 6.3.5 is the actual first public release). No behavior changes; documentation-only. GitHub end pushed via the Git Data API (PAT in `Authorization: token` header, no GCM popup) per the locked-in sandbox publish workflow; SkillHub end re-published with this changelog |
| 6.3.8 | 2026-09-07 | (this commit) | DOC ALIGNMENT CORRECTION — the 6.3.7 alignment still left 5 stale v3.6-only references unfixed (root README.md "What Changed" row + directory-tree comment, dist README.md "What Changed" row, dist SKILL.md Resources heading + the v3.7/v3.8 description block). This release closes them: all four docs (root + dist SKILL.md / README.md) now walk v3.6 (MEMORY.md boundary) -> v3.7 (write-back disabled) -> v3.8 (artifact-index + memory .md-only defense), and the root SKILL.md body now carries the v3.7/v3.8 postscript to match its dist twin. Zero behavior change; documentation-only. GitHub end pushed via the Git Data API (no GCM popup); SkillHub end re-published (version bump required by the no-republish rule). |
| 6.3.9 | 2026-09-07 | (this commit) | BEHAVIOR FIX (v3.9) + SkillHub Chinese-relapse cure — `collect_workspace_memories_to_user()` now namespaces each workspace's daily logs into `LOCAL/memory/<ws_name>/YYYY-MM-DD.md` (subdir per workspace) instead of the flat `LOCAL/memory/YYYY-MM-DD.md` that collided across workspaces by date (the 8/26 board-game vs Legal workspace incident leaked via WPS cloud). Legacy flat daily logs are MOVED (never deleted) to `LOCAL/_v39_legacy_flat_quarantine/`. Also fixes the SkillHub 6.3.8 English-relapse: `package.py` now builds the SkillHub zip from `dist/cross-device-sync/` (Chinese) instead of ROOT (English). GitHub end pushed via the Git Data API (no GCM popup); SkillHub end re-published fully in Chinese (version bump required by the no-republish rule). |
| 6.4.0 | 2026-10-02 | `f4cd941` | Dual-release complete: GitHub tree (under `cross-device-sync/` prefix) 100% English, commit `f4cd941a4f406a83114f63e26d5db26f09f81da8` (59 files pushed, 63 in subtree); SkillHub `skillId=156632` / `versionId=394425` (review pending) with a fully-Chinese changelog (6 user-facing bullets, no filenames). Bundles the 6.3.9-era fixes + MINOR D:\WorkBuddy scratchpad convention + `.workbuddy` layout migration (frees ~3.4 GB on C:). |
| 6.4.1 | 2026-10-12 | — | DOC PATCH: documented the 8 WPS-junctioned runtime-dirs field test (moving them to D:-junctions frees C: space but WPS resurrects the cloud copy within minutes; the only clean C:-free path is relocating the WPS sync-folder location itself, on both machines) and the Python junction-detection pitfall (`os.path.islink()` returns False for junctions; detect via the reparse-point bit instead). Documentation-only. |
| 6.4.2 | 2026-10-23 | dual-release 2026-10-23 | DOC OVERHAUL per TRACE evaluation (4.7/5): five new SKILL.md sections targeting the lowest sub-scores — Quick Start (setup checklist + daily routine + reading map), Capability Boundaries (consolidated from scattered notes), FAQ (10 Q&A), Worked Examples (sanitized handoff-note sample + healthy status output + machine-switch walkthrough), a Step-6 trigger lookup table (deduplicates two scattered trigger listings), and a Troubleshooting error lookup table. Fixed a heading typo and a stale cross-reference. Zero behavior change; documentation-only. Includes the 6.4.1 field-test documentation (8 WPS-junctioned runtime dirs). |
| 6.4.3 | 2026-10-23 | dual-release 2026-10-23 | SECURITY PATCH (privacy): generate_handoff() no longer hardcodes a real passphrase value as its default. Resolution order is now explicit arg > secret.txt (written by update_secret()) > a neutral placeholder, so published code never contains any real passphrase. Behavior is unchanged for machines that have secret.txt in place. Also purged git history of the leaked values by force-pushing a fresh orphan commit onto main. |
| 6.4.4 | 2026-10-24 | (this commit) | FIX: the 6.4.3 SkillHub package accidentally shipped the English (GitHub-source) documentation because a root-to-dist sync overwrote the five Chinese docs. This release restores the Chinese SKILL.md / README.md / AI_HANDOFF_GUIDE.md / sync-identity-guide.md / sync-task-SKILL.md from the 6.4.2 archive, refreshed with the renamed launcher reference. Scripts are identical to 6.4.3 (privacy fix retained). |
