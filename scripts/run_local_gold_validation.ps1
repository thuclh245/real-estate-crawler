$ErrorActionPreference = "Stop"
$ProjectDir = if ($env:PROJECT_DIR) { $env:PROJECT_DIR } else { (Resolve-Path (Join-Path $PSScriptRoot "..")).Path }
$PythonExe = Join-Path $ProjectDir ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) { $PythonExe = "python" }
Set-Location $ProjectDir

Write-Host "======================================"
Write-Host "LOCAL GOLD VALIDATION PIPELINE"
Write-Host "Runtime: Windows Local"
Write-Host "======================================"
Write-Host "Note: Linux / Google Cloud VM is the official Spark runtime."

$env:PYTHONPATH = "src"
if (-not $env:PYTHONIOENCODING) { $env:PYTHONIOENCODING = "utf-8" }
if (-not $env:SPARK_MASTER) { $env:SPARK_MASTER = "local[2]" }
if (-not $env:SPARK_DRIVER_MEMORY) { $env:SPARK_DRIVER_MEMORY = "4g" }
if (-not $env:SPARK_DRIVER_MAX_RESULT_SIZE) { $env:SPARK_DRIVER_MAX_RESULT_SIZE = "1g" }
if (-not $env:SPARK_SQL_SHUFFLE_PARTITIONS) { $env:SPARK_SQL_SHUFFLE_PARTITIONS = "8" }
if (-not $env:SPARK_DEFAULT_PARALLELISM) { $env:SPARK_DEFAULT_PARALLELISM = "8" }

$runId = "gold_validation_" + (Get-Date -Format "yyyyMMdd_HHmmss")
$logDir = "data\logs\gold_validation"
$logFile = Join-Path $logDir "$runId.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-Log {
    param([string]$Message)
    $Message | Tee-Object -FilePath $logFile -Append
}

Write-Log "[INFO] Run ID: $runId"
Write-Log "[INFO] Start time: $(Get-Date -Format o)"
Write-Log "[INFO] PYTHONPATH: $env:PYTHONPATH"
Write-Log "[INFO] Python: $(& $PythonExe --version)"
Write-Log "[INFO] Spark master: $env:SPARK_MASTER"
Write-Log "[INFO] Spark driver memory: $env:SPARK_DRIVER_MEMORY"
Write-Log "[INFO] Spark shuffle partitions: $env:SPARK_SQL_SHUFFLE_PARTITIONS"

Write-Log "[STEP 1] Running Spark Silver-to-Gold transformation"
& $PythonExe -m transform.silver_to_gold *>&1 | Tee-Object -FilePath $logFile -Append

Write-Log "[STEP 2] Running Gold readiness validation"
& $PythonExe -m validation.check_gold_readiness *>&1 | Tee-Object -FilePath $logFile -Append

Write-Log "[STEP 3] Listing Gold outputs"
Get-ChildItem data\gold -Recurse -File | Select-Object -First 50 FullName,Length | Out-String | Tee-Object -FilePath $logFile -Append

Write-Log "[INFO] End time: $(Get-Date -Format o)"
Write-Log "[SUCCESS] Local Gold validation completed"
Write-Host "[INFO] Log file: $logFile"
