# EduVerse AI - Unified Launcher Script
Param(
    [int]$Port = 8080,
    [string]$HostAddress = "127.0.0.1",
    [switch]$NoBrowser
)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "         EduVerse AI - Intelligent Study Platform         " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Python) {
    Write-Host "[ERROR] Python 3 not found on PATH. Please install Python." -ForegroundColor Red
    Exit 1
}

$Existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($Existing) {
    Write-Host "[OK] EduVerse AI is ALREADY running on http://$HostAddress`:$Port" -ForegroundColor Green
} else {
    Write-Host "[*] Starting EduVerse AI Platform on http://$HostAddress`:$Port..." -ForegroundColor Cyan
    $FsPath = Join-Path $Root "EduVerse-AI-Complete\apps\fullstack"
    $FsData = Join-Path $FsPath "data"
    $FsBackend = Join-Path $FsPath "backend"
    
    if (-not (Test-Path $FsData)) {
        New-Item -ItemType Directory -Path $FsData -Force | Out-Null
    }
    
    $env:PYTHONPATH = "$FsBackend;$env:PYTHONPATH"
    Start-Process -FilePath "python" -ArgumentList "-m quicklearn --port $Port --host $HostAddress --data-dir `"$FsData`"" -WorkingDirectory $FsBackend -WindowStyle Minimized
    Start-Sleep -Seconds 3
    Write-Host "[SUCCESS] EduVerse AI running: http://$HostAddress`:$Port" -ForegroundColor Green
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " EduVerse AI is active and ready:" -ForegroundColor Green
Write-Host "   -> URL:               http://$HostAddress`:$Port" -ForegroundColor White
Write-Host "   -> Default Login:     student@eduverse.ai / demo123" -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Cyan

if (-not $NoBrowser) {
    Start-Process "http://$HostAddress`:$Port"
}
