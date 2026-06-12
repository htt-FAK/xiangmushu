# Auto-cleanup port 8502 before starting server
$port = 8502
Write-Host "Checking port $port..." -ForegroundColor Cyan

$serverPid = (netstat -ano | Select-String ":$port" | Where-Object {
    $_.Line -match "\sLISTENING\s"
} | ForEach-Object {
    $_.Line.Trim() -split '\s+' | Select-Object -Last 1
}) | Select-Object -First 1

if ($serverPid) {
    Write-Host "Port $port is in use by PID $serverPid. Terminating..." -ForegroundColor Yellow
    taskkill /F /PID $serverPid 2>$null
    Start-Sleep -Seconds 1
    Write-Host "Port $port released." -ForegroundColor Green
} else {
    Write-Host "Port $port is free." -ForegroundColor Green
}

Write-Host "Starting server on port $port..." -ForegroundColor Cyan
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

& $python "$PSScriptRoot\server.py"
