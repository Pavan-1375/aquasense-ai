param(
  [string]$Endpoint = "https://aquasense-api-production-22173672.up.railway.app/api/ingest/http",
  [string]$DeviceId = "ESP32-001",
  [int]$Baud = 115200,
  [double]$MinInterval = 0.25
)

$ErrorActionPreference = "Stop"
if (-not $env:ESP32_INGEST_KEY) {
  throw "Set ESP32_INGEST_KEY in this PowerShell session before starting the bridge."
}

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
  throw "Python launcher 'py' was not found. Install Python 3.12 and pyserial first."
}

try { py -3 -c "import serial" } catch {
  throw "pyserial is missing. Install it with: py -3 -m pip install pyserial"
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$bridge = Join-Path $repoRoot "backend\bridge\auto_bridge.py"
Write-Host "Watching for ESP32 USB reconnects..."
Write-Host "Endpoint: $Endpoint"
Write-Host "Device: $DeviceId"
py -3 $bridge --endpoint $Endpoint --device-key $env:ESP32_INGEST_KEY --device-id $DeviceId --baud $Baud --min-interval $MinInterval
