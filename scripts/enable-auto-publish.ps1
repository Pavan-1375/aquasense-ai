$ErrorActionPreference = 'Stop'
if (-not (Test-Path (Join-Path (Get-Location) '.git'))) { throw 'Run this from the project root after git init.' }
$origin = git remote get-url origin 2>$null
if (-not $origin) { throw 'Configure the exact AquaSense GitHub origin before enabling auto-publish.' }
git config core.hooksPath .githooks
Write-Host "Auto-publish enabled for $origin" -ForegroundColor Green
