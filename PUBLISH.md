# GitHub 发布指南：workbuddy-cross-device-sync

> 全程复制粘贴，不用动脑。

---

## 第一步：在 GitHub 上创建仓库

打开 https://github.com/new

**复制下面的内容填进去：**

| 字段 | 复制这个 |
|------|---------|
| Repository name | `workbuddy-cross-device-sync` |
| Description | Hybrid cross-device sync for WorkBuddy: local db isolation, workspace-state sync, HANDOFF.md v2 handoff, conversation export. Via WPS Cloud. |
| Public / Private | 选 **Public** |
| 其他选项 | 全部不勾 |

点 **Create repository**。

创建后会跳转到一个"Quick setup"页面，**什么都不要点**，直接看下一步。

---

## 第二步：在 PowerShell 里执行（一行一行复制）

> ⚠️ 打开 PowerShell（Win+X → 终端），逐行复制，每行回车。

```powershell
cd C:\Users\62588\.workbuddy\skills\cross-device-sync
```

```powershell
git init
```

```powershell
git add .
```

```powershell
git commit -m "feat: v4 — HANDOFF.md v2 (machine+AI sections), AI_HANDOFF_GUIDE.md, conversation export, workspace_sync.py"
```

```powershell
git branch -M main
```

```powershell
git remote add origin https://github.com/<你的GitHub用户名>/workbuddy-cross-device-sync.git
```

> ⚠️ 把 `<你的GitHub用户名>` 换成你的 GitHub 用户名！

```powershell
git push -u origin main
```

---

## 第三步：设置仓库信息（GitHub 网页上操作）

打开你的仓库主页（https://github.com/<你的用户名>/workbuddy-cross-device-sync），点右侧齿轮 ⚙️ 或直接往下翻。

### 3.1 添加 Topics（标签）

找到 **Topics** 区域，逐个粘贴添加：

```
workbuddy
cross-device
sync
windows
wps-cloud
session-recovery
session-merge
handoff
productivity
python
devtools
```

### 3.2 添加 About 描述

在仓库名称下方的 Description 栏已经填好了。如果想更详细，复制这个到 **About**：

```
🔄 Hybrid cross-device sync for WorkBuddy: local db isolation, workspace-state sync, HANDOFF.md v2, conversation export. Via WPS Cloud.
```

### 3.3 仓库设置

- 勾选 ✅ **Releases**（如果有的话）
- 勾选 ✅ **Packages**（如果有的话）
- **不要**勾选 "Template repository"

---

## 仓库最终展示效果预览

创建完成后，你的仓库页面会显示：

```
📦 workbuddy-cross-device-sync
🔄 Hybrid cross-device sync for WorkBuddy

⭐ 0  |  🍴 0

Topics: workbuddy · cross-device · sync · windows · wps-cloud · session-recovery · session-merge · handoff · productivity · python · devtools

📁 文件列表：
  .gitignore
  README.md              ← 自动渲染为首页
  PUBLISH.md             ← 本文件（发布指南）
  SKILL.md               ← 技能定义（完整指南）
  AI_HANDOFF_GUIDE.md   ← AI 跨设备交接操作指南（两台 AI 共读）
  fix_db_isolation_v3.ps1      ← 数据库隔离（核心）
  fix_workspace_state_sync.ps1 ← workspace-state 同步
  scripts/
    fix_paths.py              ← 四步路径修复（JSON + DB + 缓存合并 + JSONL cwd）
    restore_and_merge.py      ← 会话恢复 & 合并工具
    workspace_sync.py         ← 机械同步脚本（DB 修复 + 交接单生成）
```

---

## 搞完之后

告诉我就行，没什么需要再做的了。以后更新脚本就正常 `git add` → `git commit` → `git push`。
