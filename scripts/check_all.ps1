# Runs all project checks in sequence.
# Usage: from the repository root, run `.\scripts\check_all.ps1`.

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$passMark = [System.Char]::ConvertFromUtf32(0x2705)
$failMark = [System.Char]::ConvertFromUtf32(0x274C)
$passWord = -join ([char]0x901A, [char]0x8FC7)
$failWord = -join ([char]0x5931, [char]0x8D25)

$results = [ordered]@{
    "Frontend build" = $false
    "Backend health check" = $false
    "pytest stable entry" = $false
}

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "== $Title =="
}

function Write-Result {
    param(
        [string]$Name,
        [bool]$Passed
    )

    if ($Passed) {
        Write-Host ("{0} {1}: {2}" -f $script:passMark, $script:passWord, $Name)
    } else {
        Write-Host ("{0} {1}: {2}" -f $script:failMark, $script:failWord, $Name)
    }
}

function Test-PortReady {
    param(
        [string]$HostName,
        [int]$Port,
        [int]$TimeoutMs = 500
    )

    $client = $null
    try {
        $client = [System.Net.Sockets.TcpClient]::new()
        $task = $client.ConnectAsync($HostName, $Port)
        if (-not $task.Wait($TimeoutMs)) {
            return $false
        }
        return $client.Connected
    } catch {
        return $false
    } finally {
        if ($null -ne $client) {
            $client.Dispose()
        }
    }
}

function Stop-ProcessTree {
    param([int]$ProcessId)

    if ($ProcessId -le 0) {
        return
    }

    & taskkill.exe /PID $ProcessId /T /F | Out-Null
}

Write-Section "1. Frontend build"
$frontendLocationPushed = $false
try {
    Push-Location (Join-Path $repoRoot "frontend")
    $frontendLocationPushed = $true
    & npm run build
    $results["Frontend build"] = ($LASTEXITCODE -eq 0)
} catch {
    Write-Host $_.Exception.Message
    $results["Frontend build"] = $false
} finally {
    if ($frontendLocationPushed) {
        Pop-Location
    }
}
Write-Result "Frontend build" $results["Frontend build"]

Write-Section "2. Backend health check"
$serverProcess = $null
try {
    $logDir = Join-Path $repoRoot "artifacts"
    if (-not (Test-Path -LiteralPath $logDir)) {
        New-Item -ItemType Directory -Path $logDir | Out-Null
    }

    $stdoutLog = Join-Path $logDir "check_all_server.out.log"
    $stderrLog = Join-Path $logDir "check_all_server.err.log"
    $serverProcess = Start-Process `
        -FilePath "python" `
        -ArgumentList @("server.py") `
        -WorkingDirectory $repoRoot `
        -PassThru `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog

    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        if ($serverProcess.HasExited) {
            break
        }
        if (Test-PortReady -HostName "localhost" -Port 8502 -TimeoutMs 500) {
            $ready = $true
            break
        }
        Start-Sleep -Seconds 1
    }

    if ($ready -and -not $serverProcess.HasExited) {
        $response = Invoke-WebRequest -Uri "http://localhost:8502/api/health" -UseBasicParsing -TimeoutSec 5
        $results["Backend health check"] = ($response.StatusCode -eq 200)
    } else {
        Write-Host "Port 8502 was not ready before the server process exited or timed out."
        $results["Backend health check"] = $false
    }
} catch {
    Write-Host $_.Exception.Message
    $results["Backend health check"] = $false
} finally {
    if ($null -ne $serverProcess) {
        Stop-ProcessTree -ProcessId $serverProcess.Id
        Wait-Process -Id $serverProcess.Id -Timeout 10 -ErrorAction SilentlyContinue
    }
}
Write-Result "Backend health check" $results["Backend health check"]

Write-Section "3. pytest stable entry"
$pytestLocationPushed = $false
try {
    Push-Location $repoRoot
    $pytestLocationPushed = $true
    & (Join-Path $scriptDir "pytest_stable.ps1")
    $results["pytest stable entry"] = ($LASTEXITCODE -eq 0)
} catch {
    Write-Host $_.Exception.Message
    $results["pytest stable entry"] = $false
} finally {
    if ($pytestLocationPushed) {
        Pop-Location
    }
}
Write-Result "pytest stable entry" $results["pytest stable entry"]

Write-Section "Summary"
$allPassed = $true
foreach ($name in $results.Keys) {
    Write-Result $name $results[$name]
    if (-not $results[$name]) {
        $allPassed = $false
    }
}

if ($allPassed) {
    exit 0
}
exit 1
