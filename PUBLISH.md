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

### Release History

| Version | Date | GitHub commit | SkillHub |
|---|---|---|---|
| 6.0.0 | 2026-08-15 | `71a0569` | skillId=156632 / versionId=238390, review pending |
| 6.1.1 | 2026-09-02 | `ceec8af` | skillId=156632; added 5.4.7 IndexedDB emergency persistence SOP + sync_cli.py unified entry point; also upgraded the SkillHub online package from the v5 file set to match GitHub v6 (added watchdog.py / manifest.yaml / LICENSE.txt / sync_identity v3.6 / watch_sync v2.2) |
| 6.3.0 | 2026-09-04 | `b9ad626` | Added the 5.5.x "path re-encoding breaks historical linkage" recovery SOP + `scripts/recover_session_jsonl.py` (id dedup merge, idempotent, atomic replacement); SkillHub changelog fully in Chinese (skillId=156632 / versionId=286824) |
| 6.3.1 | 2026-09-04 | (this commit) | Full English localization of all repo docs and Python comments (functional literals kept with notes); SkillHub side fully Sinicized |
