---
name: cross-device-sync
slug: cross-device-sync
displayName: WorkBuddy 跨设备同步
version: "6.4.0"
summary: 让 WorkBuddy 在多台 Windows 电脑之间无缝同步（WPS 云盘 + 交接单 + 自动守护进程）
license: MIT
tags:
  - workbuddy
  - codebuddy
  - cross-device-sync
  - wps-cloud
  - windows
  - 跨设备同步
  - 跨电脑同步
  - 多电脑同步
  - 双电脑办公
  - 切换电脑
  - 会话接续
  - 任务交接
  - 工作区同步
  - WPS云盘
  - 金山文档
  - 符号链接
  - symlink
  - 软链接
  - Junction
  - Windows同步
  - SQLite隔离
  - 同步工具
  - 会话恢复
  - 5.4.7修复
  - IndexedDB丢消息
  - 对话历史丢失
  - 5.5.2对话丢失
  - 恢复对话记录
  - 升级后对话不见
  - JSONL恢复
description: |
  让 WorkBuddy 在多台 Windows 电脑之间无缝同步：通过 WPS 云盘（金山文档）做中转媒介，
  本地独立 SQLite 数据库防覆盖，配合 Windows Junction 统一工作区路径与守护进程
  （单 leader 选举 / 崩溃自愈 / 卡死自愈），并通过 HANDOFF.md 交接单实现跨设备
  任务接续。

  适用场景：跨设备同步、跨电脑同步 WorkBuddy、切换电脑后看不到旧会话、
  workbuddy 同步、workbuddy 数据库隔离、workbuddy 会话接续、
  workspace deleted or renamed 错误、双电脑办公、移动办公同步等。
  也适用于 WorkBuddy 5.4.7 IndexedDB 丢消息期间，借用磁盘化机制接续工作。

  每台电脑约需 15 分钟一次性配置（Junction + 数据库隔离 + 路径修复），
  之后全自动同步。
agent_created: true
homepage: https://github.com/jamesting-eng/workbuddy-skills
---

# WorkBuddy 跨设备同步

## 概览

通过 WPS 云盘让 WorkBuddy 跨设备同步。

**核心要点**：`workbuddy.db`（SQLite 数据库）**绝对不能直接同步** — 两台电脑同时写同一个
数据库文件，会互相覆盖对方的会话历史。本 skill 搭建的是一套**混合架构**，让各司其职：

- **`workbuddy.db`** 数据库在每台电脑**独立保留**（不参与同步，避免互相覆盖）
- **技能、脚本、记忆、配置** 通过 WPS 云盘同步（符号链接）
- **工作区目录**（`C:\WorkBuddy\`）通过 Windows Junction 同步
- **`workspace-state.json`** 通过文件符号链接同步（小文件、可安全共享）
- **跨设备任务接续** 通过 `HANDOFF.md` 交接单（不是 DB 同步）

这套架构同时也解决了根本痛点：每台电脑的 `C:\Users\<用户名>` 路径各不相同，
如果不处理，切换设备后会话引用全部失效。

## WorkBuddy 5.4.7 IndexedDB 对话丢失期应急持久化 SOP

> **适用场景**：用户反馈 WorkBuddy 重启后对话消息消失（会话侧边栏仍显示新会话，
> 但点进去看不到消息正文）。这就是 **WorkBuddy 5.4.7 IndexedDB 回归 bug** —— 由
> `5.4.7.37521366` 版本引入（install-manifest generatedAt `2026-08-31T22:48:01`）。
> Chromium IndexedDB 子系统在 `app/session` 下无法初始化，消息只存在于渲染进程内存中，
> 每次 WB 重启都会丢失。其他存储路径（`Local Storage`、`Session Storage`、
> `blob_storage`、`SharedStorage`）均正常 —— 只有 IndexedDB 坏了。TIDB /
> `@tencent/ovb-indexed-db` 存储后端会静默回退到内存存储。诊断方法与排除表：
> 见本章底部的「向 WorkBuddy 官方反馈 bug」章节，以及（如已附带）用户的完整
> bug 报告 markdown。

### 为什么本 skill 在 5.4.7 时期反而最关键

本 skill **天生基于磁盘** —— `HANDOFF.md`、`MEMORY.md`、`STATUS.md`、每日日志和
`sync_identity.py` 全部绕开 IndexedDB 直接写盘。5.4.7 的回归 bug **不会破坏**跨设备
同步架构 —— 恰恰相反，这个时期让本 skill 比平时**更关键**：

- 新开的 WB 会话对话上下文为空（聊天历史没了）
- 唯一幸存的上下文就是磁盘上的内容
- 本 skill 的整个工作流本身就是那套基于磁盘的交接机制

所以：**5.4.7 期间不要停用本 skill —— 反而要更用力地启用它。**

### 会话开始前必须按此次序读盘（5.4.7 时期）

除了第 6 步正常的"切换电脑"流程外，每个会话（新对话、重启的对话、甚至同一台电脑上的
续聊）都必须先按以下确切顺序完成这些读取：

1. **`Read` `C:\WorkBuddy\_sync\HANDOFF.md`** —— 跨机器交接单
2. **`Read` `<current workspace>/.workbuddy/memory/STATUS.md`** —— 工作区状态
3. **`Read` `<current workspace>/.workbuddy/memory/YYYY-MM-DD.md`**（今天 + 昨天）—— 近期每日日志
4. **`Read` `~/.workbuddy/MEMORY.md`**（如存在）—— 用户级长期记忆
5. **只有在这之后**才能回复用户

**5.4.7 时期禁止**：说出任何类似"我记得我们讨论过……"、"上次我们说好……"、"你之前
告诉我……"却**不是**来自上述四次读取的话。没读过它们，你就不知道 —— 请如实说明。

### 强制写盘纪律（5.4.7 时期）

在正常写盘规则基础上收紧（第 6 步本来就要求切换前必写；5.4.7 时期要求写得更勤）：

- **每约 8 次工具调用，或任何影响交付物的决策**：立即更新当前工作区的 `STATUS.md`，
  内容包括：项目目标 / 最新进展 / 当前待办 / 近期对话摘要 / 关键文件路径。
- **每次实质性工作会话结束时**（即使没切换电脑）：往当天的 `YYYY-MM-DD.md` 追加
  今天决定了什么、创建了什么、有什么阻塞。
- **对话中用户提到的任何偏好、硬性约束或硬编码取值** → 立即写入 `STATUS.md`。
  不要依赖 AI 的对话记忆。
- **任何理由让你认为 WB 对话可能会丢内容**（会话很长、复杂多步任务、用户提到要
  切换电脑之前）→ 先抢先把摘要写到磁盘，**再**回复。

### 给用户的临时缓解手段（5.4.7 时期）

在官方修复发布之前：

- 正常退出 WB（右键托盘图标 → 退出），让 SQLite WAL 完成 checkpoint。即使会话正文
  因 IndexedDB 丢失，`workbuddy.db` 里仍有更新过的行元数据（列表里能看到它们，
  只是正文没了）。
- 关闭 WB 之前，手动把任何关键对话文本复制到
  `<workspace>/.workbuddy/memory/YYYY-MM-DD.md` 或外部文件。
- 在 WB 设置里关闭自动更新（关于 → 自动更新）—— 既避免被升到未来有 bug 的版本，
  也为最终的 5.4.8 热修做准备（等热修经过验证后，建议手动安装）。
- 不要相信"聊天记录里记着呢" —— 一切以磁盘为准。

### 会话正文丢失后的恢复流程

打开一个"看似为空"的会话时（列表里有、正文空白）：

1. **`Read`** `workbuddy.db` 中该会话 id 对应的行 → 恢复 `cwd`、`created_at`、
   `last_activity_at`（5.4.7 下这些字段完好无损）。
2. **`Read`** `<cwd>/.workbuddy/memory/STATUS.md` → 近期上下文。
3. **`Read`** `<cwd>/.workbuddy/memory/<当天日期>.md` → 当天的工作日志。
4. 根据这些磁盘产物重建对话脉络。
5. 若恢复了关键内容 → 通过
   `scripts/restore_and_merge.py restore <session_id> <project_dir>`
   粘贴回该会话的 JSONL（见「进阶：会话恢复」），然后重启 WB。

**绝不编造聊天内容。** 如果磁盘产物不能告诉你当时说了什么，就如实说。基于磁盘的
持久化之所以有意义，就是因为真相在磁盘上。

### 向 WorkBuddy 官方反馈 bug

如果用户想把问题推给 WorkBuddy 官方：
- 收件人：`workbuddy_ai@tencent.com`（Bug 反馈渠道）
- 主题：`【Bug】WorkBuddy 5.4.7 升级后对话消息持久化失效（IndexedDB 子系统未初始化）`
- 附上 bug 报告 markdown 文件（关键章节与平台无关）
- 预期 7 个工作日；除非内容丢失同时阻塞了计费/法务/合同类工作，否则正文中不要
  按 P0 口径表述

---

## D 盘 AI 产物暂存区（释放系统盘）

C 盘是系统盘，AI 编程时产生的全量测试配置、临时缓存、构建产物、脚本日志
默认会写进去，很容易造成系统盘紧张。本 skill 的配套约定如下：

- **铁律**：禁止在 D 盘根目录直接新建文件夹；所有 AI 产物统一落在
  `D:\WorkBuddy\<用途名称>\` 下。
- **常用子目录示例**:
  - `D:\WorkBuddy\_cd\`：脚本与日志（含清理 log 脚本）
  - `D:\WorkBuddy\_py\`：pip `--target` 依赖
  - `D:\WorkBuddy\tmp\`：临时文件
  - `D:\WorkBuddy\<测试工作区>\`：常驻全量测试工作区（不在 C 盘跑测试）
  - `D:\WorkBuddy\<构建输出>\`：构建输出
  - `D:\WorkBuddy\npm-cache\` / `D:\WorkBuddy\npm-global\`：Node/npm 缓存
  - `D:\WorkBuddy\backups\` / `D:\WorkBuddy\deploy\`：备份与部署产物
- **交付物边界**：最终交付物和工作区数据仍然进入 `C:\WorkBuddy\<工作区>\`
  （通过 WPS Junction 同步到云盘）；`D:\WorkBuddy\` 下的测试/缓存/临时目录
  **不参与 WPS 同步**，避免污染云盘、浪费同步流量。
- **清理**：可定期运行清理脚本，删除 `D:\WorkBuddy\_cd\` 与
  `D:\WorkBuddy\tmp\` 中的过期日志和临时文件；执行前先用 dry-run 确认。
- **迁移遗留**：如果 D 盘根已有历史文件夹，整体迁入 `D:\WorkBuddy\` 下，并
  同步更新脚本和快捷方式。

## .workbuddy 数据布局：实体目录已迁 D 盘（Junction 模式）

`.workbuddy` 根目录下混着两类子目录——分清它们是任何磁盘瘦身工作的前提：

- **WPS 链接（22 个）**：skills/projects/binaries/plugins/blobs/memory/...
  等是指向 WPS 云盘的目录联接，其数据就是 WPS 同步副本——搬它们**不省 C 盘**
  （实体在 WPS 目录里）而且会断跨设备同步。**永远不要动这些。**
- **实体目录（4 个）**：workspace / logs / edgeone-cache / changes-detail 是
  本机数据。2026-09-29 已迁移到 `D:\WorkBuddy\.workbuddy\`，C 盘原位以目录
  联接（junction）指回——对 WorkBuddy 完全透明，C 盘释放约 3.4 GB。

迁移配方（可断点续跑，逐目录）：

1. 确认 WorkBuddy.exe 已完全退出。
2. 逐目录（从小到大）：`robocopy /E` 到 D: → 原目录改名 `<目录>.bak-preD`
   → `mklink /J` 指回 → 透读校验；任一步失败自动回滚该目录。
3. 重跑检测必须用 `dir /AL /B` + `findstr /X` 整行精确匹配——模糊匹配会误
   命中：`workspace` 会撞上 `workspace-state.json` 符号链接行而被错误跳过。
4. 每个 `<目录>.bak-preD` 保留 2-3 天正常使用期，确认无异常后删除落袋。
5. `workspace-state.json`（文件符号链接）按静态快照迁移——跨设备会话状态
   若失真，用 WPS 路径上的新文件覆盖即可。

参考实现：`D:\WorkBuddy\migrate-workbuddy-entities-to-d.cmd`（goto 流程、
无括号块、ORBIT_DRY 干跑开关、System32 find.exe 钉死——.bat 全套铁律见
windows-script-encoding 技能）。



## 前置条件

- WPS Office 已开通云盘功能，并同步到一个已知的本地文件夹
- 两台电脑都有管理员权限（创建 Junction 必需）
- 两台电脑都装 PowerShell 5.1+

## 为什么需要管理员权限（提交平台审核用）

本 skill **完全运行在用户本机** — 不发起任何网络请求、不收集遥测数据、不调用任何外部
服务。之所以需要 PowerShell 脚本、Python 守护进程和管理员权限，原因如下：

| 操作 | 为什么需要 |
|------|-----------|
| 管理员 / `New-Item -ItemType Junction` | 把 `C:\WorkBuddy` 创建为指向 WPS 云盘文件夹的 Junction，让两台电脑共享同一规范工作区路径（不同电脑 Windows 用户名不同） |
| `fix_db_isolation_v3.ps1` | 把 `workbuddy.db`（SQLite）从云同步目录**移到本机**，防止两台电脑互相覆盖会话数据库。仅读写本机 WorkBuddy 应用数据 |
| `fix_workspace_state_sync.ps1` | 把 `workspace-state.json`（几 KB）建立符号链接，让新创建的工作区自动出现在另一台电脑的侧边栏 |
| `scripts/fix_paths.py` | 路径统一后，批量改写历史会话里陈旧的 `C:\Users\<旧用户名>` 引用 |
| `watch_sync.py` 守护进程 | 本机文件监听（仅用标准库，按 mtime 轮询）。监听本机的记忆/交接单文件，变动时拷贝到中转目录。通过本机心跳文件做单 leader 选举，避免并发写入。**无任何网络 I/O** |
| `watchdog.bat` | 守护进程崩溃或卡死时自动拉起（检查本地 PID 文件与活性信号）。用户登录时通过 `shell:startup` 启动 |
| `secret-example.txt` | 用户自行填写的同步暗号模板，用来验证两台机器看到的是同一个共享目录。真实 `secret.txt` 故意不进 Git 也不进发布包（`package.py` 已强制剔除） |

本 skill 不读取任何凭据、不访问网络、不修改 WorkBuddy / WPS 目录之外的任何文件。
所有删除操作（`clean_junk.py`）仅针对 WPS 冲突副本文件（`-副本*`），且只在原始正常版存在的前提下清理。

## 操作流程

### 第 1 步：识别云盘路径

WPS 云盘默认同步路径通常是：

```
%USERPROFILE%\Documents\WPSDrive\<numeric_id>\WPS云盘\
```

请在 WPS 云盘的设置里（设置图标 › 云盘缓存位置）确认实际路径。`<numeric_id>` 随账号不同而变化，
常见的比如 `123456789`，但请以你机器上的为准。

在每台电脑上记下完整路径：
- 云盘根目录：`C:\Users\<username>\Documents\WPSDrive\<id>\WPS云盘\`
- 云盘上的 .workbuddy 位置：`<cloud_root>\.workbuddy\`
- 云盘上的工作区位置：`<cloud_root>\WorkBuddy\`

### 第 2 步：把 .workbuddy 迁移到混合架构（两台电脑都要做）

> ⚠️ 本步骤**取代**旧的"把 .workbuddy 符号链接到云盘"方案。
> 旧方案导致 `workbuddy.db` 被两台电脑共享并互相覆盖。
> 新方案把数据库保留在本机，只同步各子目录。

**在每台电脑上**运行 `fix_db_isolation_v3.ps1`：

1. **完全关闭 WorkBuddy**（右键托盘图标 → 退出）
2. 在项目工作区中找到该脚本（通过 `C:\WorkBuddy` Junction 同步过来）：
   ```
   C:\WorkBuddy\<project>\fix_db_isolation_v3.ps1
   ```
3. 右键 →"使用 PowerShell 运行"
4. 等待出现"修复完成"

脚本做了什么：
- 检测 `.workbuddy` 是否为符号链接 → 若是则移除，创建真实的本机目录
- 把所有子目录复制到 WPS 云盘（如尚未存在）
- 为每个子目录创建符号链接：本机 → WPS 云盘
- 把 `workbuddy.db` / `workbuddy.db-wal` / `workbuddy.db-shm` 保留在本机（不参与同步）
- 旧符号链接保留为 `.workbuddy.bak` 备份

最终架构：
```
C:\Users\<user>\.workbuddy\          ← LOCAL real directory
  ├── workbuddy.db                  ← LOCAL (never synced)
  ├── workbuddy.db-wal              ← LOCAL
  ├── workspace-state.json  → WPS   ← SYMLINK (synced)
  ├── skills/               → WPS   ← SYMLINK (synced)
  ├── scripts/              → WPS   ← SYMLINK (synced)
  ├── blobs/                → WPS   ← SYMLINK (synced)
  ├── memory/               → WPS   ← SYMLINK (synced)
  └── ...all other dirs...  → WPS   ← SYMLINK (synced)
```

### 第 2b 步：同步 workspace-state.json（两台电脑都要做）

运行 v3 脚本后，`workspace-state.json` 可能仍是本机文件。
要让工作区侧边栏列表跨设备同步，也把它变成符号链接：

在**每台电脑上**运行 `fix_workspace_state_sync.ps1`：
1. 在项目工作区中找到：`C:\WorkBuddy\<project>\fix_workspace_state_sync.ps1`
2. 右键 →"使用 PowerShell 运行"（无需关闭 WorkBuddy）
3. 等待出现"修复完成"

这一步会创建：
```
C:\Users\<user>\.workbuddy\workspace-state.json  →  WPS云盘\.workbuddy\workspace-state.json
```

这样之后，在一台电脑上新建工作区，另一台的侧边栏就会同步出现。

### 第 3 步：用 C:\WorkBuddy Junction 统一工作区路径

WorkBuddy 的会话文件以绝对路径引用工作区目录。不同电脑的用户名不同
（`C:\Users\Alice\...` 与 `C:\Users\Bob\...`）。为解决这个问题，
创建一个指向云盘同步工作区目录的 `C:\WorkBuddy` Junction。

**在每台电脑上**以管理员身份运行 PowerShell：

1. 把工作区目录移入云盘：
   ```powershell
   robocopy "$env:USERPROFILE\WorkBuddy" "$env:USERPROFILE\Documents\WPSDrive\<id>\WPS云盘\WorkBuddy" /E /COPYALL /MT:4 /R:1 /W:1
   ```

   > **重要**：务必用 `/E`（不要用 `/MIR`）。`/MIR` 会把云盘上其他电脑已有的文件删掉。

2. 创建 Junction：
   ```powershell
   New-Item -ItemType Junction -Path "C:\WorkBuddy" -Target "$env:USERPROFILE\Documents\WPSDrive\<id>\WPS云盘\WorkBuddy"
   ```

### 第 4 步：修复会话路径

运行随包自带的修复脚本，统一 JSON 文件与数据库中的所有会话路径：

```bash
python scripts/fix_paths.py
```

该脚本包含 4 个修复步骤：

1. **会话 JSON 文件** —— 把 `.workbuddy/sessions/*.json` 中的
   `C:\Users\<name>\WorkBuddy` 替换为 `C:\WorkBuddy`
2. **SQLite 数据库** —— 更新 `sessions` 表的 cwd 列为统一路径
3. **项目缓存合并** —— 把旧的 `c-Users-*-WorkBuddy-*` 缓存合并进
   `c-WorkBuddy-*`（防止迁移后"对话消息消失"）
4. **JSONL cwd 字段** —— 修复 `.workbuddy/projects/c-WorkBuddy-*/*.jsonl`
   文件内每条消息的 `cwd` 字段。这一步对**跨设备兼容性至关重要**：如果 JSONL
   消息里仍含用户特定路径，从另一台电脑打开时可能无法正常渲染。
   同时会把小写 `c:` 规范化为大写 `C:`。

脚本会报告修复了哪些文件并验证目录可访问性。

运行后，在两台电脑上重启 WorkBuddy。旧会话应能正常打开。

### 第 5 步：切换电脑前先关闭 WorkBuddy

**重要**：离开一台电脑去另一台之前，必须完全关闭 WorkBuddy。

虽然 `workbuddy.db` 现在是本机文件（不参与同步），但 WorkBuddy 使用 SQLite WAL 模式
（`workbuddy.db-wal`）。未提交的 WAL 数据在 WorkBuddy 退出前不会写入主 `.db` 文件。
如果强制结束进程或电脑死机，可能丢失最新的会话数据。

此外，WPS 云盘同步客户端可能锁定 WorkBuddy 正在写入的文件，
导致 skills/scripts/memory 目录出现同步冲突。

**正确关闭方法：**
1. 关闭所有 WorkBuddy 窗口
2. 等待 5 秒让 WAL 完成 checkpoint
3. 确认没有残留的 `WorkBuddy.exe` 进程：
   ```powershell
   tasklist | findstr WorkBuddy
   ```
   应无任何输出。
4. 确认 `workbuddy.db-wal` 文件已消失或非常小
5. 然后才可以离开这台电脑

### 第 6 步：跨设备任务接续（HANDOFF.md）— 必做

由于对话**不在**两台电脑之间同步（各自持有本机 `workbuddy.db`），
需要用交接单在设备之间传递任务上下文。

**HANDOFF.md 文件位于**：`C:\WorkBuddy\_sync\HANDOFF.md`

> 📌 **架构勘误（v6 修正，2026-08）**：v3.2 所说"Junction 实时同步失效"是
> **误诊**。`C:\WorkBuddy`（WPS Junction）**就是**主用的常开同步通道 ——
> 包括隐藏的 `.workbuddy` 目录在内的整棵树都会自动同步。7 月份实际发生的是：
> WPS 同步延迟 + AI 忘了写日志，被误判成了链路失效。当前架构是
> **三层各司其职**：
>
> 1. **主通道**：WPS Junction 对 `C:\WorkBuddy` 的自动同步（工作区文件 + 记忆）
> 2. **中转兜底**：`sync_identity.py` 经 `_sync\identity\` —— 精确控制、强制
>    推拉、冲突副本清理、防 WPS 偷懒
> 3. **守护进程**：`watch_sync.py` v2.2（单 leader）在文件变动约 1-2 秒后
>    自动触发中转推送；对崩溃**和**卡死都能自愈；由 `watchdog.bat` v2 保活
>
> HANDOFF.md 本身位于 WPS 共享路径上，同时经由中转通道镜像一份。

---

#### HANDOFF.md v2 结构（机器生成区 + AI 手写区）

文件由 HTML 注释分隔为两个区域：

```
# 跨设备交接单
...

<!-- ⚙️ 以下为机器生成区，workspace_sync.py 自动更新，AI 请勿手改 -->
## 📂 活跃工作区
## 🧪 同步链路检测
<!-- ✅ 以下为 AI 手写区，workspace_sync.py 不会覆盖，AI 自行维护 -->
## 📋 任务进度
## 💬 近期对话摘要
## 📎 导出对话
```

- **机器生成区**（`⚙️` → `✅`）：由 `workspace_sync.py` 自动更新，包含工作区列表和
  同步暗码检测记录。AI **不得**手改此区域。
- **AI 手写区**（`✅` → 文件末尾）：由 AI 维护。任务进度、近期对话摘要、导出的对话
  都更新在这里。

---

#### ⚠️ 关键规则 —— 对 AI 而言（两台电脑都必须遵守）：

**当用户切换电脑，并提到任何关于"同步"、"拉取"、"接续"、"继续"、"看交接单"的话时：**

1. **第一个动作（在回复任何任务状态之前）**：`Read` `C:\WorkBuddy\_sync\HANDOFF.md`
2. 若文件存在且有内容 → 读它，并告诉用户你发现了什么
3. 若文件缺失或为空 → 说"交接单为空，可能上一台电脑没有生成"，并询问下一步怎么做
4. **绝不**依赖自己的对话记忆去猜另一台电脑的 AI 做了什么
5. **绝不**在不先读 HANDOFF.md 的情况下说"已经同步好了" —— 没读之前你就是不知道

**为什么强制如此**：每台电脑的 AI 各有各的对话历史（`workbuddy.db` 相互独立）。
知道另一台电脑发生了什么的**唯一**途径就是 HANDOFF.md。
不读它，你对另一台电脑的工作就是盲的。

---

#### ⚠️ 强制要求：每次实质性工作会话结束后必须更新 HANDOFF.md

**这正是过去缺失的那条规则 —— 也是跨设备同步反复出问题的原因。**

完成**任何**实质性工作（生成文件、做出决策、修复 bug、撰写报告、
编写代码、设计素材等）后，AI **必须**更新 `C:\WorkBuddy\_sync\HANDOFF.md`：

1. 读取当前的 `C:\WorkBuddy\_sync\HANDOFF.md`
2. 更新 AI 手写区（`✅` → 文件末尾），写入：
   - 本次会话完成了什么（项目、创建的文件、关键决策）
   - 当前状态如何（例如"GDD v0.3 已完成，待评审"）
   - 下一步是什么（例如"待对方确认后推进众筹页面设计"）
3. 写回更新后的文件

**触发时机**（出现任何一条 = 必须更新 HANDOFF.md）：
- 用户说"生成交接单" / "写交接单" / "更新交接单" / "同步" / "记得写交接单"
- 会话即将结束且完成了实质性工作
- 用户即将切换电脑（明说或暗示）
- 任何多步任务（8 次以上工具调用）已完成
- AI 自检发现"本次会话做出了重要决策"

**不要等用户提醒。** 只要做了实际工作，就更新 HANDOFF.md。

**应写入的内容**（关键是：另一台电脑的 AI 无需追问就能看懂发生了什么）：
- 日期/时间与电脑名
- 处理了哪些项目
- 创建/修改的具体文件及其路径
- 关键决策及其理由
- 当前的阻塞点或待确认问题
- 明确的下一步

---

**离开一台电脑** —— 说"生成交接单"，创建/更新 `C:\WorkBuddy\_sync\HANDOFF.md`，
记录做了什么、接下来做什么、关键决策，以及用户想验证同步效果的任何测试消息。

生成 HANDOFF.md 时，**务必**包含：
- 当前日期/时间与电脑名
- 活跃项目及其状态
- 本次会话做出的关键决策
- 给另一台电脑的明确下一步
- 用户要求附带的所有测试消息

**抵达一台电脑** —— 作为 AI，你的**第一个**工具调用**必须**是对
`C:\WorkBuddy\_sync\HANDOFF.md` 的 `Read`。
然后告诉用户另一台电脑的 AI 留下了什么。

`sync-task` skill（随本 skill 一同安装）已把这套工作流自动化。
若 `sync-task` 已加载，读/写交接的循环由它负责。

### 第 6b 步：持续同步 — 三层架构（v6）

主同步通道就是 **WPS Junction 本身**（自动、常开）。中转通道提供精确控制与清理。
在此之上有两套机制：

1. **守护进程（推荐，免维护）** —— `watch_sync.py` v2.2 随开机启动（经 `shell:startup`
   中的 `watchdog.bat`）。它只监听**源文件**（用户级记忆、各工作区记忆、
   HANDOFF.md / secret.txt / AI_HANDOFF_GUIDE.md），变动后自动推送到中转目录
   （约 1-2 秒延迟）。**单 leader 选举**（按机器心跳文件）确保同一时刻只有**一台**
   活跃机器写中转目录 —— 这正是终结 `-副本` 冲突风暴的关键。它刻意**不**监听
   中转目录本身，从而杜绝 下载→推送→再下载 的循环。与机器无关（`sys.executable`），
   可安全地在两台电脑上同时运行。

   **崩溃自愈（v2.1）**：进程级 try/except（永不退出）、连续失败计数器 +
   基线重建 + 兜底拉取、受保护的心跳线程、PID 文件。
   **卡死自愈（v2.2）**：所有子进程调用都带 `-S`（绕开 sitecustomize 对 WPS 路径上
   unlink/rmtree 的劫持 —— 这是持续一周的静默卡死的根因）；主循环每次扫描都刷新
   `liveness_<machine>.txt`。`watchdog.bat` v2 在 PID 消失**或**活性信号超过 240 秒
   （卡死）时重启守护进程。务必使用配套的 v2 看门狗 —— 旧的只查 PID 的看门狗
   发现不了卡死进程。

2. **手动推拉（兜底）** —— 离开一台电脑前运行 `sync_identity.py push`，
   到达另一台后运行 `sync_identity.py pull`。`.bat` 包装：`push.bat`、`pull.bat`、
   `一键同步.bat`。

中转目录为 `C:\WorkBuddy\_sync\identity\`。`find_junk.py` / `clean_junk.py` 负责清理
漏网的 `-副本` 冲突文件。`sync_identity.py` v3.6+ **只中转 `YYYY-MM-DD.md` 每日日志** ——
项目身份文件（MEMORY.md/STATUS.md/...）保留在各工作区本地，以防跨工作区覆盖污染
（7/24 与 7/30 两次事故）。
v3.7 关停 write-back 扇出；v3.8 把 `memory/` 硬性收敛到 `.md` 并每轮清 IDE artifact-index。 v3.9 把每个工作区的每日日志按工作区隔离到 `LOCAL/memory/<工作区名>/` 子目录（补上 v3.6 在 MEMORY.md 层已闭合、但每日日志层遗漏的跨工作区碰撞缺口）。

> ⚠️ `_sync` 不在守护进程的监听清单里 —— 脚本升级（watch_sync.py / watchdog.bat）
> 必须**手动复制**到另一台机器。

#### 工作区级 STATUS.md（2026-06-25 —— 填补"旧工作区盲区"）

除了全局的 HANDOFF.md，每个工作区现在还有自己的状态文件：
`.workbuddy/memory/STATUS.md`

这解决了两个关键盲区：
1. **回到旧工作区**（例如 5/20 在 Project A 上工作，6/5 才回来）—— AI 读了 STATUS.md
   就能准确知道上次停在哪里
2. **同一工作区开新对话**（例如对话 A 做了图像处理，对话 B 继续 GDD）—— 新对话的
   AI 读了 STATUS.md 就能接着 A 的进度干

**进入工作区时**：AI 依次读 STATUS.md → MEMORY.md → 近期每日日志（规则见 sync-task skill）
**离开工作区时**：AI 把最新进展写入 STATUS.md（规则见 sync-task skill）

STATUS.md 格式保持轻量 —— 项目目标、最新进展、当前待办、近期对话摘要、关键文件路径。
完整的读写协议见 `sync-task` skill。

### 第 7 步：验证

在每台电脑上：
1. 打开 WorkBuddy
2. 确认侧边栏显示相同的工作区（经同步的 `workspace-state.json`）
3. 点开一个工作区 —— 应能正常打开（工作文件经 Junction 同步）
4. 说"同步任务"来测试交接单生成
5. 在另一台电脑上说"继续上次"来验证任务接续

**注意**：一台电脑上的对话**不会**出现在另一台上（这是设计使然）。
`workbuddy.db` 按电脑独立保留，就是为了防止覆盖冲突。

## 恢复 5.5.x 升级后"消失"的对话历史（路径重编码问题）

**症状**：升级 WorkBuddy 到 5.5.x 后，部分工作区里早于某个时间点的对话从界面上消失，
而升级后没打开过的工作区历史完好。注意：没有任何数据被删除——对话正文仍然在磁盘上。

**根因**：对话正文按会话以 JSONL 落盘在：

```
~/.workbuddy/projects/<工作区路径编码>/<会话UUID>.jsonl
```

目录名由工作区路径编码而来。5.5.x 开始会把 `C:\WorkBuddy` junction 解析成 WPS 云盘
真实路径，新消息因此写进了一个**编码不同的兄弟目录**，例如：

```
c-WorkBuddy-2026-01-15-10-30-00                                          <- 旧编码
c-Users-Bob-WorkBuddy-2026-02-20-09-15-00                              <- 旧编码
C-Users-Bob-Documents-WPSDrive-...-WorkBuddy-2026-01-15-10-30-00 <- 新编码（5.5.x 起）
```

界面只读新目录，于是重编码之前写入的对话全部"失联"。未触动的工作区仍以旧目录为准，
所以显示正常。这是**链接失效**而非数据丢失——不需要云端恢复、不需要 WPS 版本历史、
也不需要向官方提工单。

### 先确认你属于这种情况

挑一个"受影响"的工作区，在 `~/.workbuddy/projects/` 下找它对应的旧编码目录
`c-*-<工作区后缀>`，检查里面的 `<会话UUID>.jsonl` 是否覆盖"缺失"的日期范围。
如果是，按下面恢复；如果哪里都没有 JSONL，转用上方的应急持久化 SOP。

### 用 scripts/recover_session_jsonl.py 恢复

```bash
# 0. 先备份（必做）
python -c "import shutil; shutil.copytree(r'C:\Users\<你>\.workbuddy\projects', r'D:\projects_backup')"

# 1. 预演：看会合并/复制哪些文件
python scripts/recover_session_jsonl.py --dry-run

# 2. 执行：逐会话合并新旧 JSONL（按消息 id 去重、旧记录优先），
#    并把仅存在于旧目录的会话复制到新目录。全程不删除任何文件。
python scripts/recover_session_jsonl.py

# 3. 重启 WorkBuddy，验证历史是否回来。
```

脚本幂等（消息 id 去重保证可安全重跑），逐文件原子替换（临时文件 + `os.replace`）。
仍在写入中的会话会自动重试；若文件持续被占用，合并结果保留为 `*.merge_tmp`，
其余会话照常完成。

**与 5.4.7 IndexedDB bug 的关系**：那个 bug（见上方章节）破坏的是**新消息的持久化**；
本问题破坏的是**旧消息的可见性**。两样都经历过的电脑需要两个修复都做。5.5.2 已修复
IndexedDB 一侧，本脚本补上剩下的缺口。

## 进阶：会话恢复

当一个会话的完整消息缓存（`.jsonl`）丢失但云端摘要仍在时：

### 通过云端摘要恢复会话

1. 调用 `conversation_search` 取回丢失对话的云端摘要
2. 检查项目目录（例如 `C:\WorkBuddy\2026-03-10-09-20-45\`）中幸存的输出文档
3. 运行恢复脚本重建正规缓存：
   ```bash
   python scripts/restore_and_merge.py restore <session_id> <project_dir>
   ```

### JSONL 格式关键要求

恢复的消息**必须**严格遵循 WorkBuddy 格式。缺任何一个字段 = 消息不可见：

```json
{
  "id": "<uuid>",
  "type": "message",
  "role": "user|assistant",
  "sessionId": "<session_uuid>",
  "cwd": "C:\\WorkBuddy\\<project>",
  "content": [
    {"type": "input_text", "text": "..."}
  ],
  "providerData": {},
  "timestamp": <unix_ms>,
  "parentId": "<prev_message_id>"
}
```

关键坑点：
- `cwd` **必须**用反斜杠 `C:\...` —— 正斜杠会导致路径对不上
- `sessionId` 用驼峰命名（不是 `session_id`）
- `content` 是 `{type, text}` 对象的数组（不是纯字符串）
- `providerData` 必须存在：用户消息为 `{}`，助手消息为 `{"agent":"cli"}`
- `timestamp` 是自 epoch 起的毫秒数 —— 务必确认年份正确

### 数据库字段关键要求

把恢复的会话登记进数据库时：

- `user_id` **必须**匹配真实的用户 UUID（例如 `f205e23a-...`），**不是** `"default"`
- `cwd` **必须**使用反斜杠路径分隔符
- `created_at` 与 `last_activity_at` 的单位是**毫秒**（不是秒）

> 先查询任意一条现有会话，取回正确的 `user_id`。

## 进阶：会话合并

把多个相关会话合并为一个，整合零散的讨论：

### 通过脚本合并

```bash
python scripts/restore_and_merge.py merge <source_id> <target_id>
```

脚本会处理：
1. **按消息 ID 去重** —— 共享消息（如 file-history-snapshot）不会重复
2. **时间戳排序** —— 合并后所有消息按时间先后排列
3. **时间间隔填充** —— 合并的消息之间至少留 60 秒间隔，避免碰撞
4. **合并前备份** —— 缓存到 `_merge_backup_<timestamp>/`
5. **源会话软删除** —— 源会话在数据库中标记为已删除，从侧边栏消失

### 手工合并清单

如果手工操作，合并后需验证：
- 消息总数 = 目标行数 +（源行数 - 重复数）
- 时间顺序：旧内容在前，新内容在后
- 未重复的源消息 `sessionId` 正确（必须与目标一致！）
- 源会话已在数据库中软删除

## 在 WPS 云盘同步路径下安全删除文件（三板斧）

当工作区目录（`C:\WorkBuddy\...`）或技能 / 记忆子目录位于 WPS 云盘同步范围时，
默认删除方式都不安全 —— WPS 一旦发现原文件消失，可能立刻写入一个 `-副本`（冲突副本）
兄弟文件，而朴素的 `rm -rf` 会因为 WPS 文件锁而卡死。需要批量删除 WPS 同步路径下的文件时，
请使用这三板斧。

### 第一板：用 `python -S` 跳过 sitecustomize

很多用户环境注册了 `sitecustomize.py`，会把 `os.unlink`、`shutil.rmtree` 等函数
monkey-patch 成"安全删除" / 回收站流程。在 WPS 同步路径上，这个流程会死锁
（WPS 持有文件不释放，而回收站 hook 一直在等锁）。`-S` 让 Python 不导入
`sitecustomize`，恢复标准库行为：

```bash
python -S your_delete_script.py
```

或单行调用：
```bash
python -S -c "import os; os.remove(r'C:\\WorkBuddy\\_sync\\identity\\<file>.md')"
```

### 第二板：只用 `os.remove` —— 不用 `ctypes.DeleteFileW` / `Path.unlink` / `shutil.rmtree`

- 可以：`os.remove(path)` —— 单文件，标准库，在 WPS 路径上最干净。
- 不行：`ctypes.windll.kernel32.DeleteFileW(path)` —— 绕过 Python 高层错误处理；在 WPS
  下文件经常以 `-副本` 冲突副本形式重新出现，因为 WPS 看到裸系统调用后试图"恢复"——
  从另一台机器重新上传。
- 不行：`pathlib.Path(path).unlink()` —— 在 sitecustomize 下与 `os.unlink` 遭遇同样的
  hook；即使加了 `-S`，有时仍走 `_NormalizePath`，WPS 不能完全识别。
- 不行：`shutil.rmtree(path)` —— 递归遍历；在 WPS 下任何正在上传的子目录都会触发
  "目录被占用"死锁。即使加了 `-S`，也建议改成"逐文件删除 → 目录空了再 `os.rmdir`"。

### 第三板：每进程 <= 40 个文件批次；循环"扫描 → 删除 → 再扫描"直到归零

WPS 每个目录同一时间最多约 40 个文件用于同步上传。一个进程想删 4000 个文件就会
撞锁卡住。用多进程，每个 worker 处理 <= 40 个文件后退出：

```python
import os, multiprocessing as mp

def delete_batch(paths):
    deleted = []
    for p in paths:
        try:
            os.remove(p)  # 单文件，标准库；解释器必须以 -S 启动
            deleted.append(p)
        except OSError:
            pass  # WPS 可能正持有，下次循环再试
    return deleted

def chunked(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

if __name__ == "__main__":
    target_dir = r"C:\\WorkBuddy\\_sync\\identity"
    while True:
        files = [os.path.join(target_dir, f) for f in os.listdir(target_dir)
                 if f.endswith(".md") and not f.startswith(".")]
        if not files:
            break
        # 并行删除，每个 worker 40 个文件
        with mp.Pool(processes=8) as pool:
            for batch in chunked(files, 40):
                pool.apply_async(delete_batch, (batch,))
            pool.close(); pool.join()
        # 本轮没删掉的（WPS 锁住的）下一轮再试
```

"循环到零"的模式意味着任何 WPS 正在同步的文件在下一轮会被重试 —— 最终所有
可达文件都会被清掉。

### 什么时候不该用这个方法

- **`~/.workbuddy/workbuddy.db*` 下的文件（本地，不同步）** —— 用普通的
  `os.remove` / `Path.unlink`；不涉及 WPS。
- **用户的 Desktop / Downloads / Documents 根目录** —— 永远不要在这里批量删除；
  用操作系统回收站。本方法只用于 *工作区树* 清理。
- **删单个文件** —— 直接 `os.remove` 即可，不需要多进程。

---
## 为什么项目状态和产物列表偶尔会冲突（以及怎么防）

因为本 skill **魔改了 WorkBuddy 的默认配置**（每台机器 `workbuddy.db` 隔离、
`workspace-state.json` 符号链接、`_sync/` 中转目录、HANDOFF.md 交接单），跨机器同步
引入了原生 WorkBuddy 从未设计共享的状态。最常见的冲突类型和修法：

### 症状 1：`workspace-state.json` 在两台机器上显示不同工作区

**成因**：该文件通过 `fix_workspace_state_sync.ps1` 符号链接进 WPS，但 WPS 可能在
新工作区的首批 JSONL 写入完成前就上传了变更 —— 另一台机器看到侧栏条目但点击
打开是空会话。

**修法**：创建新工作区后，在 *另一台* 机器上：
1. 等待约 5 秒让 WPS 完全同步新文件
2. 在 WPS 资源管理器里右键该工作区文件夹 → "始终保留在此设备上"
3. 重启 WorkBuddy 让侧栏重新读取 `workspace-state.json`

### 症状 2：某个工作区的 `MEMORY.md` 被另一个工作区的内容覆盖

**成因**：旧版 `sync_identity.py` 的"扁平用户级命名空间"收集机制会把每个工作区的
`MEMORY.md` 汇总到每台机器的单个 `~/.workbuddy/memory/` 目录；推送时"最新 mtime 胜出"
合并随后会用最近被编辑的那一份覆盖 *所有* 工作区的本地 `MEMORY.md`。真实事故两次：
**2026-07-24**（14 个工作区被同一份内容污染）和 **2026-07-30**（同样形态，影响面更小）。

**修法（已在 `sync_identity.py` v3.6 落地）**：
- 只有 `YYYY-MM-DD.md` 每日日志进入用户级扁平命名空间。
- 项目身份文件（`MEMORY.md`、`STATUS.md`、`DAILY_STATUS.md`、`HOME_WRAPUP.md`、
  `MORNING_BRIEF.md`）**留在工作区本地** —— 不汇总、不分发。
- v3.6 之前被污染的文件必须从该工作区自己的每日日志恢复（找 `### MEMORY.md
  overwrite on YYYY-MM-DD` 这样的标题）。

### 症状 3：一台机器上 STATUS.md / DAILY_STATUS.md 缺失或过期

**成因**：项目身份文件是工作区本地的（症状 2 的修法）；WPS 通过 Junction 同步它们，
但如果某台机器编辑时另一台离线，新版本就永远收不到。

**修法**：到达一台机器时，AI 的强制读取顺序（Step 6）能捕获这个：
1. 读 `C:\WorkBuddy\_sync\HANDOFF.md` —— 含最新状态摘要
2. 读 `<workspace>/.workbuddy/memory/STATUS.md` —— 可能过期；过期则从
   HANDOFF.md + 最近每日日志重建
3. 读 `<workspace>/.workbuddy/memory/YYYY-MM-DD.md`（今天 + 昨天）

**预防**：每次实质性工作会话都要同时写 STATUS.md（工作区本地）**和** 更新
HANDOFF.md（跨机器）。HANDOFF.md 是跨机器权威状态；STATUS.md 是工作区本地缓存。

### 症状 4：两台机器的守护进程抢中转目录

**成因**：如果两台 `watch_sync.py` 实例的主循环同一时刻都看到"中转目录空，该我推了"，
就会创建 `-副本` 冲突副本。

**修法（已在 `watch_sync.py` v2.0+ 落地）**：
- **单 leader 选举**通过每台机器的心跳文件：任何时刻只有一台机器写中转目录。
- 用 `find_junk.py` 报告观察选举情况 —— 如果看到新的 `-副本` 文件，说明 leader
  选举坏了；两台机器都重启 `watchdog.bat`。

### 症状 5：Automation `cwds` 漂移（其他章节已记录）

这不是跨设备同步独有的，但跨设备同步会加剧 —— 完整 runbook 见上文
"Automation Path Drift" 章节。

### 诊断一行命令

```bash
# 显示当前两层同步状态
python sync_cli.py status
# 输出：leader 机器、中转目录 mtime vs 源 mtime、最近 push/pull、
#      最近的 -副本 文件、守护进程活性、watchdog 活性
```

如果 `sync_cli.py status` 报告的不是"单 leader、无冲突副本、守护存活"，
就先解决那个具体子系统，再假设是数据丢失。

---

## IDE 产物索引僵尸复活（WPS 路径 vs 本地缓存冲突）

尽管 `sync_identity.py` 早已防住 `MEMORY.md` 跨工作区互覆污染（v3.6）和守护进程 leader 选举争抢（v2.0+），在 2026-09-06/07 的 C 盘微信清理期间仍冒出**第三类、更底层的僵尸复活**：本地删掉一个文件，IDE 产物面板里**没消失**，更糟的是——重启后文件还**回来**了。两个独立根因，共同源头都是"WPS 路径是符号链接、而本地缓存/索引不是"。

### 症状 A：`.workbuddy/memory/` 被非 `.md` 垃圾污染，WPS 又反向拉回（清理 → 反向拉回死循环）

**成因**：C 盘清理期间，约 47 个一次性脚本/报告（`.py`/`.txt`/`.log`）被写进了 `<workspace>/.workbuddy/memory/`——这个目录符号链接进 WPS 云盘。`watch_sync` 把它们推上 WPS；下一次同步时 WPS 副本又被拉回。每一次"本地删除"都被反向拉回抵消 → 无限僵尸循环，垃圾还顺着共享云盘污染了**每台**机器。

**修法（已在 `sync_identity.py` v3.8 落地）**：
- 新增 `cleanup_memory_non_md(dir)`，在**每次同步前**对本地和中转 `memory/` 目录双向清理非 `.md` 文件。
- `.workbuddy/memory/` 现在被画死边界：只允许 `YYYY-MM-DD.md` 每日日志和项目身份 `.md` 文件（`MEMORY.md`、`STATUS.md`、`DAILY_STATUS.md`、`HOME_WRAPUP.md`、`MORNING_BRIEF.md`）。任何临时脚本/报告在边界就被拒，WPS 无从反向拉回。

### 症状 B：IDE 产物面板显示指向已删文件的死条目（重启也不消失）

**成因**：WorkBuddy 为每个会话保存一份 **artifact-index**（`~/.workbuddy/artifact-index/*.json`，每会话一个 JSON），记录每次 Read/Write/present_files 的绝对 `file:///` URI。这些 JSON 自己也符号链接进 WPS 云盘。磁盘上文件删了，索引里的 URI 还在，于是 IDE 产物面板持续渲染僵尸条目——而且索引本身走云同步，连完整重启 IDE 都清不掉。

**修法（已在 `sync_identity.py` v3.8 落地）**：
- 新增配套脚本 `cleanup_artifact_index.py`：把每个 artifact URI 解析成真实路径，删掉文件已不存在的条目（通过 `.tmp` + `os.replace` 原子重写）。
- `sync_identity.py` 的 `main()` 现在**每次同步**都会调 `cleanup_artifact_index.py`，默认 *活跃优先* 模式（仅最近 24h 内更新过的会话），历史会话原样保留；加 `--all-sessions` 可全清。
- 这样清理在每次同步 / 守护周期自动跑，僵尸 URI 没有任何复活的窗口。

### 手动跑清理器

```bash
# 仅清活跃会话里的失效 URI：
python cleanup_artifact_index.py
# 清所有会话（大清理后用）：
python cleanup_artifact_index.py --all-sessions --dry-run   # 先预览
python cleanup_artifact_index.py --all-sessions            # 再执行
```

### 为什么这是"软件层"根治（而非一次性清理）

卖家运营助手工作区此前也撞过同样的产物面板僵尸，只做了一次性的 `.bak-20260905` 清理——**没有持久防御**，于是本轮在本工作区复发。v3.8 的修法直接集成进同步引擎本身，今后每一次同步都会自动重申边界。配合 v3.6 的 `MEMORY.md` 边界，memory/artifact 两层在双侧都闭合成防御：WPS 符号链接侧（无垃圾可同步）+ 本地索引侧（每轮清掉死 URI）。

### 后续补充（2026-09-21）：增加「产物索引自愈清理」自动化任务

**新发现**：artifact-index 目录本身也是 WPS 云盘的 junction。也就是说，即便你本地把文件删了、也把本地 JSON 里的死条目清了，云端那份旧的 JSON 还是会被推回来。更关键的是，`cleanup_artifact_index.py` 原本只在 `sync_identity.py` 跑同步时才被调用——如果你平时不经常手动跑完整同步，这个清理等于一直没跑。

所以要在 WorkBuddy 里加一个自动化任务，名字可以叫**「产物索引自愈清理」**：

- **频率**：每 24 小时一次（比每 8 小时更省算力积分；artifact-index 只在 `present_files` 时追加，每天清一次足够）。
- **工作区（`cwds`）**：务必绑定到**当前工作区**（`C:\WorkBuddy\CURRENT-WS`）。不要绑到 `~/.workbuddy` 或全局路径，否则会造成项目记忆污染，让自动化任务跑到其他工作区里「作祟」。
- **命令**（用管理版 Python 的绝对路径；建议把 `cleanup_artifact_index.py` 复制到 `C:\WorkBuddy\_sync\`，让它落在 WPS 自动同步范围之外、但又有一个固定路径）：
  ```bash
  C:\Users\<你的用户名>\.workbuddy\binaries\python\versions\<Python 版本>\python.exe -S "C:\WorkBuddy\_sync\cleanup_artifact_index.py" --all-sessions --quiet
  ```
- **输出控制**：只输出一行，例如 `产物索引自愈：清理 N 条失效引用`。不要从这个自动化任务里展开长报告。
- **为什么用 `--all-sessions`**：因为死条目可能在很久没更新的旧会话 JSON 里，只清活跃会话会漏掉。
- **为什么用 `-S`**：防止 `sitecustomize` 拦截删除并改道到回收站。

> **注意**：`C:\WorkBuddy\_sync\` 是脚本专用的非 WPS 自动同步目录，所以每台机器上都要手动复制一份 `cleanup_artifact_index.py` 过去（不要指望 WPS 自动同步它）。

---
## 已知限制

### 归档会话

WorkBuddy 目前**没有针对已归档会话的界面筛选器**。侧边栏筛选只显示：
进行中 | 已完成 | 失败 | 待处理 | 规划中 | 全部状态

会话一旦归档（数据库中 status=archived），界面上就不可见了。
恢复方法：在数据库中手动把 `status` 改回 `"working"` 或 `"completed"`：

```sql
UPDATE sessions SET status = 'completed' WHERE id = '<session_id>';
```

### 时间戳"年份 bug"

时间戳不正确（年份错误）的恢复消息会：
- 在界面上显示为不合常理的日期（例如"56年前"）
- 可能被 WorkBuddy 的渲染逻辑完全过滤掉

恢复时务必验证时间戳落在预期的日期范围内。
如果用错了年份，典型修复是加上 31536000000ms（365 天的毫秒数）的偏移。

### 附件投递与符号链接路径

搭建跨设备同步之后，`deliver_attachments` 对 `~/.workbuddy/` 下的文件可能静默失败，
因为该目录现在是指向 WPS 云盘的符号链接。WorkBuddy 的附件投递对符号链接路径的
解析方式与原生路径不同。

**解决办法**：调用 `deliver_attachments` 之前，先把文件复制到当前工作区
（`C:\WorkBuddy\<project>\`）。`C:\WorkBuddy\` 下的文件（是 Junction，不是
符号链接）能被正确解析。

```python
# Before delivering, copy to workspace:
import shutil
workspace = 'C:/WorkBuddy/<project>/'
shutil.copy(file_path, workspace + 'filename.md')
# Then deliver from workspace path
```

### 自动化任务路径漂移

自动化任务（如"下班自动存档"这类定时任务）存储了硬编码的 `cwds` 字段，
其 `prompt` 文本里也可能引用工作区路径。路径迁移之后，或当前活跃工作区变化时
（新对话 = 新的按时间戳命名的目录），自动化任务会悄悄指向**旧工作区** —— 它们
照常运行，但写到错误的目录，或者因为旧工作区已不存在而失败。

**症状**：
- 自动化任务运行了，但输出文件出现在旧工作区
- 自动化任务显示的是几周前的日期（"5月30号"）
- 当前工作区里的 `DAILY_STATUS.md` 一直不更新

**根因**：自动化任务**绑定在创建它的那个会话上**。只更新 `cwds` 和 `prompt`
是不够的 —— 自动化执行器仍在原会话的上下文中运行，仍写入原工作区。

**唯一可靠的修复：删除后重建**：

```
# 1. Delete old automations
automation_update(mode="delete", id="automation-OLDID")

# 2. Recreate in current session
automation_update(mode="create", name="...", cwds="C:\\WorkBuddy\\CURRENT-WS", ...)
```

**prompt 路径最佳实践**：使用 `.workbuddy/memory/` 这类相对路径，
而不是 `C:\\WorkBuddy\\2026-06-03\\...` 这类绝对路径。这样在新会话里重建时，
prompt 文本就不需要改写。

**预防措施**：开启新的"主力"对话后，把所有自动化任务在该会话中删除并重建。
**不要**指望用 `automation_update(mode="update")` 改变工作区绑定 —— 那没用。

## 故障排查

### 跨电脑时对话被互盶覆盖

**症状**：同步后公司机的对话消失，家里机的对话反而出现在公司机上。

**原因**：`workbuddy.db` 被当成云同步文件了。两台电脑同时写同一个 SQLite 数据库文件，会互盶覆盖。

**修复**：两台电脑都跑一次 `fix_db_isolation_v3.ps1`。该脚本会把 `.workbuddy` 从云同步的符号链接转换为本机真实目录，使 `workbuddy.db` 保留在本机，仅同步子目录。

### 新建工作区没出现在另一台电脑

**症状**：在一台电脑上创建了新工作区，另一台的侧边栏却看不到。

**原因**：`workspace-state.json` 默认是本机文件（不参与云同步）。

**修复**：两台电脑都跑一次 `fix_workspace_state_sync.ps1`。该脚本会创建一个文件符号链接，让 `workspace-state.json` 存入 WPS 云盘并自动同步。

### 诊断脚本

用 `home_check.py`（主机电脑上用 `final_check.py`）做一次全系统体检：

```bash
python home_check.py
```

检查项：符号链接目标、Junction 目标、workspace-state.json、数据库完整性、
活跃/已删除会话、时间戳、路径格式、WAL 文件，以及 .jsonl 一致性。

### 配置后验证清单

初次配置后，或感觉哪里不对劲时，运行以下检查：

```
# 1. .workbuddy is a local real directory (NOT a symlink to cloud)?
ls -la ~/.workbuddy   # should be drwxr-xr-x, NOT lrwxrwxrwx -> WPS

# 2. workbuddy.db is local?
python -c "import os; p=os.path.expanduser('~/.workbuddy/workbuddy.db'); print('OK' if os.path.exists(p) and not os.path.islink(p) else 'PROBLEM')"

# 3. Subdirectories are symlinked to WPS cloud?
ls -la ~/.workbuddy/skills   # should show -> ...WPS云盘/.workbuddy/skills

# 4. workspace-state.json is a symlink?
python -c "import os; p=os.path.expanduser('~/.workbuddy/workspace-state.json'); print('SYNCED' if os.path.islink(p) else 'LOCAL ONLY')"

# 5. Junction intact?
cmd /c "dir C:\ /AL" | findstr WorkBuddy   # should show <JUNCTION>

# 6. DB paths unified?
sqlite3 ~/.workbuddy/workbuddy.db "SELECT COUNT(*) FROM sessions WHERE cwd LIKE '%Users%';"
# Should return 0

# 7. Each workspace has .workbuddy/memory/ marker?
ls -d C:/WorkBuddy/*/.workbuddy/memory/   # should list all workspaces
```

### "Workspace renamed or deleted" 错误持续存在

1. 确认 Junction 存在：`cmd /c "dir C:\ /AL" | findstr WorkBuddy` 应显示 `<JUNCTION>`
2. 确认云盘已完全同步 —— WPS 可能把尚未下载的文件显示为占位符。右键 WPS 中的
   WorkBuddy 文件夹，选择"始终保留在此设备上"
3. 确认各项目目录都有 `.workbuddy` 子目录 —— 每个工作区都需要 `.workbuddy/memory/`
4. 重跑 `scripts/fix_paths.py` 并检查输出中有无 MISSING 条目

### Workspaces 侧边栏显示的数量比预期少

WorkBuddy 从 `workspace-state.json` 读取工作区列表，而不是直接读数据库。如果该文件
为空或过期：

**症状**：数据库里有 8 个会话，侧边栏却只显示 1 个工作区。

**修复**：从数据库重建 `workspace-state.json`：

```python
import sqlite3, json, os

db = os.path.expanduser('~/.workbuddy/workbuddy.db')
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute('SELECT DISTINCT cwd FROM sessions WHERE deleted_at IS NULL')
workspaces = [{'path': r[0], 'lastOpenedAt': 0} for r in cur.fetchall()]
conn.close()

state = {'version': 1, 'workspaces': workspaces}
with open(os.path.expanduser('~/.workbuddy/workspace-state.json'), 'w', encoding='utf-8') as f:
    json.dump(state, f, indent=2, ensure_ascii=False)
```

重建完成后重启 WorkBuddy。

### 会话存在于数据库但侧边栏看不到（软删除）

**症状**：`SELECT COUNT(*) FROM sessions` 返回 10，侧边栏却显示更少。

**检查**：部分会话可能 `deleted_at IS NOT NULL`（WorkBuddy 客户端在同步期间做的软删除）。

**修复**：
```sql
UPDATE sessions SET deleted_at = NULL WHERE deleted_at IS NOT NULL;
```

然后重建 `workspace-state.json`（见上文）并重启 WorkBuddy。

### 工作区目录缺失 .workbuddy 标记

**症状**：`C:\WorkBuddy\` 下存在工作区目录，但不出现在侧边栏，尽管数据库和
`workspace-state.json` 都正常。

**原因**：WorkBuddy 要求每个工作区目录内存在 `.workbuddy\` 子目录（哪怕为空），
才能将其识别为有效工作区。

**修复**：
```powershell
New-Item -ItemType Directory -Path "C:\WorkBuddy\<project>\.workbuddy\memory" -Force
```

### 路径斜杠不一致（C:/ 与 C:\）

**症状**：在一台电脑上恢复的会话在另一台上看不到，或消息渲染不正确。

**原因**：`cwd` 字段里的正斜杠（`C:/WorkBuddy/...`）在 Windows 上导致路径对不上。

**修复**：所有 `cwd` 字段（数据库和 JSONL 中）**必须**用反斜杠：
```python
# Fix all forward slashes in DB
cur.execute("UPDATE sessions SET cwd = REPLACE(cwd, '/', '\\\\') WHERE cwd LIKE 'C:/%'")
```

`fix_paths.py` 脚本已包含这一规范化步骤。

### 路径修复后对话消息消失

当 `projects/` 目录下同一工作区**同时**存在 `c-Users-*-WorkBuddy-*` 与
`c-WorkBuddy-*` 两个缓存时会发生此问题。WorkBuddy 只加载与当前 cwd 匹配的缓存，
旧消息就"失联"在旧缓存里了。

重跑 `scripts/fix_paths.py` —— 脚本现在包含第 3 步（合并项目缓存），会把所有旧
缓存合并进新缓存，并重命名孤立缓存。

### 创建符号链接失败

如果 `New-Item -ItemType SymbolicLink` 因权限错误失败：
- 确认 PowerShell 正以管理员身份运行
- 在 Windows 家庭版上，创建符号链接可能需要先开启开发者模式

### 恢复的会话没出现在侧边栏

把这三件事逐个检查到位（都必须正确）：
1. **数据库中的 `user_id`** —— 必须匹配真实用户 UUID，**不是** `"default"`。
   查询任意现有会话即可找到。
2. **`cwd` 路径分隔符** —— 必须用反斜杠（`C:\WorkBuddy\...`），**不是**正斜杠。
3. **JSONL 格式** —— 验证 `type`、`sessionId`（驼峰命名）、`content` 为
   `{type, text}` 数组、`providerData` 均已存在。

### 恢复内容显示不可能的日期（56年前）

**原因 1（最常见）**：`created_at` 或 `timestamp` 被设成了 `0`（即 1970-01-01）。

**原因 2**：把秒当成了毫秒用（数值小了 1000 倍，显示出 1970 年的日期）。

**修复**：
```sql
-- Fix created_at = 0 (set from first JSONL message timestamp)
UPDATE sessions SET created_at = <correct_ms>, updated_at = <correct_ms>, last_activity_at = <correct_ms> WHERE created_at = 0;
```

对年份错误的 JSONL 消息，按年份偏移量调整：
- 365 天 = 31536000000 ms
- 366 天 = 31622400000 ms（闰年）

恢复完成后务必验证时间戳落在预期的日期范围内。

### 云盘路径不一致

如果 WPS 云盘路径与默认不同，检查 WPS 设置：
WPS 应用 > 设置 > 云文档 > 缓存位置

路径格式固定为 `%USERPROFILE%\Documents\WPSDrive\<id>\WPS云盘\` —— 只有 `<id>` 会变。

## 资源

### sync_identity.py（v3.9 中转同步）

双向**中转通道**同步。收集各工作区的 `.workbuddy/memory/` 到
`C:\WorkBuddy\_sync\identity\`，拉取时再把中转记忆分发回各工作区。
同时同步 HANDOFF.md / 身份文件。v3.4+ 自动清理 WPS `-副本` 冲突文件，并跳过任何
文件名含"副本"的文件以防同步风暴；v3.5 在推送前清扫垃圾文件。
**v3.6（关键）**：扁平的用户级命名空间里只允许进入 `YYYY-MM-DD.md` 每日日志；
项目身份文件（MEMORY.md / STATUS.md / DAILY_STATUS.md / HOME_WRAPUP.md /
MORNING_BRIEF.md）一律跳过 —— 此前它们跨工作区撞名，"最新 mtime 优先"的合并把
一个工作区的内容扇出到**所有**工作区（两次事故：7/24、7/30，14 个工作区被污染）。
**v3.7（关停 write-back 扇出，2026-08-27）** —— 永久禁用 `distribute_user_memory_to_workspaces()`，封死第二阶段扇出路径（即便 v3.6 边界已关闭合并步骤，仍可能把用户级 memory/ 推回每个工作区）；同类污染不再可能发生。
**v3.8（artifact-index + memory 边界加固，2026-09-07）** —— 经 `cleanup_memory_non_md()` 把 `.workbuddy/memory/` 硬性收敛到仅 `.md`（干掉「本地清干净 → WPS 副本反向拉回」的僵尸循环，该问题在 2026-09-06 C 盘清理时暴露），并集成兄弟脚本 `cleanup_artifact_index.py`，每轮同步清理 IDE 各会话失效 artifact-index URI（默认活跃会话，`--all-sessions` 清理全部）。详见下文「IDE Artifact-Index 僵尸复活」。
**v3.9（每日日志碰撞修复，2026-09-07）** —— `collect_workspace_memories_to_user()` 现在把每个工作区的每日日志按工作区隔离到 `LOCAL/memory/<工作区名>/YYYY-MM-DD.md`（每个工作区一个子目录），而非原来的扁平 `LOCAL/memory/YYYY-MM-DD.md`。扁平布局在两个工作区同日有日志时会碰撞（「mtime 较新者胜出」覆盖另一份，污染文件经 WPS 云盘扩散—— 8/26 MyProject 桌游工作区日志覆盖法务工作区日志的事故即源于此）。按工作区隔离后，日期碰撞不可能发生。遗留的扁平每日日志一律**移动**（永不删除）到 `LOCAL/_v39_legacy_flat_quarantine/`。

### watch_sync.py（v2.2 自动守护）

带单 leader 选举的后台守护进程。监听源文件，变动后自动推送（约 1-2 秒延迟）。
与机器无关（`sys.executable`），可安全地在两台电脑上同时运行。
v2.1 崩溃自愈：永不退出的主循环、失败计数器恢复、PID 文件。
v2.2 卡死自愈：所有子进程调用带 `-S`（击败 sitecustomize 对 WPS 路径上
unlink/rmtree 的劫持），外加每次扫描都刷新的 `liveness_<machine>.txt` 心跳。

### watchdog.bat（v2 看门狗，已由 sync_cli.py 调用）

看门狗循环（30 秒一轮）。当守护进程 PID 消失（崩溃/被杀/重启）
**或**活性信号超过 240 秒（PID 还活着但主循环卡死）时重启守护进程。重启命令
带 `-S`。把它（或其快捷方式）放入 `shell:startup`。必须与 watch_sync.py
v2.2 配套使用 —— 旧的只查 PID 的看门狗发现不了卡死的守护进程。

### find_junk.py / clean_junk.py（空间回收工具）

WPS 冲突副本扫描器（生成 HTML 报告）与清理器（只删除存在完好原件的副本）。
在同步风暴之后、或 `-副本` 文件成千上万地出现时使用。

### workspace_sync.py（v3.0 工作区状态同步）

机械化同步：扫描 `C:\WorkBuddy` 工作区，重新生成 HANDOFF.md 的机器生成区
（不触碰 AI 手写区），并协助对话导出 + 同步暗码。

### sync_cli.py（v6.1+ 统一入口，SkillHub 包内唯一启动器）

取代四个 `.bat` 包装（`push.bat`、`pull.bat`、`start_sync.bat`、一键同步）的
统一启动器。双击进入交互菜单，或调用
`sync_cli.py pull` / `push` / `sync` / `verify` / `status` / `start` / `stop` /
`startup-install`。`start` 启动的是**看门狗**（由它再去监护守护进程）而非守护进程
本身，因此崩溃仍能自愈。分发渠道拒绝 `.bat` 文件，所以这是发布包里唯一的启动器。

### scripts/fix_paths.py（四步路径修复）

自动化修复脚本，统一 JSON 文件与 SQLite 数据库中的会话路径。
在所有电脑上建好 Junction 后运行。它会自动探测 `.workbuddy` 位置（可处理
符号链接）以及需要替换的用户特定路径。

### scripts/restore_and_merge.py（会话恢复与合并）

会话恢复与合并工具。两种模式：

**恢复（restore）**：从结构化数据重建丢失会话的 JSONL 缓存。
要求正确的 `user_id`、反斜杠 cwd 和规范的 JSONL 格式。
云端摘要还在但本机消息缓存已丢时使用。

**合并（merge）**：把两个会话合并为一个，带去重、时间戳排序
和源会话软删除。合并前先备份目标。

### scripts/recover_session_jsonl.py（6.3+ 新增：对话历史失联恢复）

恢复因 5.5.x 升级把工作区路径重编码（junction 被解析为 WPS 云盘真实路径）而"消失"的
对话历史。自动扫描 `~/.workbuddy/projects/` 下的新旧编码目录对，逐会话合并新旧
JSONL（按消息 id 去重、旧记录优先），并把仅存在于旧目录的会话复制到新目录。
幂等、逐文件原子替换、全程不删除任何文件。完整操作手册见
「恢复 5.5.x 升级后"消失"的对话历史」章节。
