# AI 跨设备交接操作指南

> 两台电脑的 AI 老千都读这个。

---

## 架构速览（2026-07-13 实测，重要）

```
C:\WorkBuddy\                       ← 家里/公司都是 WPS 云盘的 Junction（同一物理文件）
├── <workspace>\.workbuddy\memory\  ← 工作区记忆（含隐藏目录，WPS 主同步自动带走）
└── _sync\
    ├── HANDOFF.md                  ← 交接单（机器生成区 + AI 手写区），WPS 物理共享
    ├── AI_HANDOFF_GUIDE.md         ← 本文件
    ├── conversations\              ← 重要对话全文导出
    ├── workspace_sync.py           ← 机器区生成脚本
    ├── sync_identity.py            ← 中转通道双向同步脚本（兜底 + 精确控制）
    ├── watch_sync.py               ← 守护进程 v2.2（自愈 + 卡死自愈）
    ├── watchdog.bat                ← 看门狗（崩溃 30s 内重启 + liveness 卡死强杀）
    └── identity\                   ← 中转目录（sync_identity.py 用，非主通道）
```

**三层同步，职责不同：**

| 层 | 机制 | 角色 | 是否必须 |
|----|------|------|----------|
| **主同步** | `C:\WorkBuddy` 是 WPS 云盘 Junction，整棵树（含隐藏 `.workbuddy`）自动双向同步 | 工作区文件 + memory 的**默认通道** | ✅ 一直在线 |
| **中转兜底** | `sync_identity.py` 走 `_sync/identity\` 中转目录 | 强制 push/pull、清 WPS 冲突副本、跨机精确控制 | 可选（手动 / 守护进程自动） |
| **自动守护** | `watch_sync.py` 监听源文件变化 → 自动 trigger 中转 push | 让中转通道实时跟上，单 leader 防副本 | 增强项（v2.2 自愈+卡死自愈） |

**核心原则**：DB 分叉，不共享对话历史。通过 HANDOFF.md + conversations/ + 工作区 memory 实现任务接续。

> ⚠️ **历史坑（已修正）**：早期文档写过"WPS 云盘已弃用、HANDOFF.md 走中转通道"——
> 那是 2026-07-06 公司机 WPS 一度故障时写的，**与家里实测不符**。家里 `C:\WorkBuddy`
> 实测就是 WPS junction，WPS 是主同步（含隐藏 `.workbuddy`）。以本文件 + HANDOFF.md 为准。

---

## 📤 推送流程（离开电脑前）

**触发词**: "准备换电脑" / "今晚收尾" / "写交接单" / "准备下班"

### AI 必须做的事：

1. **更新 HANDOFF.md 的任务进度区**
   - 定位 `<!-- ✅ 以下为 AI 手写区 -->` 之后的内容
   - 更新 `## 📋 任务进度` 下各项目的状态、勾选
   - 新增或修改任务项

2. **追加对话摘要**
   - 在 `## 💬 近期对话摘要` 下追加新条目
   - 格式：
     ```markdown
     ### [日期 时间] 话题名称 — 当前电脑
     - **摘要**: 1-3 句话
     - **关键决策**: 列表
     - **产出**: 列表
     ```

3. **导出重要对话**（如果有实质性讨论）
   - 将当前对话的完整内容写入 `_sync/conversations/YYYY-MM-DD-topic.md`
   - 格式包含：话题、时间、完整对话记录
   - 在 HANDOFF.md 的 `## 📎 导出对话` 表格中添加一行

4. **更新页眉时间戳**
   - HANDOFF.md 顶部的 `**最后更新**` 时间

5. **（推荐）执行 sync_identity.py push 兜底**
   ```bash
   python C:\WorkBuddy\_sync\sync_identity.py push
   ```
   - WPS 主同步通常在跑，但手动 push 能确保中转通道也最新，另一台 `pull` 立即拿到。
   - 看到 "HANDOFF.md (中转通道): pushed" 表示成功。

---

## 📥 拉取流程（到另一台电脑后）

**触发词**: "拉取同步" / "看交接单" / "继续" / "家里电脑弄好了没"

### ⚠️ 重要：sync pull 是强制动作，不是建议

用户说「拉取同步」时，**必须**实际执行 sync_identity.py pull 命令，**不能跳过**。
单读文档/记忆文件不够，因为中转目录可能有新内容还没分发到工作区。

### AI 必须做的事：

0. **执行 sync_identity.py pull**（铁律）
   ```bash
   python C:\WorkBuddy\_sync\sync_identity.py pull
   ```
   - 从中转目录拉取 HANDOFF.md / 身份文件 / 工作区 memory
   - 看到 "HANDOFF.md (中转通道): pulled" 表示成功
   - **如果失败**：明确告诉用户「同步失败，X 错误」，不要假装成功

1. **读取 HANDOFF.md**（C:\WorkBuddy\_sync\HANDOFF.md）
   - 检查同步暗号（验证是否能看到另一台电脑留的暗号）
   - 理解当前任务进度
   - 阅读近期对话摘要

2. **检查导出对话**
   - 看 `## 📎 导出对话` 表格
   - 读取 `_sync/conversations/` 中的新文件
   - 获取完整上下文

3. **读取项目 memory**
   - `C:\WorkBuddy\{workspace}\.workbuddy\memory\MEMORY.md`
   - `C:\WorkBuddy\{workspace}\.workbuddy\memory\YYYY-MM-DD.md`

4. **向用户汇报**
   - 同步暗号是否通过
   - 当前任务进度概览
   - 最近一次对话的关键点
   - 询问是否继续

---

## 🆕 新工作区硬约束（v3.3 固化，防 7/11 断档）

> **根因复盘（2026-07-11）**：用户在公司新建工作区做大量 Axistar 工作，但 AI 没给该工作区
> 建 `.workbuddy/memory`，也没更新 HANDOFF.md。结果这批工作的**叙事日志完全没同步过来**
> （工作产物靠 WPS 主同步到了，但 AI 日志为零）。规则断层，非同步故障。

**AI 在新工作区创建后，第一步必须（顺序不可省）：**

1. **建状态文件** `.workbuddy/memory/STATUS.md`
   - 含：项目身份、当前阶段、关键约束、待决策项
   - 这是工作区的"身份证"，WPS 主同步会自动把它带走
2. **建当日日志** `.workbuddy/memory/YYYY-MM-DD.md`
   - 记录本次开局做了什么、决定了什么
3. **跑一次 sync pull**（把中转里其他电脑的状态拉过来，避免空白工作区里盲干）
4. **告知用户**：「新工作区已建立，已建 memory/STATUS，并从中转拉取最新状态」

**每次实质性工作结束，必须（收尾检查清单见下）：**
- 写/更新项目 memory（MEMORY.md 长期 + 当日日期日志）
- 更新 HANDOFF.md 手写区（任务进度 + 对话摘要）
- 这两条写进文件后，WPS 主同步会自动同步，另一台即可见

---

## 🔚 收尾检查清单（离开电脑前，AI 自检）

```
□ 项目 memory 已更新？（MEMORY.md 或当日 YYYY-MM-DD.md）
□ HANDOFF.md 手写区已更新？（任务进度 + 对话摘要 + 页眉时间）
□ 重要对话已导出 conversations/？（如有实质讨论）
□ sync_identity.py push 已跑？（推荐，确保中转也最新）
□ 用户已被告知"可以换电脑了"？
```
> 任一项未完成 → 不要说"交接完成"。WPS 主同步靠的是**文件真实存在**，
> AI 不写文件 = 对面永远看不到，与守护进程是否活着无关。

---

## 🤖 watch_sync 守护进程（v2.2，自愈 + 卡死自愈）

- **作用**：后台监听 `C:\WorkBuddy` + `~/.workbuddy` 源文件变化，自动 trigger 中转 push
- **单 leader 选举**：两台机器各写 `heartbeat_<机器名>.txt`，只有唯一活跃机才 push，防并发写副本
- **响应延迟**：扫描 1s + 防抖 1s ≈ 变化后 **1-2 秒**自动 push（旧文档写的 0.3s/500ms 是夸大）
- **v2.1 自愈（根治 7/7 静默死）**：
  - 进程级：主循环外套 try/except，任何异常只记日志 + 10s 后重建基线重进，进程**永不退出**
  - run_sync 自愈：连续失败计数，达阈值（3）自动重建基线 + 兜底 pull
  - 心跳线程异常保护
- **v2.2 卡死自愈（根治 7/13 起的「进程活着但 blocked」）**：
  - 根因：WorkBuddy 的 sitecustomize.py 劫持 WPS 路径上的 unlink/rmtree 成「永不返回的回收站子进程」→ 僵死
  - 所有子进程调用带 `-S`（跳过 sitecustomize），从根消除死锁
  - 主循环每轮 scan 更新 `liveness_<机器名>.txt`；看门狗据此判定卡死（>240s 未更新 → 强杀重启）
  - ⚠️ 看门狗必须用配套的 v2 版 `watchdog.bat`（同时查 PID 存活 + liveness 新鲜度，启动带 `-S`）；
    旧版只查 PID，检测不到 blocked，v2.2 的卡死自愈会失效
- **启动**：开机自启 `watchdog.bat`（放 shell:startup，推荐）；或 `start_sync.bat` 拉起 watchdog 链
- **所以用户无需手动跑 sync**，除了「拉取同步」这种主动要求；离开前跑一次 push.bat 是双保险

---

## ⚠️ 规则

1. **不要覆盖机器生成区**: `<!-- ⚙️ -->` 和 `<!-- ✅ -->` 之间的内容由 workspace_sync.py 维护
2. **不要修改 AI 手写区的结构**: 保持 `## 📋` / `## 💬` / `## 📎` 三个大标题
3. **对话摘要保持简洁**: 每条约 3-5 行，关键信息清晰
4. **不要在拉取后写回**: 拉取时只读 HANDOFF.md，不修改。只有推送时才写。
5. **旧摘要归档**: 超过 7 天的摘要移到 `_sync/conversations/archive/`（可选）
6. **安全**: 不要导出包含密码、Token、个人隐私的对话内容
7. **新工作区必建 memory**: 见「新工作区硬约束」章节，不可省略

---

## 🔧 workspace_sync.py 的行为

- 运行 `python workspace_sync.py` 时：
  - 更新 HANDOFF.md 中 `<!-- ⚙️ -->` 和 `<!-- ✅ -->` 之间的内容
  - 不会触碰 `<!-- ✅ -->` 之后的内容（AI 手写区安全）
- 建议每天至少运行一次（已有自动化）

---

*此文件通过 WPS junction 物理共享（`C:\WorkBuddy` 是云盘 Junction），两台电脑的 AI 看到的是同一份物理文件。*
