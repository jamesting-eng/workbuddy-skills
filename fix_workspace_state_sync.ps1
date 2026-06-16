# fix_workspace_state_sync.ps1
# 把 workspace-state.json 改为符号链接指向 WPS 云盘
# 家里电脑和公司电脑都需要运行一次

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  workspace-state.json 同步修复" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$local = "$env:USERPROFILE\.workbuddy\workspace-state.json"
$wps   = "$env:USERPROFILE\Documents\WPSDrive\358659758\WPS云盘\.workbuddy\workspace-state.json"

# 1. 检查是否已经是符号链接
$item = Get-Item $local -Force -ErrorAction SilentlyContinue
if ($item.LinkType -eq "SymbolicLink") {
    Write-Host "[跳过] workspace-state.json 已经是符号链接" -ForegroundColor Green
    Write-Host "  指向: $($item.Target)" -ForegroundColor Gray
    exit 0
}

Write-Host "[1/4] 备份本地文件..." -ForegroundColor Yellow
Copy-Item $local "$local.local.bak" -Force
Write-Host "  备份到: $local.local.bak" -ForegroundColor Gray

Write-Host "[2/4] 复制到 WPS 云盘..." -ForegroundColor Yellow
Copy-Item $local $wps -Force -ErrorAction SilentlyContinue
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $wps)) {
    Write-Host "  警告：WPS 云盘文件被锁定，使用 Remove-Item 后重试..." -ForegroundColor Yellow
    # 可能被 WPS 同步进程锁定，稍等再试
    Start-Sleep -Seconds 2
    Copy-Item $local $wps -Force
}
Write-Host "  已复制到 WPS 云盘" -ForegroundColor Gray

Write-Host "[3/4] 删除本地文件..." -ForegroundColor Yellow
Remove-Item $local -Force
Write-Host "  已删除本地文件" -ForegroundColor Gray

Write-Host "[4/4] 创建符号链接..." -ForegroundColor Yellow
New-Item -ItemType SymbolicLink -Path $local -Target $wps -Force | Out-Null
Write-Host "  符号链接已创建" -ForegroundColor Gray

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  修复完成！" -ForegroundColor Green
Write-Host "  workspace-state.json -> WPS 云盘" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
