---
name: sync-identity
description: |
  跨设备用户身份 & 记忆同步脚本。通过 C:\WorkBuddy\_sync\identity\ 中转，
  实现 ~/.workbuddy/memory/ 等用户级文件在双电脑间同步。
  触发词：「拉取同步」「push 同步」「跨设备记忆」。
agent_created: true
---

# sync_identity.py — 跨设备身份 & 记忆同步

## 文件位置

`C:\WorkBuddy\_sync\sync_identity.py`（通过 WPS 云盘跨设备同步）

## 功能

| 命令 | 作用 |
|------|------|
| `python sync_identity.py` | 双向同步（较新者胜出）|
| `python sync_identity.py push` | 强制本地 → 云盘（离开电脑前执行）|
| `python sync_identity.py pull` | 强制云盘 → 本地 + 分发到各工作区（到新电脑后执行）|

## 同步范围（v3.1）

- `~/.workbuddy/memory/` ↔ `_sync/identity/memory/`（每日交接单、对话记忆）
- `~/.workbuddy/SOUL.md`、`IDENTITY.md`、`USER.md` ↔ `_sync/identity/`
- `~/.workbuddy/workspace-state.json` ↔ `_sync/identity/`
- 各工作区 `.workbuddy/memory/` ↔ `_sync/identity/workspaces/<name>/memory/`

## 使用流程

### 离开公司电脑前
```bash
python C:\WorkBuddy\_sync\sync_identity.py push
```
执行后关闭 WorkBuddy，等 5 秒让 WAL 落盘，再关电脑。

### 到家打开家里电脑
```bash
python C:\WorkBuddy\_sync\sync_identity.py pull
```
脚本会自动把云盘上的记忆分发到所有本地工作区。

## pull 后的验证

对老千说：**「拉取同步，看交接单」**
- 应能读到公司电脑上写的交接单（`~/.workbuddy/memory/YYYY-MM-DD.md`）
- 各工作区的 `.workbuddy/memory/` 也有相同内容

## 和 workspace_sync.py 的关系

| 脚本 | 同步层次 | 说明 |
|------|-----------|------|
| `workspace_sync.py` | 工作区级 | 扫描 C:\WorkBuddy、更新 workspace-state.json、生成 HANDOFF.md |
| `sync_identity.py` | 用户级 | 同步 ~/.workbuddy/memory 等身份文件，分发到各工作区 |

**两个都跑，跨设备体验才完整。**

## 故障排查

### pull 后交接单还是空的
- 检查 WPS 云盘是否已完成同步（看网页端是否有最新文件）
- 手动检查：`cat ~/.workbuddy/memory/2026-06-18.md`

### push 时报文件被占用
- 先关闭 WorkBuddy，等 5 秒再试

### 家里电脑开了新工作区，读不到公司的工作区记忆
- v3.1 已修复：pull 时会把用户级记忆分发到所有本地工作区
- 若仍失败，手动复制：`cp ~/.workbuddy/memory/*.md <workspace>/.workbuddy/memory/`
