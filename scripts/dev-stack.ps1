param(
  [int]$FrontendPort = 5173,
  [int]$BackendPort = 8000,
  [switch]$OpenBrowser
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Test-HttpHealth([string]$Url) {
  try {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
    return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
  } catch {
    return $false
  }
}

function Wait-ForHealth([string]$Name, [string]$Url, [int]$TimeoutSeconds = 45) {
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    if (Test-HttpHealth $Url) {
      Write-Host "$Name is healthy: $Url" -ForegroundColor Green
      return
    }
    Start-Sleep -Milliseconds 500
  } while ((Get-Date) -lt $deadline)
  throw "$Name did not become healthy within $TimeoutSeconds seconds: $Url"
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw 'npm was not found. Install Node.js 18+.'
}
$pythonExecutable = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
  try {
    $candidate = (& py -3 -c "import sys; print(sys.executable)" 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -eq 0 -and $candidate) { $pythonExecutable = $candidate }
  } catch {
    # Some Windows installs expose py.exe as an App Execution Alias that cannot
    # be launched; use the regular Python command below in that case.
  }
}
if (-not $pythonExecutable -and (Get-Command python -ErrorAction SilentlyContinue)) {
  try {
    $candidate = (& python -c "import sys; print(sys.executable)" 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -eq 0 -and $candidate) { $pythonExecutable = $candidate }
  } catch {
    throw 'Python could not be launched. Install Python 3.11+ and ensure python.exe is on PATH.'
  }
}
if (-not $pythonExecutable) { throw 'Python 3.11+ was not found. Install Python and enable python.exe or the py launcher.' }
if (-not (Test-Path $pythonExecutable)) { throw "Could not resolve Python executable: $pythonExecutable" }

$backend = $null
$frontend = $null
$ownsBackend = $false
$ownsFrontend = $false

try {
  if (-not (Test-HttpHealth "http://127.0.0.1:$BackendPort/api/health")) {
    $backend = Start-Process -FilePath $pythonExecutable -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',$BackendPort,'--app-dir','backend') -WorkingDirectory $ProjectRoot -PassThru
    $ownsBackend = $true
  } else {
    Write-Host "Backend already healthy; reusing it." -ForegroundColor DarkCyan
  }
  if (-not (Test-HttpHealth "http://127.0.0.1:$FrontendPort/")) {
    $frontend = Start-Process -FilePath 'npm.cmd' -ArgumentList @('run','dev:frontend','--','--host','127.0.0.1','--port',$FrontendPort) -WorkingDirectory $ProjectRoot -PassThru
    $ownsFrontend = $true
  } else {
    Write-Host "Frontend already healthy; reusing it." -ForegroundColor DarkCyan
  }
  Wait-ForHealth 'Backend' "http://127.0.0.1:$BackendPort/api/health"
  Wait-ForHealth 'Frontend' "http://127.0.0.1:$FrontendPort/"
  Write-Host "AquaSense is ready at http://127.0.0.1:$FrontendPort/" -ForegroundColor Cyan
  Write-Host "API health: http://127.0.0.1:$BackendPort/api/health" -ForegroundColor Cyan
  Write-Host 'Press Ctrl+C to stop both services.' -ForegroundColor Yellow
  if ($OpenBrowser) { Start-Process "http://127.0.0.1:$FrontendPort/" }

  while ($true) {
    if ($ownsBackend -and $backend.HasExited) { throw "Backend exited with code $($backend.ExitCode)." }
    if ($ownsFrontend -and $frontend.HasExited) { throw "Frontend exited with code $($frontend.ExitCode)." }
    if (-not (Test-HttpHealth "http://127.0.0.1:$BackendPort/api/health")) { throw 'Backend health check failed.' }
    if (-not (Test-HttpHealth "http://127.0.0.1:$FrontendPort/")) { throw 'Frontend health check failed.' }
    Start-Sleep -Seconds 5
  }
} finally {
  foreach ($process in @($frontend, $backend)) {
    if ($null -ne $process -and -not $process.HasExited -and (($process.Id -eq $backend.Id -and $ownsBackend) -or ($process.Id -eq $frontend.Id -and $ownsFrontend))) {
      Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
  }
}

