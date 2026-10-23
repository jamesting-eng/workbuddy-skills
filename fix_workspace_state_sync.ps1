# fix_workspace_state_sync.ps1
# Turns workspace-state.json into a symlink pointing at the WPS cloud drive.
# Run once on EACH computer (home and office).

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  workspace-state.json Sync Fix" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$local = "$env:USERPROFILE\.workbuddy\workspace-state.json"
# NOTE: "WPS云盘" below is the literal cloud-drive folder name created by
# WPS Office on Chinese-locale systems -- functional, do not translate.
$wps   = "$env:USERPROFILE\Documents\WPSDrive\123456789\WPS云盘\.workbuddy\workspace-state.json"

# 1. Skip if it is already a symlink
$item = Get-Item $local -Force -ErrorAction SilentlyContinue
if ($item.LinkType -eq "SymbolicLink") {
    Write-Host "[SKIP] workspace-state.json is already a symlink" -ForegroundColor Green
    Write-Host "  Target: $($item.Target)" -ForegroundColor Gray
    exit 0
}

Write-Host "[1/4] Backing up the local file..." -ForegroundColor Yellow
Copy-Item $local "$local.local.bak" -Force
Write-Host "  Backed up to: $local.local.bak" -ForegroundColor Gray

Write-Host "[2/4] Copying to the WPS cloud drive..." -ForegroundColor Yellow
Copy-Item $local $wps -Force -ErrorAction SilentlyContinue
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $wps)) {
    Write-Host "  Warning: cloud-drive file locked; removing and retrying..." -ForegroundColor Yellow
    # The WPS sync process may hold a lock; wait briefly and retry
    Start-Sleep -Seconds 2
    Copy-Item $local $wps -Force
}
Write-Host "  Copied to the WPS cloud drive" -ForegroundColor Gray

Write-Host "[3/4] Removing the local file..." -ForegroundColor Yellow
Remove-Item $local -Force
Write-Host "  Local file removed" -ForegroundColor Gray

Write-Host "[4/4] Creating the symlink..." -ForegroundColor Yellow
New-Item -ItemType SymbolicLink -Path $local -Target $wps -Force | Out-Null
Write-Host "  Symlink created" -ForegroundColor Gray

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Fix complete!" -ForegroundColor Green
Write-Host "  workspace-state.json -> WPS cloud drive" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
