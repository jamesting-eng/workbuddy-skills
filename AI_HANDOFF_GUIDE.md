# AI 跨设备交接操作指南

> 两台电脑的 AI 老千都读这个。

---

## 架构速览

> **v3.2 (2026-07-06 修复)**: WPS 云盘同步已失效，**HANDOFF.md 不再走云盘，改走 sync_identity.py 中转通道**。

```
C:\WorkBuddy\_sync\              ← 本地目录（不是 Junction，v3.2 修正）
├── HANDOFF.md                  ← 交接单（机器生成区 + AI 手写区）
│                                  ↓ 双向同步
│                              C:\WorkBuddy\_sync\identity\HANDOFF.md  ← 中转副本
├── AI_HANDOFF_GUIDE.md         ← 本文件（v3.2 架构说明）
├── conversations/              ← 重要对话全文导出
│   └── YYYY-MM-DD-topic.md
├── workspace_sync.py           ← 机械同步脚本（生成机器区）
└── sync_identity.py            ← 身份+记忆+HANDOFF 跨设备同步脚本
                                  （已升级到 v3.2）
```

**核心原则**: DB 分叉，不共享对话历史。通过 HANDOFF.md + conversations/ 实现任务接续。

**跨设备同步机制**:
- **sync_identity.py 双向同步**（权威）: HANDOFF.md / 身份文件 / 各工作区 memory/
- **WPS 云盘直传**（v3.2 已弃用）: 原计划靠 `C:\WorkBuddy` Junction → WPS 云盘，2026-07 确认失效
- **兜底**: 任何一端运行 `python sync_identity.py push` / `pull` 即可手动同步

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

5. **执行 sync_identity.py push**（v3.2 关键步骤）
   ```bash
   python C:\WorkBuddy\_sync\sync_identity.py push
   ```
   - 推送 HANDOFF.md / 身份文件 / 工作区 memory 到中转目录
   - 看到 "HANDOFF.md (中转通道): pushed" 表示成功
   - **必须等到这一步完成再离开电脑！**

---

## 📥 拉取流程（到另一台电脑后）

**触发词**: "拉取同步" / "看交接单" / "继续" / "家里电脑弄好了没"

### ⚠️ 重要：sync pull 是强制动作，不是建议

用户说「拉取同步」时，**必须**实际执行 sync_identity.py pull 命令，**不能跳过**。
单读文档/记忆文件不够，因为中转目录可能有新内容还没分发到工作区。

### AI 必须做的事：

0. **执行 sync_identity.py pull**（铁律，v3.3 强制）
   ```bash
   # 推荐：直接用 一键同步.bat / pull.bat（已处理路径）
   # 或显式调用（%USERPROFILE% 跨机器通用，不再硬编码用户名）：
   "%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe" "C:\WorkBuddy\_sync\sync_identity.py" pull
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

## 🆕 新工作区自动同步（v3.3 新增）

**场景**: 用户新开一次 WorkBuddy 对话，系统创建新工作区目录（如 `2026-07-06-15-30-00\`）。

**AI 必须在工作区创建后立即做**:

1. **跑一次 sync pull**（把中转目录里其他电脑的工作拉过来，避免在空白工作区里干活）
2. **读取 STATUS.md**（如果中转里拉过来的）
3. **告知用户**：「新工作区已建立，已从家里/公司拉取最新状态」

**watch_sync 守护进程**:
- 后台常驻（开机自启），无需手动启动
- 监听整个 `C:\WorkBuddy\` 根，新工作区目录出现 0.3s 内自动纳入监听
- 文件一改 500ms 内自动 push 到中转
- **所以用户无需手动跑 sync 命令**，除了「拉取同步」这种主动要求

---

## ⚠️ 规则

1. **不要覆盖机器生成区**: `<!-- ⚙️ -->` 和 `<!-- ✅ -->` 之间的内容由 workspace_sync.py 维护
2. **不要修改 AI 手写区的结构**: 保持 `## 📋` / `## 💬` / `## 📎` 三个大标题
3. **对话摘要保持简洁**: 每条约 3-5 行，关键信息清晰
4. **不要在拉取后写回**: 拉取时只读 HANDOFF.md，不修改。只有推送时才写。
5. **旧摘要归档**: 超过 7 天的摘要移到 `_sync/conversations/archive/`（可选）
6. **安全**: 不要导出包含密码、Token、个人隐私的对话内容

---

## 🔧 workspace_sync.py 的行为

- 运行 `python workspace_sync.py` 时：
  - 更新 HANDOFF.md 中 `<!-- ⚙️ -->` 和 `<!-- ✅ -->` 之间的内容
  - 不会触碰 `<!-- ✅ -->` 之后的内容（AI 手写区安全）
- 建议每天至少运行一次（已有自动化）

---

*此文件通过 `sync_identity.py` 中转通道跨设备共享（v3.2+，不再依赖 Junction 直传），两台电脑的 AI 看到的是同一份中转副本。*
