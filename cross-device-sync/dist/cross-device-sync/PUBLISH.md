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
├── secret-example.txt
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

## 第四步：仓库信息（GitHub 网页，API 改不了，只能手动点一次）✅ 已完成（2026-08-15），无需再操作

1. 打开 https://github.com/jamesting-eng/workbuddy-skills
2. 右上角 About 区域 → 铅笔图标 ✏️
3. Description 填：

```
让 WorkBuddy / CodeBuddy 在多台 Windows 电脑之间无缝同步 — WPS 云盘中转 + 交接单 + 自动守护进程
```

4. 同一弹窗 Topics 逐个输入回车：

```
codebuddy  workbuddy  cross-device-sync  wps-cloud  sqlite  windows
```

> 效果：别人搜 `codebuddy` / `workbuddy` / `sync` 能命中本仓库；搜索结果一眼看懂用途。

---

## 验证

推送后访问 `https://github.com/<用户名>/workbuddy-skills` ，确认仓库根目录
下的文件都已更新（尤其是 README.md、SKILL.md、watch_sync.py、find_junk.py、clean_junk.py）。

---

## 第五步：发布到 SkillHub（推荐 CLI 通道，已实测跑通）

### 一次性准备

1. skillhub.cn 注册 + 实名认证，个人中心创建 API Token（`skh_...`）
2. 拿 CLI（单文件 Python，无需安装）：
   ```bash
   curl -fsSL https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/install/latest.tar.gz | tar -xz
   # 解出 cli/skills_store_cli.py，用本机 python 直接跑
   ```
3. SKILL.md frontmatter 补 SkillHub 必填字段：`slug` / `displayName` / `version` / `summary` / `tags` / `license`

### 发布流程（Windows 记得 `export PYTHONIOENCODING=utf-8` 防 GBK 编码错）

```bash
python skills_store_cli.py login --key skh_你的Token --host https://api.skillhub.cn
python skills_store_cli.py publish ./发布目录 --dry-run     # 预检
python skills_store_cli.py publish ./发布目录 --changelog "..." --json
# 成功返回 ok:true + skillId，reviewStatus=pending 等审核（1-7 个工作日）
```

### ⚠️ 平台文件类型白名单（实测被拒过的）

| 被拒文件 | 处理 |
|---|---|
| `.gitignore` | 发布目录剔除（仓库工件，不进技能包） |
| `LICENSE`（无扩展名） | 改名 `LICENSE.txt`（仅发布目录，GitHub 仓库保持无扩展名以被识别） |
| `secret.txt.example` | 改名 `secret-example.txt`，同步改文档引用 |
| **所有 `.bat`** | 剔除；看门狗用 **`watchdog.py`**（watchdog.bat 的 Python 移植版）替代，其余 bat 用 python 等价命令（README 里有说明段） |

`.py` / `.md` / `.ps1` / `.yaml` / `.txt` 实测可过。`dist/cross-device-sync/` 是当前合规的发布目录样板。

### 发布后

- 监控：开发者后台「我的技能」看审核状态（安全扫描 → 内容审核 → 上架）
- 被拒会附理由，改完重新 publish 即可
- 迭代版本：改 `manifest.yaml` 和 SKILL.md 的 version 后重新 publish

## 以后更新（铁律：GitHub 与 SkillHub 双端同步发版）

> **版本必须一致**：任何一次版本更新，GitHub 和 SkillHub 都要发，且版本号相同。
> 只发一边 = 未完成发版。GitHub About/Topics 已配置（2026-08-15），无需重复操作。

### 双发清单（按顺序执行）

1. **改版本号（两处必须同值）**：`manifest.yaml` 的 `version` + `SKILL.md` frontmatter 的 `version`
2. **更新发布目录**：把变更文件同步到 `dist/cross-device-sync/`（注意白名单：无 `.bat`、`LICENSE.txt`、`secret-example.txt`）
3. **GitHub 端**：
   ```powershell
   git add -A
   git commit -m "feat(cross-device-sync): vX.Y — 一句话变更说明"
   git push origin main   # 家里机需先挂 Clash 代理；PAT 用一次废一次
   ```
4. **SkillHub 端**（CLI 已 login 的前提下）：
   ```bash
   export PYTHONIOENCODING=utf-8
   python skills_store_cli.py publish ./dist/cross-device-sync --changelog "..." --json
   ```
5. **核对**：GitHub 仓库页面版本 = SkillHub 后台「我的技能」版本 = `manifest.yaml` 版本，三者一致才算发完
6. 若 SkillHub 审核被拒：按理由修改后重新 publish，**GitHub 端同步补 commit**（如修复文档/白名单问题），保持两端内容一致

### 发布前全量核对清单（一次发对 · 杜绝无效版本号）

SkillHub **没有 unpublish API**，发错一次就永久留一个垃圾版本。所以**每次上架前必须逐文件过一遍**，下面每条都打勾才能发。

- [ ] **语言**：SkillHub 树 = **100% 中文**；GitHub 树 = **100% 英文**。脚本（`.py` / `.bat` / `.ps1` / `.cmd`）**禁止翻译**。（历史事故：英文 SKILL.md 曾两次误发到 SkillHub，白烧了版本号。）
- [ ] **版本号 5 处逐字节一致**：`manifest.yaml` = `SKILL.md` frontmatter = `package.py` VERSION = GitHub commit 信息 = SkillHub 版本号。
- [ ] **版本说明 / changelog 逐行读**：级别对、版本号对、**无错别字**、无上版复制粘贴的残句。
- [ ] **版本历史必须是真文本、且不含任何文件名 / 路径**：以 inline 方式传入（**严禁** `--changelog <路径>` 或 `@文件`，历史翻车点）；发布后从 SkillHub 回读，确认显示的是文本而非路径。
- [ ] **每个改动过的文件都要通读**（不是只看 `git diff --stat`）。
- [ ] **文件清单核对**：打包列表与预期数量一致（如 23 个文件）；确认没有混入 `.gitignore` / `.bat` / 无扩展名 `LICENSE`（SkillHub 会拒收）。
- [ ] **隐私 PII 扫描**：覆盖 `.py` / `.md` / `.yaml` / `.ps1` / `.bat` / `.cmd` / `.txt`。
- [ ] **`py_compile`** 全部 `.py`；**`.bat` / `.cmd` 必须 CRLF + 纯 ASCII**。
- [ ] **改动脚本至少跑一遍 `--dry-run`** 冒烟。

### 待发布（Unreleased · 暂不上架）

> **发布时机纪律**：云端**只上稳定版**。已知后续还要改（比如等官方回了 2026-09-17 工单、技能必然要跟着调）时，改动先攒在这里。本地版本号已**锁到 6.4.0**（如实记录现状），云端发布推迟到官方修复落地后，届时一次性发 **6.4.0**（不在 SkillHub 上发任何中间版本号）。

| 改动项 | 级别 | 说明 |
|---|---|---|
| `recover_session_jsonl.py`：按 `id` 去重会丢 1481 行合法记录 | PATCH | 已改为按整行序列化去重 |
| `recover_session_jsonl.py`：候选目录未排除旧编码 `c-` 前缀 | PATCH | 会把内容在两个旧编码目录间来回写，而非写入 UI 读取的 gen3 |
| `recover_session_jsonl.py`：新增 `--exclude <工作区后缀,...>` 参数 | MINOR | 恢复时可跳过正在活跃的工作区 |
| D 盘 AI 产物暂存区约定与清理脚本 | PATCH | 将 AI 编程产生的测试配置、临时缓存、脚本日志统一落在 `D:\WorkBuddy\<用途名称>\`；禁止直接在 D 盘根新建文件夹；交付物仍经 `C:\WorkBuddy\`（WPS Junction）同步；D:\WorkBuddy 暂存区不参与 WPS 同步；配套清理 log 脚本。 |
| artifact-index 僵尸复活根因补充 + 自愈自动化 | PATCH | 补充说明 artifact-index 目录本身是 WPS 云盘 junction，旧清理只在同步时运行、平时不生效；新增「产物索引自愈清理」WorkBuddy 自动化配置：每 24 小时一次、绑定当前工作区、用 `-S` + `--all-sessions --quiet`、输出仅一行。 |
| `.workbuddy` 数据布局：4 个物理目录（工作区/日志/edgeone 缓存/变更明细）迁移到 D:\WorkBuddy\.workbuddy 并 junction 指回；22 个 WPS junction 不动 | MINOR | 释放 C 盘约 3.4 GB；SKILL.md 新增迁移配方与可续传脚本模式章节；说明混合布局（.workbuddy 根 = 22 个 WPS junction + 4 个物理目录）及「绝不搬迁 WPS junctioned 目录」规则。已于 2026-09-29 在公司机实测迁移并验证。 |

**计划目标版本：6.3.9 → 6.4.0（取本批最高级别 MINOR）。**
**等官方回信后再统一发布**——官方修复大概率还会牵动技能改动。

**6.4.0 草稿 changelog（用户视角，发 SkillHub 时直接抄，不含内部文件名）：**

> 6.4.0 —— 会话历史恢复加固 + D 盘产物暂存区约定 + .workbuddy 布局迁移
> - 修复会话历史恢复时，两个会话共用同一 ID 会丢掉合法记录的问题；现按整行去重。
> - 修复恢复时有时会在两个旧路径编码文件夹之间互写、而非写入规范目录的问题。
> - 新增「恢复时跳过正在活跃的工作区」选项，避免打扰正在进行的工作。
> - 补充 D:\WorkBuddy 产物暂存区约定：AI 编程产生的测试配置、临时缓存、脚本日志统一落在 D:\WorkBuddy\<用途名称>\，不再散落在 D 盘根；最终交付物仍经 C:\WorkBuddy（WPS Junction）同步；D 盘暂存区不参与 WPS 同步，并附清理 log 脚本。
> - 新增「产物索引自愈清理」自动化配置模板：绑定当前工作区、每天运行一次、清理所有会话里的失效引用，让你即使不手动跑同步，IDE 产物面板也不会残留死条目。
> - 将技能的 4 个物理数据目录（工作区 / 日志 / edgeone 缓存 / 变更明细）迁移到 D:\WorkBuddy\.workbuddy 并 junction 指回，22 个 WPS junction 原样不动；为 C 盘释放约 3.4 GB，并在 SKILL.md 中补充了迁移配方与「绝不搬迁 WPS junctioned 目录」的规则。

### 历史发版记录

| 版本 | 日期 | GitHub commit | SkillHub |
|---|---|---|---|
| 6.0.0 | 2026-08-15 | `71a0569` | skillId=156632 / versionId=238390，审核 pending |
| 6.1.1 | 2026-09-02 | `ceec8af` | skillId=156632，新增 5.4.7 IndexedDB 应急持久化 SOP + sync_cli.py 统一入口；同步将 SkillHub 线上包从 v5 文件集提升为与 GitHub v6 一致（补 watchdog.py / manifest.yaml / LICENSE.txt / sync_identity v3.6 / watch_sync v2.2） |
| 6.3.0 | 2026-09-04 | `b9ad626` | 新增 5.5.x「路径重编码致历史失联」恢复 SOP + `scripts/recover_session_jsonl.py`（id 去重合并、幂等、原子替换）；SkillHub 中文版 changelog 全中文 |
| 6.3.1 | 2026-09-04 | 本次 | GitHub 端全量英文化（全部文档+脚本注释，功能字面量保留加注）；SkillHub 端中文查缺补漏（SOP 章节英文段落全部翻译） |
| 6.3.3 | 2026-09-06 | (已在树内；并入 6.3.4) | 新增「在 WPS 云盘同步路径下安全删除文件（三板斧）」章节：python -S 绕过 sitecustomize + 只用 os.remove + 每进程 ≤40 文件多进程循环到零；新增「为什么项目状态和产物列表偶尔会冲突（以及怎么防）」章节：workspace-state.json 同步竞态、扁平命名空间 MEMORY.md 污染（7/24 与 7/30 事故）、STATUS.md 过期、守护进程 leader 选举。SkillHub 中文完整日志 |
| 6.3.4 | 2026-09-07 | （内部版，未对外推送，自销） | 内部测试版意外带出真实机器名、Windows 用户名、WPS 云盘数字 ID、项目名。发现后立即自销，未对外发布。下方的 6.3.5 是脱敏重发版，变更日志里写清用哪些占位符替换了哪些真实标识（OFFICE-PC / HOME-PC / Bob / Alice / 123456789 / MyProject 等） |
| 6.3.5 | 2026-09-07 | (本次提交) | v3.8 对 IDE 产物面板僵尸复活（WPS 路径 vs 本地缓存冲突）的系统级根治：`sync_identity.py` 现在用 `cleanup_memory_non_md()` 把 `.workbuddy/memory/` 画死为只允许 `.md`（根除"本地清理 → WPS 副本反向拉回"死循环），并集成 `cleanup_artifact_index.py` 在每次同步时清掉失效的 artifact-index URI（默认活跃优先，加 `--all-sessions` 全清）；同时并入 6.3.3 的「三板斧安全删除」与「项目状态/产物列表冲突」章节。SkillHub 中文完整日志 |
| 6.3.6 | 2026-09-07 | (本次提交) | 安全加固 —— 重发以清除 6.3.5 被安全扫描标记的风险旗：把全部无条件删文件路径（sync_identity.py 里的 cleanup_duplicates / cleanup_memory_non_md、sync_cli.py 里的临时/目标 unlink、watchdog.py / watch_sync.py 里的守护进程 pidfile unlink）统一替换为可恢复、可干预的 safe_remove()（移到隔离区、永不硬删；CDS_DRY_RUN=1 仅审计）。同步行为零变化。SkillHub 变更日志全中文 |
| 6.3.7 | 2026-09-07 | (本次提交) | 文档 + 发布历史对齐 —— 把 SKILL.md / README.md 总览段落与 PUBLISH.md 发布历史表与实际 `sync_identity.py` v3.8 代码对齐：根目录 `### sync_identity.py (v3.6)` 标题与 README.md 里 v3.6 单行 changelog 改为 v3.6（MEMORY.md 边界）→ v3.7（write-back 关停）→ v3.8（artifact-index + memory .md-only 防御）的完整演进链；发布历史表新增 6.3.4 一行，记录内部隐私泄漏自销的测试版（脱敏后的 6.3.5 才是首个对外发布）。零行为变更，纯文档。GitHub 端按已固化的沙箱发布流程走 Git Data API（PAT 走 `Authorization: token` 头，无 GCM 弹窗）；SkillHub 端同步重发 |
| 6.3.8 | 2026-09-07 | (本次提交) | 文档对齐补漏 —— 6.3.7 的对齐仍漏掉 5 处 v3.6 单行残留（根 README.md「v6 更新了什么」表行 + 目录树注释、dist README.md 表行、dist SKILL.md 资源标题 + v3.7/v3.8 说明块）。本版补齐：四份文档（根 + dist 的 SKILL.md / README.md）现已统一走 v3.6（MEMORY.md 边界）→ v3.7（write-back 关停）→ v3.8（artifact-index + memory .md-only 防御）完整演进链，且根 SKILL.md 正文已补上 v3.7/v3.8 后缀以与 dist 双生版一致。零行为变更，纯文档。GitHub 端走 Git Data API（无 GCM 弹窗）；SkillHub 端重发（同版本禁重发规则要求 bump 版本）。 |
| 6.3.9 | 2026-09-07 | (本次提交) | **行为修复（v3.9）＋ SkillHub 英文版复发根治** —— `collect_workspace_memories_to_user()` 现在把每个工作区的每日日志按工作区隔离到 `LOCAL/memory/<工作区名>/YYYY-MM-DD.md`（每个工作区一个子目录），不再用扁平的 `LOCAL/memory/YYYY-MM-DD.md`（多工作区同日日志会被「新 mtime 覆盖旧」挤掉，8/26 桌游工作区日志覆盖法务工作区日志、经 WPS 云盘污染的事故即源于此）。遗留的扁平每日日志一律**移动**（永不删除）到 `LOCAL/_v39_legacy_flat_quarantine/`。同时根治 SkillHub 6.3.8 误发英文版的问题：`package.py` 改为从 `dist/cross-device-sync/`（中文树）打包，而非 ROOT（英文树）。GitHub 端走 Git Data API（无 GCM 弹窗）；SkillHub 端全中文重发（同版本禁重发规则要求 bump 版本）。 |
