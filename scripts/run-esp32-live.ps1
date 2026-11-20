param(
  [string]$DeviceId = "ESP32-001",
  [int]$Baud = 115200
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

Write-Host "AquaSense ESP32 live bridge" -ForegroundColor Cyan
Write-Host "Plug in the ESP32. The bridge will detect COM5/any supported USB serial port and reconnect automatically." -ForegroundColor Yellow

if (-not $env:ESP32_INGEST_KEY) {
  $secure = Read-Host "Enter the Railway DEVICE_INGEST_KEY" -AsSecureString
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try { $env:ESP32_INGEST_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}

& "$projectRoot\scripts\start-esp32-bridge.ps1" -DeviceId $DeviceId -Baud $Baud
