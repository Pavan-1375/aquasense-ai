param([string]$Destination = "backups")
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$source = "backend/hydroinsight.db"
if (!(Test-Path $source)) { throw "SQLite database not found: $source" }
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
Copy-Item $source (Join-Path $Destination "aquasense-$stamp.db")
Write-Output "Backup created in $Destination"
