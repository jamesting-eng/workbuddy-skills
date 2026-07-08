# Cross-Device Sync for WorkBuddy

让 WorkBuddy 在多台 Windows 电脑之间无缝同步 — 在公司创建的对话，回家继续；家里的任务，公司接着干。

## 这是什么？

一个 [WorkBuddy](https://www.codebuddy.cn) 技能，解决多台 Windows 电脑之间 WorkBuddy 数据的同步问题。

**核心痛点**： `workbuddy.db`（SQLite）不能被两台电脑同时读写 — 会导致对话记录互相覆盖。每台电脑的 Windows 用户目录也不同，导致会话文件路径失效。

**解决方案（v5 混合架构）**：

- `workbuddy.db` 本地独立（不覆盖）
- 子目录通过符号链接同步 WPS 云盘
- 工作区通过 Junction 统一为 `C:\WorkBuddy\`
- 通过 `sync_identity.py` **中转通道** + `HANDOFF.md` 交接单 + `AI_HANDOFF_GUIDE.md` 实现跨设备任务接续
- `watch_sync.py` 后台守护进程自动同步（单 leader 选举，根治副本冲突）

> ⚠️ **v3.2 架构修正（重要）**：原计划靠 `C:\WorkBuddy` Junction → WPS 云盘直传 HANDOFF.md，**2026-07 实测该链路失效**。现改为 `sync_identity.py` 中转通道（经 `_sync/identity/` 子目录）同步 HANDOFF.md / 身份文件 / 工作区 memory。本文档与旧版 README 中"Junction 直传"相关描述均已作废。

## 目录结构

```
（本仓库根目录即本技能的全部文件，无需子目录）

├── SKILL.md                          # 技能定义 & 完整操作指南
├── README.md                         # 本文件
├── PUBLISH.md                        # GitHub 发布指南
├── AI_HANDOFF_GUIDE.md               # AI 跨设备交接操作指南（两台 AI 共读）
├── sync_identity.py                  # 用户身份 & 记忆 & HANDOFF 中转同步脚本（v3.5）
├── watch_sync.py                     # 自动同步守护进程（单 leader 选举，v2.0）
├── find_junk.py                      # WPS 冲突副本扫描器（生成 HTML 报告）
├── clean_junk.py                     # WPS 冲突副本清理器（双保险，只删有正本的）
├── workspace_sync.py                 # 机械同步脚本（DB 修复 + 交接单机器区生成）
├── secret.txt.example                # 同步暗号模板（复制为 secret.txt，勿提交真值）
├── fix_db_isolation_v3.ps1           # 数据库隔离脚本（核心，来自 v4）
├── fix_workspace_state_sync.ps1      # workspace-state 同步修复（来自 v4）
├── push.bat                          # 离开电脑前一键推送（handoff + verify）
├── pull.bat                          # 到另一台电脑一键拉取校验
├── 一键同步.bat                       # 拉取 + 启动守护进程
├── start_sync.bat                    # 守护进程开机自启（放 shell:startup）
└── scripts/
    ├── fix_paths.py                  # 路径修复脚本（四步，来自 v4）
    └── restore_and_merge.py          # 会话恢复 & 合并工具（来自 v4）
```

## 它能做什么

| 功能 | 说明 |
|------|------|
| **混合架构同步** | `workbuddy.db` 本地独立（不怕覆盖），子目录/工作区同步 WPS 云盘 |
| **中转通道同步** | `sync_identity.py` 经 `_sync/identity/` 中转 HANDOFF.md / 身份 / memory（v3.2 权威通道） |
| **数据库隔离** | `fix_db_isolation_v3.ps1` 一键将 `.workbuddy` 从云端 symlink 转为本地目录 |
| **workspace-state 同步** | 新建工作区自动出现在另一台电脑侧边栏 |
| **HANDOFF.md v2 交接单** | 结构化交接单，分机器生成区 + AI 手写区，含对话摘要导出、同步暗号验证 |
| **对话导出** | 重要对话全文导出到 `_sync/conversations/`，另一台电脑可读取完整上下文 |
| **AI 操作指南** | `AI_HANDOFF_GUIDE.md` 详细规定两台 AI 的推送/拉取行为，防止遗漏 |
| **自动同步守护进程** | `watch_sync.py` 后台常驻，文件一改自动 push；单 leader 选举避免双机并发写 → 根治副本冲突风暴 |
| **垃圾清理** | `find_junk.py` / `clean_junk.py` 扫描并清理 WPS 产生的 `-副本` 冲突文件 |
| **路径修复** | 自动修复 JSON session 文件、SQLite 数据库、项目缓存中的路径引用 |
| **缓存合并** | 路径迁移后，自动合并分裂的项目缓存，防止「对话消息消失」 |
| **会话恢复** | 消息缓存丢失时，基于云端摘要 + 项目产出重建可用的会话上下文 |
| **会话合并** | 把分散在多个会话中的相关讨论合并到一个对话中，自动去重、按时间排序 |
| **WAL 强制刷盘** | 关闭前确保 SQLite WAL 数据写入主数据库，避免数据丢失 |
| **用户身份 & 记忆同步** | `sync_identity.py` 通过 `_sync/identity/` 中转，同步 `~/.workbuddy/memory/` 等用户级文件 |

## 前置条件

- Windows 10/11
- WPS Office（带云盘功能，同步到本地）
- **管理员权限**（创建 Junction 需要）
- Windows 上已安装 WorkBuddy

## 快速开始

### 1. 配置同步（每台电脑各运行一次，约 15 分钟）

```
# ① 数据库隔离：把 workbuddy.db 从云盘分离到本地
.\fix_db_isolation_v3.ps1

# ② workspace-state 同步：新建工作区两边都能看到
.\fix_workspace_state_sync.ps1

# ③ 创建 C:\WorkBuddy Junction 统一工作目录路径
New-Item -ItemType Junction -Path "C:\WorkBuddy" `
    -Target "$env:USERPROFILE\Documents\WPSDrive\<id>\WPS云盘\WorkBuddy"
```

### 2. 修复路径

```
# 在每台电脑上运行，统一所有会话路径
python scripts/fix_paths.py
```

脚本会自动完成四步：JSON 修复 → 数据库修复 → 项目缓存合并 → JSONL cwd 路径修复。

### 3. 启动自动同步守护进程

```
# 开机自启（推荐）：把 start_sync.bat 放进 shell:startup
# 或手动启动一次：
python watch_sync.py            # 常驻守护（单 leader 模式安全）
python watch_sync.py --status   # 查看监听状态 + leader 状态
```

守护进程会在后台监听源文件变化并自动 push；单 leader 选举确保同一时间只有一台机器写中转目录，根治 WPS 副本冲突风暴。

### 4. 使用交接单（跨设备任务接续）

**离开电脑前** — 说"生成交接单"或"同步任务"：

- AI 自动更新 `C:\WorkBuddy\_sync\HANDOFF.md`
- 包含活跃项目、任务进度、对话摘要、下一步行动
- 执行 `sync_identity.py push` 推到中转通道（**必须等推送完成再离开**）

**到另一台电脑后** — 说"拉取同步"或"继续上次"：

- AI 第一个动作：执行 `sync_identity.py pull`（铁律，不可跳过）
- 展示上一次的工作状态和上下文
- 无缝接续任务

> ⚠️ **重要**：v3.2 起，HANDOFF.md 等通过 `sync_identity.py` 中转通道同步，**不再依赖 Junction 直传**。中转目录为 `C:\WorkBuddy\_sync\identity\`。

## 注意事项 & 踩过的坑

坑 | 现象 | 原因 | 解决
---|------|------|------
**db 被同步覆盖** | 公司电脑对话消失，家里对话出现在公司 | `workbuddy.db` 在 WPS 云盘里被两台电脑共享 | 运行 `fix_db_isolation_v3.ps1`（v3 架构核心）
**新建工作区不显示** | 公司建的工作区，家里侧边栏没有 | `workspace-state.json` 是本地文件未同步 | 运行 `fix_workspace_state_sync.ps1`
**WAL 未刷盘** | 关闭后最新对话丢失 | WorkBuddy 没完全退出，WAL 文件残留 | 确认进程完全退出，WAL 文件消失
**workspace-state.json 为空** | 侧边栏只显示1个工作区 | WPS 同步了旧版本或客户端覆盖了 | 从 DB 重建 workspace-state.json
**会话被软删除** | DB 有记录但侧边栏看不到 | WorkBuddy 客户端同步时标记 deleted_at | `UPDATE sessions SET deleted_at = NULL`
**缺少 .workbuddy 标记** | 工作区目录存在但 sidebar 不显示 | 目录缺少 `.workbuddy/memory/` 子目录 | 手动创建标记目录
**路径分隔符** | 恢复的会话不在列表显示 | cwd 用了 `C:/...` 正斜杠 | 必须用 `C:\...` 反斜杠
**user_id** | 同上 | 数据库里填了 `"default"` | 必须用真实 UUID
**时间戳年份** | 显示「56年前」且内容不渲染 | `created_at=0` 或秒级而非毫秒级 | 确保毫秒级
**对话消失** | 路径修复后历史消息没了 | 项目缓存因路径变更分裂成两份 | `fix_paths.py` 第三步自动合并
**deliver_attachments 静默失败** | 发送的文件对方收不到 | `~/.workbuddy/` 是 symlink 路径 | 先 `cp` 到 `C:\WorkBuddy\` 再 delivery
**AI 不知道读交接单** | 换电脑后 AI 说"已经同步好了"但看不到上下文 | AI 没有被指示要先读 HANDOFF.md | 更新 SKILL.md 强制规则（v4 已修复）
**Junction 直传失效** | HANDOFF.md 跨设备不同步 | 2026-07 确认 WPS Junction 链路失效 | v3.2 改走 `sync_identity.py` 中转通道
**WPS 副本冲突风暴** | 几千个 `-副本` 文件 | 两台电脑同时写同一 WPS 路径 | `watch_sync.py` 单 leader 选举 + `find_junk.py`/`clean_junk.py` 清理 |

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

交接单（ `HANDOFF.md`）通过 `sync_identity.py` 中转通道（经 `C:\WorkBuddy\_sync\identity\`），是两台电脑的 AI 之间可靠的共享信息通道。v2 版本加入了机器生成区 + AI 手写区分离、对话摘要导出、同步暗号验证；v3.2 起改为中转通道同步，v5 加入自动同步守护进程。详见 `AI_HANDOFF_GUIDE.md`。

**Q: 出现大量 `-副本` 文件怎么办？**

用 `python find_junk.py` 扫描并生成报告，确认每个副本都有正本后，用 `python clean_junk.py --execute` 清理。当前 v5 单 leader 机制已阻止新副本产生，这是一次性清理。

## 安装为 WorkBuddy 技能

1. 克隆本仓库到本地：

```powershell
git clone https://github.com/<你的GitHub用户名>/workbuddy-skills.git
```

2. 把仓库根目录的全部文件复制进 WorkBuddy 用户技能目录：

```
# 目标目录（用户级技能）：
#   %USERPROFILE%\.workbuddy\skills\cross-device-sync\
# 即把本仓库根目录的 SKILL.md / *.py / *.bat / scripts/ 等整体放进去
```

3. 在 WorkBuddy 对话中直接说「跨设备同步」或「帮我在多台电脑间同步 WorkBuddy」即可自动触发此技能。

> 技能文件位于仓库根目录（不是 `cross-device-sync/` 子目录）。安装时把根目录内容对应放入 `~/.workbuddy/skills/cross-device-sync/` 即可。

## 许可

MIT License — 随意使用、修改、分发。
