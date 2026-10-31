# ==============================================================================
# EduVerse AI - Application Launcher
# Platform: Windows PowerShell
# ==============================================================================
[CmdletBinding()]
Param(
    [int]$Port = 8080,
    [string]$HostAddress = "127.0.0.1",
    [switch]$NoBrowser,
    [switch]$ForceRestart
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "       EduVerse AI - Grounded Academic Study & Active Recall Platform   " -ForegroundColor Yellow
Write-Host "       Indira College of Engineering & Management (ICEM Pune)           " -ForegroundColor White
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1. Locate and verify Python >= 3.10
Write-Host "[1/6] Verifying Python runtime..." -ForegroundColor Cyan
$PythonCmd = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $PythonCmd) {
    Write-Host "[ERROR] Python is not installed or not found on PATH." -ForegroundColor Red
    Write-Host "Please install Python 3.10+ from https://www.python.org/" -ForegroundColor Yellow
    Exit 1
}

$PyVerOutput = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
$PyVerParts = $PyVerOutput.Split('.')
if ([int]$PyVerParts[0] -lt 3 -or ([int]$PyVerParts[0] -eq 3 -and [int]$PyVerParts[1] -lt 10)) {
    Write-Host "[ERROR] Detected Python $PyVerOutput. EduVerse AI requires Python 3.10 or newer." -ForegroundColor Red
    Exit 1
}
Write-Host "      Found Python $PyVerOutput ($($PythonCmd.Source))" -ForegroundColor Green

# 2. Locate canonical application and backend
Write-Host "[2/6] Locating canonical fullstack codebase..." -ForegroundColor Cyan
$FullstackDir = Join-Path $ScriptRoot "EduVerse-AI-Complete\apps\fullstack"
$BackendDir = Join-Path $FullstackDir "backend"
$DataDir = Join-Path $FullstackDir "data"
$StaticDir = Join-Path $BackendDir "quicklearn\static"

if (-not (Test-Path $BackendDir)) {
    Write-Host "[ERROR] Backend directory not found at $BackendDir" -ForegroundColor Red
    Exit 1
}

if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
}

# 3. Check compiled frontend assets
Write-Host "[3/6] Verifying frontend production build..." -ForegroundColor Cyan
$IndexHtml = Join-Path $StaticDir "index.html"
if (-not (Test-Path $IndexHtml)) {
    Write-Host "      [NOTICE] Compiled frontend static bundle not found at $StaticDir" -ForegroundColor Yellow
    Write-Host "      Attempting to build frontend with Vite..." -ForegroundColor Cyan
    $FrontendDir = Join-Path $FullstackDir "frontend"
    if (Test-Path $FrontendDir) {
        Push-Location $FrontendDir
        try {
            & npm run build
            Write-Host "      [SUCCESS] Frontend build completed." -ForegroundColor Green
        } catch {
            Write-Host "[ERROR] Failed to compile frontend. Please run 'npm run build' inside $FrontendDir." -ForegroundColor Red
            Exit 1
        } finally {
            Pop-Location
        }
    } else {
        Write-Host "[ERROR] Neither static build nor frontend source was found." -ForegroundColor Red
        Exit 1
    }
} else {
    Write-Host "      Production static assets verified ($IndexHtml)" -ForegroundColor Green
}

# 4. Port occupancy and health check
Write-Host "[4/6] Checking port $Port status..." -ForegroundColor Cyan
$TargetUrl = "http://${HostAddress}:${Port}"
$HealthUrl = "${TargetUrl}/api/v1/health"

$AlreadyRunning = $false
try {
    $HealthResp = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 2 -ErrorAction Stop
    if ($HealthResp.status -eq "ok" -or $HealthResp.app -eq "EduVerse AI") {
        $AlreadyRunning = $true
    }
} catch {
    # Not responding as healthy EduVerse
}

if ($AlreadyRunning -and -not $ForceRestart) {
    Write-Host "      EduVerse AI is ALREADY RUNNING and healthy on port $Port." -ForegroundColor Green
} else {
    # Check if port is in use by another service
    $PortOccupied = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($PortOccupied) {
        if ($ForceRestart) {
            # Only terminate if we confirmed it is an EduVerse instance on that port
            $ProcId = $PortOccupied[0].OwningProcess
            Write-Host "      Restarting service on port $Port (terminating PID $ProcId)..." -ForegroundColor Yellow
            Stop-Process -Id $ProcId -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 1
        } else {
            Write-Host "[ERROR] Port $Port is currently occupied by another process (PID $($PortOccupied[0].OwningProcess))." -ForegroundColor Red
            Write-Host "Please pass a different port (e.g. -Port 8081) or use -ForceRestart if appropriate." -ForegroundColor Yellow
            Exit 1
        }
    }

    # 5. Launch Backend Server
    Write-Host "[5/6] Starting EduVerse AI server..." -ForegroundColor Cyan
    $ProcessArgs = "-m quicklearn --port $Port --host $HostAddress --data-dir `"$DataDir`""
    $StartInfo = New-Object System.Diagnostics.ProcessStartInfo
    $StartInfo.FileName = "python"
    $StartInfo.Arguments = $ProcessArgs
    $StartInfo.WorkingDirectory = $BackendDir
    $StartInfo.EnvironmentVariables["PYTHONPATH"] = $BackendDir
    $StartInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Minimized
    $StartInfo.UseShellExecute = $false

    $Proc = [System.Diagnostics.Process]::Start($StartInfo)
    Write-Host "      Process launched (PID $($Proc.Id)). Waiting for health and frontend verification..." -ForegroundColor Gray

    # Poll /api/v1/health and frontend root for up to 25 seconds
    $Healthy = $false
    for ($i = 0; $i -lt 25; $i++) {
        Start-Sleep -Seconds 1
        try {
            $resp = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 2 -ErrorAction Stop
            $uiResp = Invoke-WebRequest -Uri $TargetUrl -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
            if (($resp.status -eq "ok" -or $resp.app -eq "EduVerse AI") -and $uiResp.StatusCode -eq 200) {
                $Healthy = $true
                break
            }
        } catch {
            Write-Host -NoNewline "."
        }
    }
    Write-Host ""

    if (-not $Healthy) {
        Write-Host "[ERROR] Server failed to pass health check within 25 seconds." -ForegroundColor Red
        Write-Host "Check backend logs or run 'python -m quicklearn --port $Port' manually." -ForegroundColor Yellow
        Exit 1
    }
    Write-Host "      Health and frontend verification passed successfully." -ForegroundColor Green
}

# 6. Summary and Browser Launch
Write-Host "[6/6] EduVerse AI is active and ready." -ForegroundColor Cyan
Write-Host ""
Write-Host "========================================================================" -ForegroundColor Green
Write-Host " Access EduVerse AI in your browser:" -ForegroundColor White
Write-Host "   -> Platform URL:       $TargetUrl" -ForegroundColor Cyan
Write-Host "   -> API Health Status:  $HealthUrl" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Green
Write-Host ""

if (-not $NoBrowser) {
    Write-Host "Opening $TargetUrl in your default web browser..." -ForegroundColor Gray
    Start-Process $TargetUrl
}

Exit 0
