# tools/git_commit.ps1
# Quick commit + push.
# Usage:
#   .\tools\git_commit.ps1 "add postflop CFR v5.1"

param(
    [Parameter(Mandatory=$true)]
    [string]$Message
)

$ErrorActionPreference = "Stop"

Write-Host "=== git status ===" -ForegroundColor Cyan
git status --short
Write-Host ""

Write-Host "=== git add -A ===" -ForegroundColor Cyan
git add -A

Write-Host "=== git commit ===" -ForegroundColor Cyan
git commit -m $Message
if ($LASTEXITCODE -ne 0) {
    Write-Host "Nothing to commit or error" -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "=== git push ===" -ForegroundColor Cyan
git push

Write-Host ""
Write-Host "Done" -ForegroundColor Green