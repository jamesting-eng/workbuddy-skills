# GitHub 发布指南：workbuddy-skills / cross-device-sync

> 全程复制粘贴，不用动脑。本技能文件**直接位于 `workbuddy-skills` 仓库根目录**（平铺，无子目录），不是独立仓库。

---

## 重要修正（v5）

旧版 PUBLISH.md 指导创建**独立仓库** `workbuddy-cross-device-sync`，且误以为技能在
`cross-device-sync/` 子目录。实际情况：技能文件**平铺在 `workbuddy-skills` 仓库根目录**。所以：

- ❌ 不要新建独立仓库
- ❌ 不要套一层 `cross-device-sync/` 子目录（仓库根目录即技能根）
- ✅ 直接把技能文件放进 `workbuddy-skills` 仓库根目录

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
├── push.bat / pull.bat / 一键同步.bat / start_sync.bat
└── scripts/
    ├── fix_paths.py
    └── restore_and_merge.py
```

> ⚠️ `secret.txt` 含真实暗号，**不要提交**（已在 .gitignore 思路中排除，或手动勿 add）。

---

## 第三步：提交并推送

```powershell
git add -A
git commit -m "feat(cross-device-sync): v5 — watch_sync daemon (single-leader), junk cleanup, v3.2 transit channel, portable paths"
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
