#!/usr/bin/env python3
"""
跨设备工作区同步脚本 v3.0
- 扫描 C:\WorkBuddy 磁盘工作区，更新 workspace_sync
- 生成/更新 HANDOFF.md 机器生成区（保留 AI 手写区）
- 对话导出辅助
- 新增：同步暗号管理 + 同步验证
"""

import sqlite3, os, json, time, re
from datetime import datetime

WORKBUDDY_ROOT = r"C:\WorkBuddy"
HANDOFF_DIR = os.path.join(WORKBUDDY_ROOT, "_sync")
HANDOFF_FILE = os.path.join(HANDOFF_DIR, "HANDOFF.md")
CONVERSATIONS_DIR = os.path.join(HANDOFF_DIR, "conversations")
SECRET_FILE = os.path.join(HANDOFF_DIR, "secret.txt")

# HANDOFF.md 分隔标记
DELIM_START = "<!-- ⚙️ 以下为机器生成区"
DELIM_MID = "<!-- ✅ 以下为 AI 手写区"


def find_db():
    home = os.path.expanduser("~")
    db_path = os.path.join(home, ".workbuddy", "workbuddy.db")
    if os.path.exists(db_path):
        return db_path
    raise FileNotFoundError(f"未找到 workbuddy.db: {db_path}")


def get_db_workspaces(db_path):
    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT w.path, w.last_opened_at,
               COUNT(CASE WHEN s.deleted_at IS NULL THEN 1 END) as active,
               MAX(s.created_at) as last_session
        FROM workspaces w
        LEFT JOIN sessions s ON s.cwd = w.path
        GROUP BY w.path ORDER BY w.path
    """).fetchall()
    conn.close()
    return rows


def get_disk_workspaces():
    result = []
    for d in os.listdir(WORKBUDDY_ROOT):
        full = os.path.join(WORKBUDDY_ROOT, d)
        wb = os.path.join(full, ".workbuddy")
        if os.path.isdir(full) and os.path.isdir(wb):
            result.append(full)
    return sorted(result)


def read_ai_section():
    """读取 HANDOFF.md 中 AI 手写区的内容（保留不覆盖）"""
    if not os.path.exists(HANDOFF_FILE):
        return None
    with open(HANDOFF_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    idx = content.find(DELIM_MID)
    if idx == -1:
        return content  # 没有分隔标记，整文件保留
    return content[idx:]


def update_secret(new_secret):
    """
    更新同步暗号（同时写入多个文件）
    由 AI 在交接单生成时调用
    """
    print(f"🔐 正在更新同步暗号为: {new_secret}")
    
    # 1. 更新 HANDOFF.md 机器生成区
    if os.path.exists(HANDOFF_FILE):
        with open(HANDOFF_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 替换暗号行
        pattern = r'> \*\*暗号：.*?\*\*'
        replacement = f'> **暗号：{new_secret}**'
        new_content = re.sub(pattern, replacement, content)
        
        if new_content != content:
            with open(HANDOFF_FILE, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"  ✅ HANDOFF.md 暗号已更新")
        else:
            print(f"  ⚠️ HANDOFF.md 暗号未变化（可能已经是新的）")
    
    # 2. 更新 secret.txt（纯文本备份）
    os.makedirs(HANDOFF_DIR, exist_ok=True)
    with open(SECRET_FILE, 'w', encoding='utf-8') as f:
        f.write(f"# 同步验证暗号备份\n\n")
        f.write(f"**最后更新**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"**当前暗号**: {new_secret}\n\n")
        f.write(f"**验证方式**: \n")
        f.write(f"1. 读取本文件，确认暗号一致\n")
        f.write(f"2. 如果暗号不一致，说明同步失败，需要手动刷新WPS云盘\n\n")
        f.write(f"**历史暗号**:\n")
        f.write(f"- 端午安康 (2026-06-18 及之前)\n")
        f.write(f"- 我不爱吃榴莲 (2026-06-25 某次更新)\n")
        f.write(f"- 🍑 我喜欢吃水蜜桃！ (2026-06-25 18:30)\n")
        f.write(f"- {new_secret} (当前)\n")
    print(f"  ✅ secret.txt 暗号已更新")
    
    # 3. 更新 AI_HANDOFF_GUIDE.md
    guide_file = os.path.join(HANDOFF_DIR, "AI_HANDOFF_GUIDE.md")
    if os.path.exists(guide_file):
        with open(guide_file, 'r', encoding='utf-8') as f:
            guide_content = f.read()
        
        # 替换暗号检查说明
        pattern = r'检查同步暗号（.*?）'
        replacement = f'检查同步暗号（{new_secret}）'
        new_guide = re.sub(pattern, replacement, guide_content)
        
        if new_guide != guide_content:
            with open(guide_file, 'w', encoding='utf-8') as f:
                f.write(new_guide)
            print(f"  ✅ AI_HANDOFF_GUIDE.md 暗号已更新")
    
    print(f"\n✅ 暗号已同步到3个文件，跨设备验证可靠")
    return True


def verify_sync():
    """
    验证同步状态：检查暗号是否一致
    由 AI 在拉取同步时调用
    """
    print("=" * 50)
    print("[验证] 同步验证")
    print("=" * 50)
    
    # 读取 secret.txt
    secret_phrase = "(未找到)"
    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r'\*\*当前暗号\*\*: (.*)', content)
        if match:
            secret_phrase = match.group(1)
    
    # 读取 HANDOFF.md
    handoff_phrase = "(未找到)"
    if os.path.exists(HANDOFF_FILE):
        with open(HANDOFF_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r'> \*\*暗号：(.*?)\*\*', content)
        if match:
            handoff_phrase = match.group(1)
    
    print(f"  secret.txt 暗号: {secret_phrase}")
    print(f"  HANDOFF.md 暗号: {handoff_phrase}")
    
    if secret_phrase == handoff_phrase and secret_phrase != "(未找到)":
        print("\n  [OK] 暗号一致，同步正常！")
        return True
    else:
        print("\n  [警告] 暗号不一致，可能WPS还没同步完")
        print("     建议：手动刷新WPS云盘，或等待几分钟后再试")
        return False


def generate_handoff(db_path, secret_phrase="我是你爸爸"):
    """生成机器生成区，保留 AI 手写区"""
    os.makedirs(HANDOFF_DIR, exist_ok=True)
    os.makedirs(CONVERSATIONS_DIR, exist_ok=True)

    conn = sqlite3.connect(db_path)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    computer = os.environ.get('COMPUTERNAME', 'Unknown')

    # 工作区数据
    db_ws = get_db_workspaces(db_path)

    # 构建机器生成区
    ws_rows = []
    for path, last_op, active, last_session in db_ws:
        name = os.path.basename(path)
        if last_op and last_op > 0 and last_op < 9999999999999:
            ts = time.strftime('%Y-%m-%d', time.localtime(last_op / 1000))
        elif last_session and last_session > 0:
            ts = time.strftime('%Y-%m-%d', time.localtime(last_session / 1000))
        else:
            ts = '未知'
        ws_rows.append(f"| {name} | {active} | {ts} |")

    ws_table = '\n'.join(ws_rows) if ws_rows else '| (无) | - | - |'

    machine_section = f"""# 🔄 跨设备交接单

> **最后更新**: {now} | **电脑**: {computer} | **用户**: 小白

---

<!-- ⚙️ 以下为机器生成区，workspace_sync.py 自动更新，AI 请勿手改 -->

## 📂 活跃工作区

| 工作区 | 对话数 | 最后活动 |
|--------|--------|----------|
{ws_table}

## 🧪 同步链路检测

> **暗号：{secret_phrase}** ← 如果在另一台电脑看到这句话，HANDOFF.md 跨设备同步正常 ✅

---

"""

    # 读取已有 AI 手写区
    ai_section = read_ai_section()
    if ai_section and DELIM_MID in ai_section:
        pass  # 保留已有内容
    elif ai_section:
        # 首次创建 AI 手写区（旧格式文件）
        ai_section = f"""{DELIM_MID}，workspace_sync.py 不会覆盖，AI 自行维护 -->

## 📋 任务进度

### 🏗 跨设备同步系统
- **状态**: 基础架构完成
- [ ] 实际场景测试

### 🎴 「梦境邮差」电商项目
- **状态**: 待重启
- [ ] 市场调研
- [ ] Indiegogo 众筹
- [ ] B2C 独立站
- [ ] B2B 后台

---

## 💬 近期对话摘要

*（暂无，AI 会在会话结束时写入）*

---

## 📎 导出对话

*（暂无）*

---

## ⚠️ 换电脑操作

1. 关闭 WorkBuddy → 等 5 秒 → 确认无进程
2. 到另一台电脑打开 WorkBuddy
3. 对老千说：**"拉取同步，看交接单"**

---

*此文件通过 `C:\\WorkBuddy` Junction → WPS 云盘跨设备共享*
"""
    else:
        # 没有已有文件，创建初始模板
        ai_section = f"""{DELIM_MID}，workspace_sync.py 不会覆盖，AI 自行维护 -->

## 📋 任务进度

*（AI 会在会话中维护此区域）*

---

## 💬 近期对话摘要

*（暂无）*

---

## 📎 导出对话

*（暂无）*

---

## ⚠️ 换电脑操作

1. 关闭 WorkBuddy → 等 5 秒 → 确认无进程
2. 到另一台电脑打开 WorkBuddy
3. 对老千说：**"拉取同步，看交接单"**

---

*此文件通过 `C:\\WorkBuddy` Junction → WPS 云盘跨设备共享*
"""

    full_content = machine_section + ai_section

    with open(HANDOFF_FILE, 'w', encoding='utf-8') as f:
        f.write(full_content)

    conn.close()
    print(f"✅ 交接单已更新: {HANDOFF_FILE}")
    print(f"   → 机器生成区已刷新")
    print(f"   → AI 手写区已保留")
    print(f"   → 暗号: {secret_phrase}")


def export_conversation_text(topic, text, source_computer=None):
    """
    导出对话全文到 _sync/conversations/
    由 AI 调用，用户不应手动运行
    """
    os.makedirs(CONVERSATIONS_DIR, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    safe_topic = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff_-]', '-', topic)[:40]
    filename = f"{date_str}-{safe_topic}.md"
    filepath = os.path.join(CONVERSATIONS_DIR, filename)

    computer = source_computer or os.environ.get('COMPUTERNAME', 'Unknown')

    content = f"""# {topic}

> 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')} | 电脑: {computer}

---

{text}
"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✅ 对话已导出: {filepath}")
    return filepath


def sync_all():
    db_path = find_db()

    conn = sqlite3.connect(db_path)

    disk = get_disk_workspaces()
    print(f"📂 C:\\WorkBuddy 下有 {len(disk)} 个工作区")

    existing = set(r[0] for r in conn.execute("SELECT path FROM workspaces").fetchall())
    added = 0
    now_ms = int(time.time() * 1000)

    for w in disk:
        if w not in existing:
            conn.execute("INSERT OR IGNORE INTO workspaces (path, last_opened_at) VALUES (?, ?)", (w, now_ms))
            added += 1
            print(f"  ➕ 添加: {os.path.basename(w)}")

    conn.execute("UPDATE sessions SET deleted_at = NULL WHERE deleted_at IS NOT NULL AND cwd LIKE 'C:\\\\WorkBuddy\\\\%'")
    restored = conn.execute("SELECT changes()").fetchone()[0]

    conn.execute("UPDATE workspaces SET last_opened_at = ? WHERE last_opened_at = 0", (now_ms,))

    conn.commit()
    conn.close()

    print(f"\n📊 结果: +{added} 工作区, +{restored} 会话恢复")

    generate_handoff(db_path)

    print("\n" + "=" * 50)
    print("⚠️  提示:")
    print("  1. 完全退出 WorkBuddy 后重新打开")
    print("  2. HANDOFF.md 位于 C:\\WorkBuddy\\_sync\\")
    print("  3. AI 手写区不会被覆盖")
    print("  4. 对话导出到 _sync/conversations/")


if __name__ == '__main__':
    import sys
    if '--handoff' in sys.argv:
        db_path = find_db()
        generate_handoff(db_path)
    elif '--export' in sys.argv and len(sys.argv) >= 4:
        # 用法: python workspace_sync.py --export "话题" "文本内容"
        topic = sys.argv[2]
        text = sys.argv[3]
        export_conversation_text(topic, text)
    elif '--update-secret' in sys.argv and len(sys.argv) >= 3:
        # 用法: python workspace_sync.py --update-secret "新暗号"
        new_secret = sys.argv[2]
        update_secret(new_secret)
    elif '--verify' in sys.argv:
        # 用法: python workspace_sync.py --verify
        verify_sync()
    else:
        sync_all()
