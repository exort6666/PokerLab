$ErrorActionPreference = "Continue"
$logFile = "overnight_$(Get-Date -Format 'yyyyMMdd_HHmm').log"

Write-Host "=== Log: $logFile ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "=== STAGE 1: 3-max x 500K ===" -ForegroundColor Yellow
$start1 = Get-Date
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
python tools/run_preflop_sweep.py `
    --n 3 `
    --stacks 5 8 10 12 15 20 25 30 `
    --iterations 500000 `
    --engine mc `
    --postflop-model allin_equivalent `
    --workers 11 2>&1 | Tee-Object -FilePath $logFile -Append
$end1 = Get-Date
Write-Host ""
Write-Host "STAGE 1 done in $([math]::Round(($end1 - $start1).TotalMinutes, 1)) min" -ForegroundColor Green
Write-Host ""

Write-Host "=== STAGE 2: 4-max x 200K ===" -ForegroundColor Yellow
$start2 = Get-Date
python tools/run_preflop_sweep.py `
    --n 4 `
    --stacks 5 8 10 12 15 20 25 30 `
    --iterations 200000 `
    --engine mc `
    --postflop-model allin_equivalent `
    --workers 11 2>&1 | Tee-Object -FilePath $logFile -Append
$end2 = Get-Date
Write-Host ""
Write-Host "STAGE 2 done in $([math]::Round(($end2 - $start2).TotalMinutes, 1)) min" -ForegroundColor Green
Write-Host ""

$total = ($end2 - $start1).TotalMinutes
Write-Host "=== ALL DONE in $([math]::Round($total, 1)) min ===" -ForegroundColor Cyan
Write-Host "Log: $logFile" -ForegroundColor Cyan