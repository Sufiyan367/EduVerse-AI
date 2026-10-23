# ==============================================================================
# EduVerse AI — Graceful Shutdown Script (Hardened Process Safety)
# Stops ONLY application-owned EduVerse processes. Never kills unrelated processes.
# ==============================================================================

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
if (Test-Path (Join-Path $ScriptRoot "data")) {
    $BaseDir = $ScriptRoot
} elseif (Test-Path (Join-Path $ScriptRoot "EduVerse_Foundation_PoC\upstream_quicklearn\data")) {
    $BaseDir = Join-Path $ScriptRoot "EduVerse_Foundation_PoC\upstream_quicklearn"
} elseif (Test-Path (Join-Path $ScriptRoot "upstream_quicklearn\data")) {
    $BaseDir = Join-Path $ScriptRoot "upstream_quicklearn"
} else {
    $BaseDir = $ScriptRoot
}

$DataDir = Join-Path $BaseDir "data"
$PidFile = Join-Path $DataDir "eduverse.pid"

function Test-IsEduVerseProcess([int]$testPid) {
    if (-not $testPid -or $testPid -le 4) { return $false }
    try {
        $cim = Get-CimInstance Win32_Process -Filter "ProcessId = $testPid" -ErrorAction SilentlyContinue
        if ($cim) {
            $cmd = if ($cim.CommandLine) { $cim.CommandLine.ToLower() } else { "" }
            $exe = if ($cim.ExecutablePath) { $cim.ExecutablePath.ToLower() } else { "" }
            if ($cmd -match "quicklearn" -or $cmd -match "eduverse" -or $exe -match "eduverse") {
                return $true
            }
        }
    } catch {}
    return $false
}

$stopped = $false

# 1. Stop via recorded PID (with ownership verification)
if (Test-Path $PidFile) {
    $rawPid = Get-Content $PidFile -ErrorAction SilentlyContinue
    if ($rawPid) {
        $targetPid = [int]($rawPid.ToString().Trim())
        if (Test-IsEduVerseProcess $targetPid) {
            Write-Host "[STOP] Stopping verified EduVerse AI process (PID: $targetPid)..." -ForegroundColor Cyan
            Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
            $stopped = $true
        } else {
            $existing = Get-Process -Id $targetPid -ErrorAction SilentlyContinue
            if ($existing) {
                Write-Host "[WARN] Stale PID $targetPid belongs to unrelated process ($($existing.ProcessName)). Skipping termination." -ForegroundColor Yellow
            }
        }
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

# 2. Check if port 8080 is still held by an EduVerse process
$conns = Get-NetTCPConnection -State Listen -LocalPort 8080 -ErrorAction SilentlyContinue
if ($conns) {
    foreach ($conn in $conns) {
        $portPid = $conn.OwningProcess
        if (Test-IsEduVerseProcess $portPid) {
            Write-Host "[STOP] Freeing port 8080 (verified EduVerse PID: $portPid)..." -ForegroundColor Cyan
            Stop-Process -Id $portPid -Force -ErrorAction SilentlyContinue
            $stopped = $true
        } else {
            $p = Get-Process -Id $portPid -ErrorAction SilentlyContinue
            Write-Host "[WARN] Port 8080 is held by an unrelated process (PID: $portPid, Name: $($p.ProcessName)). Skipping termination." -ForegroundColor Yellow
        }
    }
}

if ($stopped) {
    Start-Sleep -Milliseconds 500
    Write-Host "[SUCCESS] EduVerse AI server stopped cleanly." -ForegroundColor Green
} else {
    Write-Host "[INFO] EduVerse AI server was not running." -ForegroundColor Gray
}
