# Cross-Device Sync for WorkBuddy / CodeBuddy

让 WorkBuddy 在多台 Windows 电脑之间无缝同步 — 在公司创建的对话，回家继续；家里的任务，公司接着干。

## 这是什么？

一个 [WorkBuddy](https://www.codebuddy.cn) 技能，解决多台 Windows 电脑之间 WorkBuddy 数据的同步问题。

**核心痛点**： `workbuddy.db`（SQLite）不能被两台电脑同时读写 — 会导致对话记录互相覆盖。每台电脑的 Windows 用户目录也不同，导致会话文件路径失效。

**解决方案（v6 混合三层架构）**：

- `workbuddy.db` 本地独立（不覆盖）
- 子目录通过符号链接同步 WPS 云盘
- 工作区通过 Junction 统一为 `C:\WorkBuddy\`
- **主同步 = WPS Junction**：整棵 `C:\WorkBuddy` 树（含隐藏 `.workbuddy`）由 WPS 云盘自动双向同步
- **中转兜底 = `sync_identity.py`**：经 `_sync/identity/` 精确控制身份文件 / HANDOFF / memory 同步，并清理 WPS 冲突副本
- **自动守护 = `watch_sync.py` v2.2 + `watchdog.bat`**：文件一变自动 push（单 leader 选举），进程崩溃/卡死自愈
- 通过 `HANDOFF.md` 交接单 + `AI_HANDOFF_GUIDE.md` 实现跨设备任务接续

> 📌 **架构勘误（v6）**：v3.2 曾断言「Junction 直传失效，一切改走中转」。**7 月实测证明该结论是误诊**——`C:\WorkBuddy` Junction 一直是正常工作的主同步通道（所谓"失效"实为 WPS 同步延迟 + AI 未写日志的人为遗漏）。正确认知是**三层并存、各司其职**：WPS Junction 主同步、中转通道兜底与精确控制、守护进程让中转实时化。中转通道仍保留：它是清理冲突副本、强制对齐、防 WPS 偷懒的必要工具。

## v6 更新了什么（相对 v5）

| 变更 | 说明 |
|------|------|
| `sync_identity.py` v3.5 → **v3.6** | **根治 MEMORY.md 跨工作区互覆污染**：collect/distribute 仅允许 `YYYY-MM-DD.md` 每日日志进入扁平用户级命名空间；项目身份文件（MEMORY.md/STATUS.md/DAILY_STATUS.md 等）一律跳过，不再被「mtime 较新者胜出」合并后扇回所有工作区（7/24、7/30 两次事故，14 个工作区 MEMORY.md 被同一份内容覆盖） |
| `watch_sync.py` v2.0 → **v2.2** | v2.1 自愈：主循环外套 try/except 永不退出、连续失败自动重建基线+兜底 pull、PID 文件、心跳线程保护；v2.2 卡死自愈：子进程全部带 `-S`（跳过 sitecustomize 对 WPS 路径 unlink/rmtree 的劫持——7/13 起静默僵死一周的根因）、主循环每轮更新 `liveness_<机器名>.txt` 活性信号 |
| **新增 `watchdog.bat`（v2）** | 看门狗：PID 不存在（崩溃/被杀）**或** liveness 超 240s 未更新（主循环 blocked）→ 任一成立即强杀重启；重启命令带 `-S`。放 `shell:startup` 获得机器重启级自愈 |
| `AI_HANDOFF_GUIDE.md` 重写 | 修正三层架构认知；新增「新工作区硬约束」（第一步必建 `.workbuddy/memory/STATUS.md` + 当日日志）与「收尾检查清单」；响应延迟如实标注 1-2s |

## 目录结构

```
（本仓库根目录即本技能的全部文件，无需子目录）

├── SKILL.md                          # 技能定义 & 完整操作指南
├── README.md                         # 本文件
├── LICENSE                           # MIT
├── .gitignore                        # 排除 secret.txt / 运行日志 / PID 等本地产物
├── PUBLISH.md                        # GitHub 发布指南
├── AI_HANDOFF_GUIDE.md               # AI 跨设备交接操作指南（两台 AI 共读）
├── sync_identity.py                  # 用户身份 & 记忆 & HANDOFF 中转同步脚本（v3.6）
├── watch_sync.py                     # 自动同步守护进程（v2.2：单 leader + 自愈 + 卡死自愈）
├── watchdog.bat                      # 看门狗（崩溃重启 + liveness 卡死强杀，放 shell:startup）
├── find_junk.py                      # WPS 冲突副本扫描器（生成 HTML 报告）
├── clean_junk.py                     # WPS 冲突副本清理器（双保险，只删有正本的）
├── workspace_sync.py                 # 机械同步脚本（DB 修复 + 交接单机器区生成）
├── secret.txt.example                # 同步暗号模板（复制为 secret.txt，勿提交真值）
├── fix_db_isolation_v3.ps1           # 数据库隔离脚本（核心，来自 v4）
├── fix_workspace_state_sync.ps1      # workspace-state 同步修复（来自 v4）
├── push.bat                          # 离开电脑前一键推送（handoff + verify）
├── pull.bat                          # 到另一台电脑一键拉取校验
├── 一键同步.bat                       # 拉取 + 启动守护进程
├── start_sync.bat                    # 守护进程启动器（拉起 watchdog 链）
└── scripts/
    ├── fix_paths.py                  # 路径修复脚本（四步，来自 v4）
    └── restore_and_merge.py          # 会话恢复 & 合并工具（来自 v4）
```

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

```
# 在每台电脑上运行，统一所有会话路径
python scripts/fix_paths.py
```

脚本会自动完成四步：JSON 修复 → 数据库修复 → 项目缓存合并 → JSONL cwd 路径修复。

### 3. 启动自动同步守护进程（v6 推荐 watchdog.bat）

```
# 开机自启（推荐）：把 watchdog.bat 放进 shell:startup（Win+R → shell:startup）
# 它会拉起 watch_sync.py 并持续守护：
#   - 进程不存在（崩溃/被杀/机器重启）→ 30s 内重启
#   - liveness_<机器名>.txt 超 240s 未更新（主循环卡死）→ 强杀重启
# 手动启动一次：
python -S watch_sync.py            # 常驻守护（单 leader 模式安全；-S 跳过 sitecustomize）
python -S watch_sync.py --status   # 查看监听状态 + leader 状态 + liveness 阈值
python -S watch_sync.py --once     # 跑一次同步就退出
```

> ⚠️ **务必用配套的 v2 版 `watchdog.bat`**。旧版只查 PID 存活，检测不了「进程活着但 blocked」的卡死（这正是 7/13 起静默死一周的真因）。注意 `_sync` 目录不在自动同步范围，升级时需手动把新版 `watch_sync.py` + `watchdog.bat` 复制到另一台电脑同路径。

守护进程会在后台监听源文件变化（扫描 1s + 防抖 1s ≈ 1-2 秒延迟）并自动 push；单 leader 选举确保同一时间只有一台机器写中转目录，根治 WPS 副本冲突风暴。

### 4. 使用交接单（跨设备任务接续）

**离开电脑前** — 说"生成交接单"或"同步任务"：

- AI 自动更新 `C:\WorkBuddy\_sync\HANDOFF.md`
- 包含活跃项目、任务进度、对话摘要、下一步行动
- 执行 `sync_identity.py push` 推到中转通道（**必须等推送完成再离开**）

**到另一台电脑后** — 说"拉取同步"或"继续上次"：

- AI 第一个动作：执行 `sync_identity.py pull`（铁律，不可跳过）
- 展示上一次的工作状态和上下文
- 无缝接续任务

> ⚠️ **WPS 同步会"偷懒"**：空目录 ≠ 没做。WPS 客户端有同步延迟，判断另一台机器是否有产出，必须交叉核对 `_sync/` 交接报告 + 对方机器实际路径，不能只看本地目录。

## 注意事项 & 踩过的坑

| 坑 | 现象 | 原因 | 解决 |
|----|------|------|------|
| **db 被同步覆盖** | 公司电脑对话消失，家里对话出现在公司 | `workbuddy.db` 在 WPS 云盘里被两台电脑共享 | 运行 `fix_db_isolation_v3.ps1`（v3 架构核心） |
| **新建工作区不显示** | 公司建的工作区，家里侧边栏没有 | `workspace-state.json` 是本地文件未同步 | 运行 `fix_workspace_state_sync.ps1` |
| **WAL 未刷盘** | 关闭后最新对话丢失 | WorkBuddy 没完全退出，WAL 文件残留 | 确认进程完全退出，WAL 文件消失 |
| **workspace-state.json 为空** | 侧边栏只显示1个工作区 | WPS 同步了旧版本或客户端覆盖了 | 从 DB 重建 workspace-state.json |
| **会话被软删除** | DB 有记录但侧边栏看不到 | WorkBuddy 客户端同步时标记 deleted_at | `UPDATE sessions SET deleted_at = NULL` |
| **缺少 .workbuddy 标记** | 工作区目录存在但 sidebar 不显示 | 目录缺少 `.workbuddy/memory/` 子目录 | 手动创建标记目录（新工作区第一步就建） |
| **路径分隔符** | 恢复的会话不在列表显示 | cwd 用了 `C:/...` 正斜杠 | 必须用 `C:\...` 反斜杠 |
| **user_id** | 同上 | 数据库里填了 `"default"` | 必须用真实 UUID |
| **时间戳年份** | 显示「56年前」且内容不渲染 | `created_at=0` 或秒级而非毫秒级 | 确保毫秒级 |
| **对话消失** | 路径修复后历史消息没了 | 项目缓存因路径变更分裂成两份 | `fix_paths.py` 第三步自动合并 |
| **deliver_attachments 静默失败** | 发送的文件对方收不到 | `~/.workbuddy/` 是 symlink 路径 | 先 `cp` 到 `C:\WorkBuddy\` 再 delivery |
| **AI 不知道读交接单** | 换电脑后 AI 说"已经同步好了"但看不到上下文 | AI 没有被指示要先读 HANDOFF.md | 更新 SKILL.md 强制规则（v4 已修复） |
| **WPS 副本冲突风暴** | 几千个 `-副本` 文件 | 两台电脑同时写同一 WPS 路径 | `watch_sync.py` 单 leader 选举 + `find_junk.py`/`clean_junk.py` 清理 |
| **守护进程静默死一周** | 7/7、7/13 两次，中转同步停摆无告警 | ① sync 超时异常未捕获直接退出；② sitecustomize 劫持 WPS 路径 unlink/rmtree 成永不返回的回收站子进程 → 主进程 blocked 但 PID 还在 | v2.1 进程级自愈 + v2.2 子进程全带 `-S`；看门狗查 liveness（不只 PID） |
| **看门狗检测不到卡死** | 进程活着但僵死，看门狗永不重启 | 旧 watchdog.bat 只 `tasklist` 查 PID | v2 版 watchdog.bat：liveness 超 240s → 强杀重启 |
| **MEMORY.md 跨工作区互覆污染** | 14 个工作区的 MEMORY.md 变成同一份内容（7/24、7/30 两次事故） | collect/distribute 把各工作区同名 MEMORY.md 压平到同一用户级命名空间，mtime 较新者胜出，再扇回所有工作区 | **v3.6**：身份文件不进扁平中转，仅 `YYYY-MM-DD.md` 每日日志走中转 |
| **每日日志同名残留风险** | 某工作区日志被扇出到多个工作区（7/11 NESPA 日志扇出 8 个区） | `YYYY-MM-DD.md` 跨工作区同名仍会互相覆盖 | **已知未修**：如需彻底隔离需按工作区命名空间化（更大重构） |
| **.bat 中文乱码** | CMD 里中文变乱码 | bat 文件存成了 UTF-8 | 含中文的 .bat 必须 GBK 编码；纯 ASCII 内容则任何编码都安全 |
| **沙箱无法测 .bat** | AI 沙箱里 `cmd /c`、`Start-Process cmd` 被禁 | WorkBuddy 沙箱安全策略 | .bat 只能在真机验证；沙箱内用直接拉起 python 进程的方式模拟验证 |
| **WPS 同步偷懒** | 公司机文件家里看不到，误判"没做" | WPS 客户端同步延迟/不彻底 | 手动刷新几次；跨机判空必须交叉核对 `_sync/` 交接报告 + 对方实际路径 |
| **跨机归因错误** | 把公司机 sync 过来的工作算成"家里做的" | WPS 会静默镜像工作产物 | 写收尾前按「分区约定」给每条工作判机器来源（provenance） |

## 运维约定（建议）

- **AI 分区**：两台电脑各只做一个项目（如家里=个人项目、公司=工作项目），避免同一事项跨机讨论导致记忆混乱
- **新工作区硬约束**：建区第一步就建 `.workbuddy/memory/STATUS.md` + 当日日志，否则叙事日志会断层
- **收尾铁律**：AI 若发现某工作区"空"，禁止直接判"无产出"，先交叉核对交接报告再下结论
- **暗号**：`secret.txt` 每次拉取后验证一致；**不要在聊天/文档中提交真值**

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

**Q: 守护进程挂了怎么办？**

v2.2 + watchdog.bat v2 的组合下：崩溃 30s 内自动重启、卡死（liveness 超 240s）自动强杀重启、机器重启由 shell:startup 兜底。手动检查：`python -S watch_sync.py --status`；看日志：`_sync/watch_sync.log`。

**Q: 出现大量 `-副本` 文件怎么办？**

用 `python find_junk.py` 扫描并生成报告，确认每个副本都有正本后，用 `python clean_junk.py --execute` 清理。当前单 leader 机制已阻止新副本产生，这是一次性清理。

**Q: MEMORY.md 被污染了怎么恢复？**

v3.6 已阻止再次发生。已被覆盖的文件：中转目录和同步命名空间里都没有干净备份，需回到对应工作区，靠对话历史/项目产出**手动针对性重建**（不要让 AI 批量自动重建，容易把污染内容再写回去）。

## 安装为 WorkBuddy 技能

1. 克隆本仓库到本地：

```
git clone https://github.com/jamesting-eng/workbuddy-skills.git
```

> 如果你 fork 了本仓库，clone 时把 `jamesting-eng` 换成你自己的 GitHub 用户名即可。

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
