$ErrorActionPreference = "Stop"

Write-Host "======================================"
Write-Host "PHASE 5 - LOCAL VALIDATION PIPELINE"
Write-Host "Runtime: Windows Local"
Write-Host "======================================"
Write-Host "Note: Linux / Google Cloud VM is the official Spark runtime."

$env:PYTHONPATH = "src"

$runId = "phase5_" + (Get-Date -Format "yyyyMMdd_HHmmss")
$logDir = "data\logs\phase5_spark"
$logFile = Join-Path $logDir "$runId.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-Log {
    param([string]$Message)
    $Message | Tee-Object -FilePath $logFile -Append
}

Write-Log "[INFO] Run ID: $runId"
Write-Log "[INFO] Start time: $(Get-Date -Format o)"
Write-Log "[INFO] PYTHONPATH: $env:PYTHONPATH"
Write-Log "[INFO] Python: $(python --version)"

Write-Log "[STEP 1] Running Spark Silver-to-Gold transformation"
python -m transform.silver_to_gold *>&1 | Tee-Object -FilePath $logFile -Append

Write-Log "[STEP 2] Running Phase 3 Gold validation"
python -m validation.check_phase3 *>&1 | Tee-Object -FilePath $logFile -Append

Write-Log "[STEP 3] Listing Gold outputs"
Get-ChildItem data\gold -Recurse -File | Select-Object -First 50 FullName,Length | Out-String | Tee-Object -FilePath $logFile -Append

Write-Log "[INFO] End time: $(Get-Date -Format o)"
Write-Log "[SUCCESS] Phase 5 local validation completed"
Write-Host "[INFO] Log file: $logFile"
