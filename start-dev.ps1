param(
    [switch]$ForceRestart
)

$ErrorActionPreference = "Stop"

function Get-PortListener {
    param([int]$Port)

    try {
        return Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop |
            Select-Object -First 1
    } catch {
        return $null
    }
}

function Stop-ListenerIfRequested {
    param(
        [int]$Port,
        [string]$Name
    )

    $listener = Get-PortListener -Port $Port
    if (-not $listener) {
        return
    }

    $process = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
    $processName = if ($process) { $process.ProcessName } else { "PID $($listener.OwningProcess)" }

    if (-not $ForceRestart) {
        throw "$Name cannot start because port $Port is already in use by $processName. Re-run with -ForceRestart or stop that process first."
    }

    if ($process) {
        Stop-Process -Id $process.Id -Force -ErrorAction Stop
        Start-Sleep -Milliseconds 500
    } else {
        throw "$Name cannot start because port $Port is in use by PID $($listener.OwningProcess), and that process could not be resolved."
    }
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontendDir = Join-Path $root "frontend"
$backendDir = Join-Path $root "cv_system_output"
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$logsDir = Join-Path $root "logs"
$backendOut = Join-Path $logsDir "backend.out.log"
$backendErr = Join-Path $logsDir "backend.err.log"
$frontendOut = Join-Path $logsDir "frontend.out.log"
$frontendErr = Join-Path $logsDir "frontend.err.log"
$backendPidFile = Join-Path $logsDir "backend.pid"
$frontendPidFile = Join-Path $logsDir "frontend.pid"

if (-not (Test-Path $frontendDir)) {
    throw "Frontend directory not found: $frontendDir"
}

if (-not (Test-Path $backendDir)) {
    throw "Backend directory not found: $backendDir"
}

if (-not (Test-Path $venvPython)) {
    throw "Python virtual environment not found at $venvPython"
}

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

Stop-ListenerIfRequested -Port 8000 -Name "Backend"
Stop-ListenerIfRequested -Port 3000 -Name "Frontend"

Remove-Item -LiteralPath $backendOut, $backendErr, $frontendOut, $frontendErr -ErrorAction SilentlyContinue

$backendProcess = Start-Process `
    -FilePath $venvPython `
    -ArgumentList "main.py" `
    -WorkingDirectory $backendDir `
    -RedirectStandardOutput $backendOut `
    -RedirectStandardError $backendErr `
    -PassThru

$frontendProcess = Start-Process `
    -FilePath "npm.cmd" `
    -ArgumentList "run", "dev", "--", "--port", "3000" `
    -WorkingDirectory $frontendDir `
    -RedirectStandardOutput $frontendOut `
    -RedirectStandardError $frontendErr `
    -PassThru

Set-Content -Path $backendPidFile -Value $backendProcess.Id
Set-Content -Path $frontendPidFile -Value $frontendProcess.Id

Write-Host "Backend starting at http://127.0.0.1:8000 (PID $($backendProcess.Id))"
Write-Host "Frontend starting at http://127.0.0.1:3000 (PID $($frontendProcess.Id))"
Write-Host "Logs:"
Write-Host "  Backend stdout: $backendOut"
Write-Host "  Backend stderr: $backendErr"
Write-Host "  Frontend stdout: $frontendOut"
Write-Host "  Frontend stderr: $frontendErr"
Write-Host ""
Write-Host "If ports are already busy, run: .\start-dev.ps1 -ForceRestart"
