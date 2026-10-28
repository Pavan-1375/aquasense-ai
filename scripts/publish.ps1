param(
  [string]$CommitMessage = 'Update AquaSense application',
  [switch]$SkipChecks
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path '.git')) { throw 'This project is not a Git repository. Run git init and configure an origin first.' }
$origin = git remote get-url origin 2>$null
if (-not $origin) { throw 'No GitHub origin is configured. Add the exact AquaSense repository URL before publishing.' }

if (-not $SkipChecks) {
  npm run build
  py -3 -m compileall -q backend
  $env:PYTHONPATH = 'backend'
  py -3 -m unittest discover -s backend/tests -v
}

git add -A
if (git diff --cached --quiet) {
  Write-Host 'No changes to commit.'
  exit 0
}
git commit -m $CommitMessage
$branch = git branch --show-current
if (-not $branch) { $branch = 'main'; git branch -M $branch }
git push -u origin $branch
Write-Host "Published $branch to $origin" -ForegroundColor Green

