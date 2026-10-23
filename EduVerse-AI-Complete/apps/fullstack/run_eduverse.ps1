[CmdletBinding()]
param(
    [int]$Port = 8080,
    [string]$HostAddress = "127.0.0.1",
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
if (Test-Path (Join-Path $ScriptRoot "backend")) {
    $PoCRoot = $ScriptRoot
    $BackendDir = Join-Path $ScriptRoot "backend"
} elseif (Test-Path (Join-Path $ScriptRoot "upstream_quicklearn\backend")) {
    $PoCRoot = Join-Path $ScriptRoot "upstream_quicklearn"
    $BackendDir = Join-Path $ScriptRoot "upstream_quicklearn\backend"
} elseif (Test-Path (Join-Path $ScriptRoot "EduVerse_Foundation_PoC\upstream_quicklearn\backend")) {
    $PoCRoot = Join-Path $ScriptRoot "EduVerse_Foundation_PoC\upstream_quicklearn"
    $BackendDir = Join-Path $PoCRoot "backend"
} else {
    $PoCRoot = $ScriptRoot
    $BackendDir = Join-Path $ScriptRoot "backend"
}
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
$DataDir = Join-Path $PoCRoot "data"
$LogsDir = Join-Path $PoCRoot "logs"
$PidFile = Join-Path $DataDir "eduverse.pid"
$LogFile = Join-Path $LogsDir "eduverse.log"
$ErrLog = Join-Path $LogsDir "eduverse_err.log"

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

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "                EduVerse AI -- Launch Assistant                       " -ForegroundColor White
Write-Host "        Indira College of Engineering and Management (ICEM Pune)      " -ForegroundColor DarkCyan
Write-Host "======================================================================" -ForegroundColor Cyan

# 1. Ensure Directories
if (-not (Test-Path $DataDir)) { New-Item -ItemType Directory -Path $DataDir -Force | Out-Null }
if (-not (Test-Path $LogsDir)) { New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null }

# 2. Check Virtual Environment
if (-not (Test-Path $VenvPython)) {
    $FallbackVenv = "S:\SY\SEM 3\MP\EduVerse_Web_Demo\backend\.venv\Scripts\python.exe"
    if (Test-Path $FallbackVenv) {
        $VenvPython = $FallbackVenv
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $VenvPython = (Get-Command python).Source
    } else {
        Write-Host "[ERROR] Virtual environment not found at: $VenvPython" -ForegroundColor Red
        Write-Host "Please ensure backend virtualenv is created and dependencies are installed." -ForegroundColor Yellow
        exit 1
    }
}

# 3. Check for existing running instance on port
$portConn = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if ($portConn) {
    $existingPid = $portConn.OwningProcess[0]
    if (Test-IsEduVerseProcess $existingPid) {
        $existingPid | Set-Content $PidFile -Force
        Write-Host "[INFO] EduVerse AI is already active (PID: $existingPid) on http://$($HostAddress):$($Port)" -ForegroundColor Green
        if (-not $NoBrowser) {
            Start-Process "http://$($HostAddress):$($Port)"
        }
        exit 0
    } else {
        $p = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        Write-Host "[ERROR] Port $Port is occupied by an unrelated process (PID: $existingPid, Name: $($p.ProcessName))." -ForegroundColor Red
        Write-Host "Please stop that application or launch EduVerse AI on an alternative port: .\run_eduverse.ps1 -Port <number>" -ForegroundColor Yellow
        exit 1
    }
}

# 4. Check Local Provider Status
Write-Host "[CHECK] Inspecting local AI providers..." -ForegroundColor Gray
$ollamaRunning = $false
$lmstudioRunning = $false

try {
    $r1 = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 1 -UseBasicParsing -ErrorAction Stop
    if ($r1.StatusCode -eq 200) { $ollamaRunning = $true }
} catch {}

try {
    $r2 = Invoke-WebRequest -Uri "http://localhost:1234/v1/models" -TimeoutSec 1 -UseBasicParsing -ErrorAction Stop
    if ($r2.StatusCode -eq 200) { $lmstudioRunning = $true }
} catch {}

if ($ollamaRunning) {
    Write-Host "  -> Ollama is online at http://localhost:11434" -ForegroundColor Green
} elseif ($lmstudioRunning) {
    Write-Host "  -> LM Studio is online at http://localhost:1234" -ForegroundColor Green
} else {
    Write-Host "  -> Local daemons (Ollama / LM Studio) are offline." -ForegroundColor DarkYellow
    Write-Host "  -> Server will run with configured Settings (Mock AI available for offline demo)." -ForegroundColor Gray
}

# 5. Launch Server Process
Write-Host "[START] Launching EduVerse AI background server..." -ForegroundColor Cyan

$serverArgs = "-m quicklearn --port $Port --host $HostAddress --data-dir `"$DataDir`""

$process = Start-Process `
    -FilePath $VenvPython `
    -ArgumentList $serverArgs `
    -WorkingDirectory $BackendDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput $LogFile `
    -RedirectStandardError $ErrLog `
    -PassThru

# 6. Poll for Readiness
Write-Host "[WAIT] Waiting for application startup..." -NoNewline -ForegroundColor Gray
$ready = $false
$timeoutSec = 25
$startTime = Get-Date

while (((Get-Date) - $startTime).TotalSeconds -lt $timeoutSec) {
    Start-Sleep -Milliseconds 600
    Write-Host "." -NoNewline -ForegroundColor Gray
    try {
        $res = Invoke-RestMethod -Uri "http://$($HostAddress):$($Port)/api/v1/settings" -TimeoutSec 1 -ErrorAction Stop
        if ($res.settings) {
            $ready = $true
            break
        }
    } catch {}
}
Write-Host ""

if ($ready) {
    # Record actual listening PID
    $conn = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if ($conn) {
        $conn.OwningProcess[0] | Set-Content $PidFile -Force
    } else {
        $process.Id | Set-Content $PidFile -Force
    }

    Write-Host "======================================================================" -ForegroundColor Green
    Write-Host "  [SUCCESS] EduVerse AI is active and ready!" -ForegroundColor Green
    Write-Host "  URL:      http://$($HostAddress):$($Port)" -ForegroundColor White
    Write-Host "  Storage:  $DataDir" -ForegroundColor Gray
    Write-Host "  Stop:     Run .\stop_eduverse.ps1 to shutdown gracefully" -ForegroundColor Gray
    Write-Host "======================================================================" -ForegroundColor Green

    if (-not $NoBrowser) {
        Start-Process "http://$($HostAddress):$($Port)"
    }
} else {
    Write-Host "[ERROR] Server failed to respond within $timeoutSec seconds." -ForegroundColor Red
    Write-Host "Review logs at: $LogFile" -ForegroundColor Yellow
    exit 1
}

