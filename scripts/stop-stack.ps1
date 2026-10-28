$ErrorActionPreference = 'SilentlyContinue'
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match 'uvicorn app\.main:app' -or $_.CommandLine -match 'vite.*--host 127\.0\.0\.1' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Write-Host 'AquaSense frontend and backend processes stopped.'

