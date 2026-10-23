# ============================================================
# fix_db_isolation_v3.ps1
# Definitive fix: rebuild the .workbuddy directory layout
#
# [Problem solved]
# Before: C:\Users\<user>\.workbuddy --symlink--> WPS cloud drive\.workbuddy\
#   -> workbuddy.db lives on the WPS cloud drive, shared by both
#      computers, overwriting each other
#
# After: C:\Users\<user>\.workbuddy = a real local directory
#   -> workbuddy.db stays local, never synced by the WPS cloud drive
#   -> other subdirectories become junctions pointing at the matching
#      cloud-drive directories (still synced)
#   -> config files (settings.json etc.) are copied local
#
# [Usage] Close WorkBuddy first, then right-click -> "Run with PowerShell"
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  WorkBuddy DB Isolation Fix v3" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# -- Path variables -------------------------------------------
# NOTE: "WPS云盘" below is the literal cloud-drive folder name created by
# WPS Office on Chinese-locale systems -- functional, do not translate.
$wpsWb   = "$env:USERPROFILE\Documents\WPSDrive\123456789\WPS云盘\.workbuddy"
$localWb = "$env:USERPROFILE\.workbuddy"
$bakWb   = "$env:USERPROFILE\.workbuddy_old_symlink"

Write-Host "User:         $env:USERNAME"
Write-Host "WPS dir:      $wpsWb"
Write-Host "Local dir:    $localWb"
Write-Host ""

# -- 1. Check WorkBuddy is closed ------------------------------
$procs = Get-Process -Name "WorkBuddy" -ErrorAction SilentlyContinue
if ($procs) {
    Write-Host "[X] WorkBuddy is still running! Quit it fully first (tray icon -> Exit)" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "[OK] WorkBuddy is closed" -ForegroundColor Green

# -- 2. Check the WPS cloud drive ------------------------------
if (-not (Test-Path $wpsWb)) {
    Write-Host "[X] WPS cloud-drive directory not found: $wpsWb" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "[OK] WPS cloud-drive directory exists" -ForegroundColor Green

# -- 3. WAL checkpoint -----------------------------------------
$wpsDb  = "$wpsWb\workbuddy.db"
$pyPath = "$localWb\binaries\python\versions\3.13.12\python.exe"
if (-not (Test-Path $pyPath)) {
    # localWb may still be a symlink; binaries may live inside the WPS tree
    $pyPath = "$wpsWb\binaries\python\versions\3.13.12\python.exe"
}
if ((Test-Path $pyPath) -and (Test-Path $wpsDb)) {
    Write-Host ""
    Write-Host "[..] WAL checkpoint..." -ForegroundColor Yellow
    & $pyPath -c "import sqlite3; c=sqlite3.connect(r'$wpsDb'); print('WAL checkpoint:', c.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()); c.close()"
    Write-Host "[OK] WAL checkpoint done" -ForegroundColor Green
}

# -- 4. Remove the old symlink, create a real local directory --
Write-Host ""
Write-Host "[..] Rebuilding .workbuddy directory layout..." -ForegroundColor Yellow

$wbItem = Get-Item $localWb -Force -ErrorAction SilentlyContinue
if ($wbItem) {
    if ($wbItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        Write-Host "  Removing old symlink..."
        # Remove-Item cannot delete symlinked dirs; use cmd rmdir instead
        cmd /c "rmdir `"$localWb`"" | Out-Null
    } else {
        Write-Host "  Renaming old directory as backup..."
        Rename-Item $localWb $bakWb -Force
    }
}

New-Item -ItemType Directory -Path $localWb -Force | Out-Null
Write-Host "  [OK] Local .workbuddy directory created" -ForegroundColor Green

# -- 5. Junction every cloud-drive subdirectory ----------------
Write-Host ""
Write-Host "[..] Creating junctions (subdirs -> WPS cloud drive)..." -ForegroundColor Yellow

$wpsDirs = Get-ChildItem $wpsWb -Directory -Force
$junctionCount = 0
foreach ($dir in $wpsDirs) {
    $localDir = "$localWb\$($dir.Name)"
    $wpsDir   = $dir.FullName
    $result = cmd /c "mklink /J `"$localDir`" `"$wpsDir`"" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [+] $($dir.Name)" -ForegroundColor Gray
        $junctionCount++
    } else {
        Write-Host "  [!] $($dir.Name): $result" -ForegroundColor Yellow
    }
}
Write-Host "  [OK] Created $junctionCount junctions" -ForegroundColor Green

# -- 6. Copy single files local (config + db) ------------------
Write-Host ""
Write-Host "[..] Copying files local..." -ForegroundColor Yellow

$wpsFiles = Get-ChildItem $wpsWb -File -Force
foreach ($f in $wpsFiles) {
    # Skip db files (handled separately below)
    if ($f.Name -match "^workbuddy\.db") { continue }
    $dst = "$localWb\$($f.Name)"
    Copy-Item $f.FullName $dst -Force
    Write-Host "  Copied: $($f.Name)" -ForegroundColor Gray
}

# -- 7. workbuddy.db: keep local, out of the cloud drive -------
Write-Host ""
Write-Host "[..] Setting up the local database (not synced)..." -ForegroundColor Yellow

$dbFiles = @("workbuddy.db", "workbuddy.db-wal", "workbuddy.db-shm")
foreach ($dbf in $dbFiles) {
    $src = "$wpsWb\$dbf"
    $dst = "$localWb\$dbf"
    if (Test-Path $src) {
        Copy-Item $src $dst -Force
        Write-Host "  Copied: $dbf" -ForegroundColor Gray
    }
}

# Delete the db copies inside the cloud drive (prevents them being
# synced onto the other computer)
Write-Host "  Removing db files from the WPS cloud drive..."
foreach ($dbf in $dbFiles) {
    Remove-Item "$wpsWb\$dbf" -Force -ErrorAction SilentlyContinue
}
Write-Host "[OK] Local database ready; cloud-drive db removed" -ForegroundColor Green

# -- 8. Verify -------------------------------------------------
Write-Host ""
Write-Host "[..] Verifying..." -ForegroundColor Yellow

$newItem  = Get-Item $localWb -Force
$isLink   = [bool]($newItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint)
$dbOk     = Test-Path "$localWb\workbuddy.db"
$dbWpsGone = -not (Test-Path "$wpsWb\workbuddy.db")
$skillsOk  = Test-Path "$localWb\skills"

Write-Host "  .workbuddy is a local dir (not a symlink): $(-not $isLink)" -ForegroundColor $(if (-not $isLink) { "Green" } else { "Red" })
Write-Host "  workbuddy.db is local:                     $dbOk"    -ForegroundColor $(if ($dbOk)      { "Green" } else { "Red" })
Write-Host "  cloud-drive db removed:                    $dbWpsGone" -ForegroundColor $(if ($dbWpsGone) { "Green" } else { "Yellow" })
Write-Host "  skills junction healthy:                   $skillsOk" -ForegroundColor $(if ($skillsOk)  { "Green" } else { "Red" })

# -- 9. Done ---------------------------------------------------
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  [OK] Fix complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Summary:" -ForegroundColor White
Write-Host "  - .workbuddy is now a real local directory" -ForegroundColor Gray
Write-Host "  - workbuddy.db stays local and is never overwritten by sync" -ForegroundColor Gray
Write-Host "  - skills/scripts etc. keep syncing via junctions into the WPS cloud drive" -ForegroundColor Gray
Write-Host ""
Write-Host "[!] You must also run this script once on the other computer!" -ForegroundColor Yellow
Write-Host ""
Write-Host "You can reopen WorkBuddy now."
Read-Host "Press Enter to close"
