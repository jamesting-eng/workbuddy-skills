# ============================================================
# fix_db_isolation_v3.ps1
# 最终修复方案：重建 .workbuddy 目录结构
# 
# 【解决的问题】
# 原来: C:\Users\<user>\.workbuddy ──符号链接──> WPS云盘\.workbuddy\
#   → workbuddy.db 在 WPS 云盘，两台电脑共享，互相覆盖
#
# 修复后: C:\Users\<user>\.workbuddy = 本地真实目录
#   → workbuddy.db 在本地，不被 WPS 云盘同步
#   → 其他子目录通过 junction 指向 WPS 云盘对应目录（继续同步）
#   → 配置文件（settings.json 等）复制到本地
#
# 【用法】关闭 WorkBuddy 后，右键"用 PowerShell 运行"
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  WorkBuddy DB 隔离修复脚本 v3" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── 路径变量 ──────────────────────────────────────────────────
$wpsWb   = "$env:USERPROFILE\Documents\WPSDrive\358659758\WPS云盘\.workbuddy"
$localWb = "$env:USERPROFILE\.workbuddy"
$bakWb   = "$env:USERPROFILE\.workbuddy_old_symlink"

Write-Host "用户:        $env:USERNAME"
Write-Host "WPS 目录:    $wpsWb"
Write-Host "本地目录:    $localWb"
Write-Host ""

# ── 1. 检查 WorkBuddy 是否已关闭 ────────────────────────────
$procs = Get-Process -Name "WorkBuddy" -ErrorAction SilentlyContinue
if ($procs) {
    Write-Host "❌ WorkBuddy 仍在运行！请先完全退出（右键托盘 → 退出）" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}
Write-Host "✅ WorkBuddy 已关闭" -ForegroundColor Green

# ── 2. 检查 WPS 云盘 ─────────────────────────────────────────
if (-not (Test-Path $wpsWb)) {
    Write-Host "❌ 找不到 WPS 云盘目录: $wpsWb" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}
Write-Host "✅ WPS 云盘目录存在" -ForegroundColor Green

# ── 3. WAL 刷盘 ──────────────────────────────────────────────
$wpsDb  = "$wpsWb\workbuddy.db"
$pyPath = "$localWb\binaries\python\versions\3.13.12\python.exe"
if (-not (Test-Path $pyPath)) {
    # localWb 可能是符号链接，binaries 在 WPS 里
    $pyPath = "$wpsWb\binaries\python\versions\3.13.12\python.exe"
}
if ((Test-Path $pyPath) -and (Test-Path $wpsDb)) {
    Write-Host ""
    Write-Host "⚙️  WAL 刷盘..." -ForegroundColor Yellow
    & $pyPath -c "import sqlite3; c=sqlite3.connect(r'$wpsDb'); print('WAL checkpoint:', c.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()); c.close()"
    Write-Host "✅ WAL 刷盘完成" -ForegroundColor Green
}

# ── 4. 删除旧符号链接，创建本地真实目录 ─────────────────────
Write-Host ""
Write-Host "⚙️  重建 .workbuddy 目录结构..." -ForegroundColor Yellow

$wbItem = Get-Item $localWb -Force -ErrorAction SilentlyContinue
if ($wbItem) {
    if ($wbItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        Write-Host "  删除旧符号链接..."
        # Remove-Item 对符号链接目录要用 cmd rmdir
        cmd /c "rmdir `"$localWb`"" | Out-Null
    } else {
        Write-Host "  重命名旧目录为备份..."
        Rename-Item $localWb $bakWb -Force
    }
}

New-Item -ItemType Directory -Path $localWb -Force | Out-Null
Write-Host "  ✅ 本地 .workbuddy 目录已创建" -ForegroundColor Green

# ── 5. 为 WPS 云盘的所有子目录创建 junction ──────────────────
Write-Host ""
Write-Host "⚙️  创建 junction 链接（子目录 → WPS 云盘）..." -ForegroundColor Yellow

$wpsDirs = Get-ChildItem $wpsWb -Directory -Force
$junctionCount = 0
foreach ($dir in $wpsDirs) {
    $localDir = "$localWb\$($dir.Name)"
    $wpsDir   = $dir.FullName
    $result = cmd /c "mklink /J `"$localDir`" `"$wpsDir`"" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✔ $($dir.Name)" -ForegroundColor Gray
        $junctionCount++
    } else {
        Write-Host "  ✘ $($dir.Name): $result" -ForegroundColor Yellow
    }
}
Write-Host "  ✅ 创建了 $junctionCount 个 junction 链接" -ForegroundColor Green

# ── 6. 复制单文件到本地（配置 + db）─────────────────────────
Write-Host ""
Write-Host "⚙️  复制文件到本地..." -ForegroundColor Yellow

$wpsFiles = Get-ChildItem $wpsWb -File -Force
foreach ($f in $wpsFiles) {
    # 跳过 db 文件（稍后单独处理）
    if ($f.Name -match "^workbuddy\.db") { continue }
    $dst = "$localWb\$($f.Name)"
    Copy-Item $f.FullName $dst -Force
    Write-Host "  复制: $($f.Name)" -ForegroundColor Gray
}

# ── 7. 处理 workbuddy.db：放本地，不进 WPS 云盘 ─────────────
Write-Host ""
Write-Host "⚙️  设置本地数据库（不同步）..." -ForegroundColor Yellow

$dbFiles = @("workbuddy.db", "workbuddy.db-wal", "workbuddy.db-shm")
foreach ($dbf in $dbFiles) {
    $src = "$wpsWb\$dbf"
    $dst = "$localWb\$dbf"
    if (Test-Path $src) {
        Copy-Item $src $dst -Force
        Write-Host "  复制: $dbf" -ForegroundColor Gray
    }
}

# 删除 WPS 云盘里的 db（防止被同步到另一台电脑）
Write-Host "  从 WPS 云盘删除 db 文件..."
foreach ($dbf in $dbFiles) {
    Remove-Item "$wpsWb\$dbf" -Force -ErrorAction SilentlyContinue
}
Write-Host "✅ 本地数据库已就绪，WPS 云盘 db 已删除" -ForegroundColor Green

# ── 8. 验证 ──────────────────────────────────────────────────
Write-Host ""
Write-Host "⚙️  验证..." -ForegroundColor Yellow

$newItem  = Get-Item $localWb -Force
$isLink   = [bool]($newItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint)
$dbOk     = Test-Path "$localWb\workbuddy.db"
$dbWpsGone = -not (Test-Path "$wpsWb\workbuddy.db")
$skillsOk  = Test-Path "$localWb\skills"

Write-Host "  .workbuddy 是本地目录（非符号链接）: $(-not $isLink)"  -ForegroundColor $(if (-not $isLink) { "Green" } else { "Red" })
Write-Host "  workbuddy.db 在本地:                 $dbOk"             -ForegroundColor $(if ($dbOk)        { "Green" } else { "Red" })
Write-Host "  WPS 云盘里 db 已删除:                $dbWpsGone"        -ForegroundColor $(if ($dbWpsGone)   { "Green" } else { "Yellow" })
Write-Host "  skills 目录 junction 正常:           $skillsOk"         -ForegroundColor $(if ($skillsOk)    { "Green" } else { "Red" })

# ── 9. 完成 ──────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ✅ 修复完成！" -ForegroundColor Green  
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "说明：" -ForegroundColor White
Write-Host "  - .workbuddy 现在是本地真实目录" -ForegroundColor Gray
Write-Host "  - workbuddy.db 仅在本地，不会被同步覆盖" -ForegroundColor Gray
Write-Host "  - skills/scripts 等通过 junction 继续同步到 WPS 云盘" -ForegroundColor Gray
Write-Host ""
Write-Host "⚠️  家里的电脑也需要运行一次此脚本！" -ForegroundColor Yellow
Write-Host ""
Write-Host "现在可以重新打开 WorkBuddy 了。"
Read-Host "按回车关闭"
