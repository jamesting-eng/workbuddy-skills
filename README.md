# Cross-Device Sync for WorkBuddy

让 WorkBuddy 在多台 Windows 电脑之间无缝同步 — 在公司创建的对话，回家继续；家里的任务，公司接着干。

## 这是什么？

一个 [WorkBuddy](https://www.codebuddy.cn) 技能，解决多台 Windows 电脑之间 WorkBuddy 数据的同步问题。

**核心痛点**：`workbuddy.db`（SQLite）不能被两台电脑同时读写 — 会导致对话记录互相覆盖。每台电脑的 Windows 用户目录也不同，导致会话文件路径失效。

**解决方案（v4 混合架构）**：
- `workbuddy.db` 本地独立（不覆盖）
- 子目录通过符号链接同步 WPS 云盘
- 工作区通过 Junction 统一为 `C:\WorkBuddy\`
- 通过 `HANDOFF.md` 交接单 + `AI_HANDOFF_GUIDE.md` 实现跨设备任务接续

## 目录结构

```
cross-device-sync/
├── SKILL.md                          # 技能定义 & 完整操作指南
├── README.md                         # 本文件
├── PUBLISH.md                       # GitHub 发布指南
├── AI_HANDOFF_GUIDE.md            # AI 跨设备交接操作指南（两台 AI 共读）
├── sync_identity.py                  # 用户身份 & 记忆同步脚本（v3.1）
├── fix_db_isolation_v3.ps1           # 数据库隔离脚本（核心）
├── fix_workspace_state_sync.ps1      # workspace-state 同步修复
└── scripts/
    ├── fix_paths.py                  # 路径修复脚本（四步）
    ├── restore_and_merge.py          # 会话恢复 & 合并工具
    └── workspace_sync.py            # 机械同步脚本（DB 修复 + 交接单生成）
```

## 它能做什么

| 功能 | 说明 |
|------|------|
| **混合架构同步** | `workbuddy.db` 本地独立（不怕覆盖），子目录/工作区同步 WPS 云盘 |
| **数据库隔离** | `fix_db_isolation_v3.ps1` 一键将 `.workbuddy` 从云端 symlink 转为本地目录 |
| **workspace-state 同步** | 新建工作区自动出现在另一台电脑侧边栏 |
| **HANDOFF.md v2 交接单** | 结构化交接单，分机器生成区 + AI 手写区，含对话摘要导出、同步暗号验证 |
| **对话导出** | 重要对话全文导出到 `_sync/conversations/`，另一台电脑可读取完整上下文 |
| **AI 操作指南** | `AI_HANDOFF_GUIDE.md` 详细规定两台 AI 的推送/拉取行为，防止遗漏 |
| **路径修复** | 自动修复 JSON session 文件、SQLite 数据库、项目缓存中的路径引用 |
| **缓存合并** | 路径迁移后，自动合并分裂的项目缓存，防止「对话消息消失」 |
| **会话恢复** | 消息缓存丢失时，基于云端摘要 + 项目产出重建可用的会话上下文 |
| **会话合并** | 把分散在多个会话中的相关讨论合并到一个对话中，自动去重、按时间排序 |
| **WAL 强制刷盘** | 关闭前确保 SQLite WAL 数据写入主数据库，避免数据丢失 |
| **用户身份 & 记忆同步** | `sync_identity.py` 通过 `_sync/identity\` 中转，同步 `~/.workbuddy/memory/` 等用户级文件，确保每日交接单跨设备可读 |

## 前置条件

- Windows 10/11
- WPS Office（带云盘功能，同步到本地）
- **管理员权限**（创建 Junction 需要）
- Windows 上已安装 WorkBuddy

## 快速开始

### 1. 配置同步（每台电脑各运行一次，约 15 分钟）

```powershell
# ① 数据库隔离：把 workbuddy.db 从云盘分离到本地
.\fix_db_isolation_v3.ps1

# ② workspace-state 同步：新建工作区两边都能看到
.\fix_workspace_state_sync.ps1

# ③ 创建 C:\WorkBuddy Junction 统一工作目录路径
New-Item -ItemType Junction -Path "C:\WorkBuddy" `
    -Target "$env:USERPROFILE\Documents\WPSDrive\<id>\WPS云盘\WorkBuddy"
```

### 2. 修复路径

```bash
# 在每台电脑上运行，统一所有会话路径
python scripts/fix_paths.py
```

脚本会自动完成四步：JSON 修复 → 数据库修复 → 项目缓存合并 → JSONL cwd 路径修复。

### 3. 使用交接单（跨设备任务接续）

**离开电脑前** — 说"生成交接单"或"同步任务"：
- AI 自动更新 `C:\WorkBuddy\_sync\HANDOFF.md`
- 包含活跃项目、任务进度、对话摘要、下一步行动
- 可选：加入测试暗号验证同步链路

**到另一台电脑后** — 说"拉取同步"或"继续上次"：
- AI 第一个动作：读取 `C:\WorkBuddy\_sync\HANDOFF.md`
- 展示上一次的工作状态和上下文
- 无缝接续任务

> ⚠️ **重要**：交接单机制依赖 `C:\WorkBuddy` Junction → WPS 云盘。`HANDOFF.md` 是两台电脑的 AI 之间唯一的共享信息通道。

## 注意事项 & 踩过的坑

这里记录了实际使用中踩过的所有坑，每一个都有血泪教训：

| 坑 | 现象 | 原因 | 解决 |
|----|------|------|------|
| **db 被同步覆盖** | 公司电脑对话消失，家里对话出现在公司 | `workbuddy.db` 在 WPS 云盘里被两台电脑共享 | 运行 `fix_db_isolation_v3.ps1`（v3 架构核心） |
| **新建工作区不显示** | 公司建的工作区，家里侧边栏没有 | `workspace-state.json` 是本地文件未同步 | 运行 `fix_workspace_state_sync.ps1` |
| **WAL 未刷盘** | 关闭后最新对话丢失 | WorkBuddy 没完全退出，WAL 文件残留 | 确认进程完全退出，WAL 文件消失 |
| **workspace-state.json 为空** | 侧边栏只显示1个工作区 | WPS 同步了旧版本或客户端覆盖了 | 从 DB 重建 workspace-state.json |
| **会话被软删除** | DB 有记录但侧边栏看不到 | WorkBuddy 客户端同步时标记 deleted_at | `UPDATE sessions SET deleted_at = NULL` |
| **缺少 .workbuddy 标记** | 工作区目录存在但 sidebar 不显示 | 目录缺少 `.workbuddy/memory/` 子目录 | 手动创建标记目录 |
| **路径分隔符** | 恢复的会话不在列表显示 | cwd 用了 `C:/...` 正斜杠 | 必须用 `C:\...` 反斜杠 |
| **user_id** | 同上 | 数据库里填了 `"default"` | 必须用真实 UUID，可从已有 session 查询 |
| **时间戳年份** | 显示「56年前」且内容不渲染 | `created_at=0` 或秒级而非毫秒级 | 从 .jsonl 取真实时间戳，确保毫秒级 |
| **对话消失** | 路径修复后历史消息没了 | 项目缓存因路径变更分裂成两份 | `fix_paths.py` 第三步自动合并 |
| **deliver_attachments 静默失败** | 发送的文件对方收不到 | `~/.workbuddy/` 是 symlink 路径 | 先 `cp` 到 `C:\WorkBuddy\` 再 delivery |
| **AI 不知道读交接单** | 换电脑后 AI 说"已经同步好了"但看不到上下文 | AI 没有被指示要先读 HANDOFF.md | 更新 SKILL.md 强制规则（v4 已修复） |

## 常见问题

**Q: 同步后为什么公司电脑的对话在家里看不到？**

**这是设计如此。** `workbuddy.db` 每台电脑独立存储，对话历史不同步。这是为了避免两台电脑同时写同一个数据库导致互相覆盖。跨设备任务接续用"同步任务"生成 `HANDOFF.md` 交接单。

**Q: 新建的工作区别台电脑看不到？**

确认 `workspace-state.json` 是否是符号链接指向 WPS 云盘。如果不是，运行 `fix_workspace_state_sync.ps1`。

**Q: 两台电脑的对话会不会再次被覆盖？**

不会。v3 架构中 `workbuddy.db` 完全在本地，WPS 云盘里根本没有这个文件。

**Q: 能不能用别的云盘？**

理论上可以。核心就是把 `.workbuddy` 符号链接到任意云盘同步目录。但路径替换逻辑需要相应调整。WPS 云盘对国内用户免费且不限速，是最推荐的方案。

**Q: Mac 能用吗？**

目前脚本仅支持 Windows（依赖 PowerShell 的 Junction 和 `C:\` 路径约定）。Mac 用户可以手动创建符号链接并修改脚本中的路径格式。欢迎 PR。

**Q: 交接单机制靠谱吗？**

交接单（`HANDOFF.md`）通过 `C:\WorkBuddy` Junction → WPS 云盘，是两台电脑的 AI 之间唯一的共享信息通道。v2 版本加入了机器生成区 + AI 手写区分离、对话摘要导出、同步暗号验证，实测可靠。详见 `AI_HANDOFF_GUIDE.md`。

## 安装为 WorkBuddy 技能

将此仓库克隆到 WorkBuddy 的用户技能目录：

```bash
git clone https://github.com/<your-username>/workbuddy-cross-device-sync.git ~/.workbuddy/skills/cross-device-sync
```

然后在 WorkBuddy 对话中直接说「跨设备同步」或「帮我在多台电脑间同步 WorkBuddy」即可自动触发此技能。

## 许可

MIT License — 随意使用、修改、分发。
