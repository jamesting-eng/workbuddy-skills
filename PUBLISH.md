# GitHub 发布指南：workbuddy-skills / cross-device-sync

> 全程复制粘贴，不用动脑。本技能文件**直接位于 `workbuddy-skills` 仓库根目录**（平铺，无子目录），不是独立仓库。

---

## 重要修正（v6）

- 技能文件**平铺在 `workbuddy-skills` 仓库根目录**（不是独立仓库、不是 `cross-device-sync/` 子目录）。
- v6 新增文件：`watchdog.bat`（看门狗 v2，与 watch_sync.py v2.2 配套）。
- `sync_identity.py` 升到 v3.6（MEMORY.md 互覆污染根治），`watch_sync.py` 升到 v2.2（卡死自愈）。
- ⚠️ `_sync/` 目录不在守护进程监听范围：升级脚本后，**必须手动**把新版
  `watch_sync.py` + `watchdog.bat` 复制到另一台电脑的 `C:\WorkBuddy\_sync\` 同路径。
- ⚠️ `watchdog.bat` 保持纯 ASCII（或 GBK）编码，UTF-8 中文会 CMD 乱码。

## 安全提醒（PAT）

- **不要把 GitHub PAT 贴进任何聊天或提交内容**。一旦泄露立即去 GitHub 撤销
  （Settings → Developer settings → Personal access tokens）。
- 推送时如需临时用 PAT：clone URL 里嵌 token → push 完成后立即
  `git remote set-url origin https://github.com/<user>/workbuddy-skills.git` 剥离。
- 公司机沙箱无外网时先 `export http_proxy=http://127.0.0.1:7890 && export https_proxy=http://127.0.0.1:7890`（Clash）。

---

## 第一步：拿到 workbuddy-skills 仓库

如果本地还没有克隆：

```powershell
cd C:\Users\$env:USERNAME\Documents\GitHub   # 或任意你喜欢的位置
git clone https://github.com/<你的GitHub用户名>/workbuddy-skills.git
cd workbuddy-skills
```

如果已有克隆，先拉最新：

```powershell
cd <workbuddy-skills 本地路径>
git pull
```

---

## 第二步：放入技能目录

把本地 `_sync/` 里的最新技能文件复制/覆盖到仓库根目录：

```
workbuddy-skills/            ← 仓库根目录即技能根
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
├── push.bat / pull.bat / 一键同步.bat / start_sync.bat / watchdog.bat
└── scripts/
    ├── fix_paths.py
    └── restore_and_merge.py
```

> ⚠️ `secret.txt` 含真实暗号，**不要提交**（已在 .gitignore 思路中排除，或手动勿 add）。

---

## 第三步：提交并推送

```powershell
git add -A
git commit -m "feat(cross-device-sync): v6 — sync_identity v3.6 (MEMORY.md pollution fix), watch_sync v2.2 (hang self-heal), watchdog.bat v2 (liveness check)"
git push origin main
```

---

## 第四步：仓库信息（GitHub 网页，可选）

- 确认仓库 Description：`🔄 Hybrid cross-device sync for WorkBuddy`
- Topics 可加：`workbuddy cross-device sync windows wps-cloud session-recovery python devtools`

---

## 验证

推送后访问 `https://github.com/<用户名>/workbuddy-skills` ，确认仓库根目录
下的文件都已更新（尤其是 README.md、SKILL.md、watch_sync.py、find_junk.py、clean_junk.py）。

---

## 以后更新

改完本地 `_sync` 里的脚本后，把变更同步到 `workbuddy-skills` 仓库根目录再：
`git add` → `git commit` → `git push`。
