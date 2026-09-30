# run_overnight.ps1
# Job 1 (8 workers): preflop 4-max x 500K
# Job 2 (3 workers): postflop 15 boards x 9 configs x 5000 iter
# Then: build U_avg for each config.

$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

$stamp = Get-Date -Format 'yyyyMMdd_HHmm'
$log1 = "overnight_preflop_$stamp.log"
$log2 = "overnight_postflop_$stamp.log"
$log3 = "overnight_uavg_$stamp.log"

Write-Host "=== Logs ===" -ForegroundColor Cyan
Write-Host "  preflop : $log1"
Write-Host "  postflop: $log2"
Write-Host "  uavg    : $log3"
Write-Host ""

Write-Host "=== Job 1: preflop 4-max x 500K (8 workers) ===" -ForegroundColor Yellow
$job1 = Start-Process -FilePath "python" `
    -ArgumentList "-u","tools/run_preflop_sweep.py",
                  "--n","4",
                  "--stacks","5","8","10","12","15","20","25","30",
                  "--iterations","500000",
                  "--engine","mc",
                  "--postflop-model","allin_equivalent",
                  "--workers","8" `
    -NoNewWindow -PassThru `
    -RedirectStandardOutput $log1 `
    -RedirectStandardError "${log1}.err"
Write-Host "  PID = $($job1.Id)"

Write-Host "=== Job 2: postflop sweep (3 workers) ===" -ForegroundColor Yellow
$job2 = Start-Process -FilePath "python" `
    -ArgumentList "-u","tools/run_postflop_sweep.py",
                  "--iterations","5000",
                  "--workers","3" `
    -NoNewWindow -PassThru `
    -RedirectStandardOutput $log2 `
    -RedirectStandardError "${log2}.err"
Write-Host "  PID = $($job2.Id)"
Write-Host ""

$t0 = Get-Date
Write-Host "=== Waiting for Job 1 (preflop) ===" -ForegroundColor Cyan
$job1.WaitForExit()
$t1 = Get-Date
Write-Host "Job 1 done in $([math]::Round(($t1-$t0).TotalMinutes,1)) min" -ForegroundColor Green

if (-not $job2.HasExited) {
    Write-Host "=== Waiting for Job 2 (postflop) ===" -ForegroundColor Cyan
    $job2.WaitForExit()
}
$t2 = Get-Date
Write-Host "Job 2 done in $([math]::Round(($t2-$t0).TotalMinutes,1)) min" -ForegroundColor Green

Write-Host ""
Write-Host "=== Building U_avg ===" -ForegroundColor Cyan
python -u tools/build_uavg.py 2>&1 | Tee-Object -FilePath $log3 -Append

$total = ((Get-Date) - $t0).TotalMinutes
Write-Host ""
Write-Host "=== ALL DONE in $([math]::Round($total,1)) min ===" -ForegroundColor Cyan
Write-Host "Logs: $log1 | $log2 | $log3"