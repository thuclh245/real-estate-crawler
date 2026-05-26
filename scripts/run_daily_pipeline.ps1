param(
    [ValidateSet("full", "smoke")]
    [string]$Mode = $env:PIPELINE_MODE
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($Mode)) { $Mode = "full" }

$ProjectDir = if ($env:PROJECT_DIR) { $env:PROJECT_DIR } else { (Resolve-Path (Join-Path $PSScriptRoot "..")).Path }
$PythonExe = Join-Path $ProjectDir ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) { $PythonExe = "python" }
$Bucket = if ($env:GCS_BUCKET) { $env:GCS_BUCKET } else { "gs://bigdata-subject-real-estate-lakehouse" }
$CrawlConfigsRaw = if ($env:CRAWL_CONFIGS) { $env:CRAWL_CONFIGS } else { "configs/team/batdongsan_house_150.yaml,configs/sources/nhatot.yaml" }
$CrawlDate = if ($env:CRAWL_DATE) { $env:CRAWL_DATE } else { Get-Date -Format "yyyy-MM-dd" }
$SyncToGcs = if ($env:SYNC_TO_GCS) { $env:SYNC_TO_GCS } else { "true" }

$RunId = if ($env:RUN_ID) { $env:RUN_ID } else { "daily_" + (Get-Date -Format "yyyyMMdd_HHmmss") }
$LogDir = Join-Path $ProjectDir "data\logs\daily_pipeline"
$LogFile = Join-Path $LogDir "$RunId.log"
$StartTime = Get-Date
$PipelineStatus = "running"
$ValidationStatus = "not_started"
$GcsSyncStatus = "not_started"
$ErrorMessage = ""
$CrawlIdsCreated = New-Object System.Collections.Generic.List[string]
$SourceNamesCreated = New-Object System.Collections.Generic.List[string]
$InputSilverPartitions = New-Object System.Collections.Generic.List[string]

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$env:PYTHONPATH = "src"
if (-not $env:PYTHONIOENCODING) { $env:PYTHONIOENCODING = "utf-8" }
if (-not $env:SPARK_MASTER) { $env:SPARK_MASTER = "local[2]" }
if (-not $env:SPARK_DRIVER_MEMORY) { $env:SPARK_DRIVER_MEMORY = "4g" }
if (-not $env:SPARK_DRIVER_MAX_RESULT_SIZE) { $env:SPARK_DRIVER_MAX_RESULT_SIZE = "1g" }
if (-not $env:SPARK_SQL_SHUFFLE_PARTITIONS) { $env:SPARK_SQL_SHUFFLE_PARTITIONS = "8" }
if (-not $env:SPARK_DEFAULT_PARALLELISM) { $env:SPARK_DEFAULT_PARALLELISM = "8" }

function Write-Log {
    param([string]$Message)
    $Message | Tee-Object -FilePath $LogFile -Append
}

function Assert-NativeSuccess {
    param([string]$Step)
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

function Write-Observability {
    $endTime = Get-Date
    $duration = [int]($endTime - $StartTime).TotalSeconds
    $env:OBS_RUN_ID = $RunId
    $env:OBS_RUN_DATE = $CrawlDate
    $env:OBS_PIPELINE_MODE = $Mode
    $env:OBS_PIPELINE_STATUS = $PipelineStatus
    $env:OBS_VALIDATION_STATUS = $ValidationStatus
    $env:OBS_GCS_SYNC_STATUS = $GcsSyncStatus
    $env:OBS_ERROR_MESSAGE = $ErrorMessage
    $env:OBS_START_TIME = $StartTime.ToString("o")
    $env:OBS_END_TIME = $endTime.ToString("o")
    $env:OBS_DURATION_SECONDS = "$duration"
    $env:OBS_CRAWL_CONFIGS = $CrawlConfigsRaw
    $env:OBS_CRAWL_IDS_CREATED = ($CrawlIdsCreated -join ",")
    $env:OBS_SOURCE_NAMES = ($SourceNamesCreated | Select-Object -Unique) -join ","
    $env:OBS_INPUT_SILVER_PARTITIONS = ($InputSilverPartitions -join ",")

    & $PythonExe -c @"
import json
import os
from pathlib import Path
from observability import DailyRunSummary, DataQualityReport, ProductionRunSummary
from validation.publish_gate import evaluate_publish_gate

gold_summary_path = Path('data/gold/phase3_summary.json')
gold_summary = json.loads(gold_summary_path.read_text(encoding='utf-8')) if gold_summary_path.exists() else {}
summary = DailyRunSummary().generate_summary(
    run_id=os.environ['OBS_RUN_ID'],
    run_date=os.environ['OBS_RUN_DATE'],
    pipeline_status=os.environ['OBS_PIPELINE_STATUS'],
    validation_status=os.environ['OBS_VALIDATION_STATUS'],
    gcs_sync_status=os.environ['OBS_GCS_SYNC_STATUS'],
    start_time=os.environ['OBS_START_TIME'],
    end_time=os.environ['OBS_END_TIME'],
    duration_seconds=int(os.environ['OBS_DURATION_SECONDS']),
    error_message=os.environ.get('OBS_ERROR_MESSAGE') or None,
    gold_summary=gold_summary,
    crawl_configs=[x.strip() for x in os.environ.get('OBS_CRAWL_CONFIGS', '').split(',') if x.strip()],
    crawl_ids_created=[x.strip() for x in os.environ.get('OBS_CRAWL_IDS_CREATED', '').split(',') if x.strip()],
    pipeline_mode=os.environ['OBS_PIPELINE_MODE'],
)
DailyRunSummary().write_summary(summary)
decision = evaluate_publish_gate(
    pipeline_mode=os.environ['OBS_PIPELINE_MODE'],
    run_class='production' if os.environ['OBS_PIPELINE_MODE'] == 'full' else 'smoke',
    pipeline_status=os.environ['OBS_PIPELINE_STATUS'],
    validation_status=os.environ['OBS_VALIDATION_STATUS'],
    silver_records_written=summary['total_silver_records'],
)
production_summary = ProductionRunSummary().generate_summary(
    run_id=os.environ['OBS_RUN_ID'],
    run_date=os.environ['OBS_RUN_DATE'],
    pipeline_status=os.environ['OBS_PIPELINE_STATUS'],
    validation_status=os.environ['OBS_VALIDATION_STATUS'],
    start_time=os.environ['OBS_START_TIME'],
    end_time=os.environ['OBS_END_TIME'],
    duration_seconds=int(os.environ['OBS_DURATION_SECONDS']),
    pipeline_mode=os.environ['OBS_PIPELINE_MODE'],
    run_class='production' if os.environ['OBS_PIPELINE_MODE'] == 'full' else 'smoke',
    source_names=[x.strip() for x in os.environ.get('OBS_SOURCE_NAMES', '').split(',') if x.strip()],
    crawl_ids_created=summary['crawl_ids_created'],
    crawl_configs=summary['crawl_configs'],
    gold_summary=gold_summary,
    publish_status=decision.status,
    publish_block_reason=decision.block_reason,
    input_silver_partitions=[x.strip() for x in os.environ.get('OBS_INPUT_SILVER_PARTITIONS', '').split(',') if x.strip()],
    published_outputs=['data/gold'] if decision.status == 'published' else [],
    error_message=os.environ.get('OBS_ERROR_MESSAGE') or None,
)
ProductionRunSummary().write_summary(production_summary)
history = []
for path in sorted(Path('data/logs/daily_pipeline').glob('run_date=*/daily_run_summary.json')):
    try:
        row = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        continue
    if row.get('run_date') != summary['run_date']:
        history.append(row)
report = DataQualityReport()
metrics = {
    'parse_success_rate': summary['parse_success_rate'],
    'duplicate_rate': summary['duplicate_rate'],
    'missing_price_rate': summary['missing_price_rate'],
    'missing_area_rate': summary['missing_area_rate'],
    'missing_location_rate': summary['missing_location_rate'],
    'total_records': summary['total_silver_records'],
    'total_current_listings': summary['total_current_listings'],
}
comparison = report.compute_comparison(metrics, history)
quality_level = report.classify_quality(
    metrics['parse_success_rate'],
    metrics['duplicate_rate'],
    baseline_metrics=(comparison or {}).get('baseline_metrics') if comparison else None,
    current_metrics=metrics,
)
for path in report.write_reports(summary['run_date'], 'data/reports', include_json=True, metrics=metrics, comparison=comparison, quality_level=quality_level):
    print(f'Data quality report written to: {path}')
"@ | Tee-Object -FilePath $LogFile -Append
    Assert-NativeSuccess "write observability"
}

function Invoke-SourcesToSilver {
    param([string[]]$ConfigPaths)
    Write-Log "[1] Source-aware Crawl + Bronze-to-Silver"
    $summaryPath = Join-Path $LogDir "$RunId.sources_to_silver.json"
    $runnerArgs = @("-m", "pipeline.sources_to_silver", "--base-dir", (Join-Path $ProjectDir "data"), "--summary-output", $summaryPath)
    foreach ($configPath in $ConfigPaths) {
        $runnerArgs += @("--config", $configPath)
    }
    & $PythonExe @runnerArgs *>&1 | Tee-Object -FilePath $LogFile -Append
    Assert-NativeSuccess "sources-to-silver step"

    $runnerSummary = Get-Content -Path $summaryPath -Raw | ConvertFrom-Json
    foreach ($run in $runnerSummary.runs) {
        $CrawlIdsCreated.Add([string]$run.crawl_id) | Out-Null
        $SourceNamesCreated.Add([string]$run.source) | Out-Null
        $InputSilverPartitions.Add("source=$($run.source)/crawl_date=$($run.crawl_date)/crawl_id=$($run.crawl_id)") | Out-Null
    }
}

try {
    Set-Location $ProjectDir
    Write-Log "[INFO] Run ID: $RunId"
    Write-Log "[INFO] Mode: $Mode"
    Write-Log "[INFO] Crawl date: $CrawlDate"
    Write-Log "[INFO] Spark master: $env:SPARK_MASTER"
    Write-Log "[INFO] Spark driver memory: $env:SPARK_DRIVER_MEMORY"
    Write-Log "[INFO] Spark shuffle partitions: $env:SPARK_SQL_SHUFFLE_PARTITIONS"

    $configs = $CrawlConfigsRaw.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    if ($Mode -eq "smoke") { $configs = @($configs[0]) }
    $preflightArgs = @("-m", "src.validation.preflight", "--run-id", $RunId, "--output-dir", (Join-Path $ProjectDir "data\logs\preflight"))
    foreach ($config in $configs) { $preflightArgs += @("--config", $config) }
    if ($Mode -eq "full") { $preflightArgs += "--require-spark" }
    & $PythonExe @preflightArgs *>&1 | Tee-Object -FilePath $LogFile -Append
    Assert-NativeSuccess "preflight"
    Invoke-SourcesToSilver $configs

    if ($Mode -eq "smoke") {
        $script:PipelineStatus = "success"
        $script:ValidationStatus = "skipped"
        $script:GcsSyncStatus = "skipped"
        Write-Observability
        exit 0
    }

    Write-Log "[2] Silver-to-Gold"
    & $PythonExe -m transform.silver_to_gold *>&1 | Tee-Object -FilePath $LogFile -Append
    Assert-NativeSuccess "silver-to-gold"

    Write-Log "[3] Validation"
    $script:ValidationStatus = "running"
    & $PythonExe -m validation.check_gold_readiness *>&1 | Tee-Object -FilePath $LogFile -Append
    Assert-NativeSuccess "validation"
    $script:ValidationStatus = "pass"

    if ($script:ValidationStatus -ne "pass") {
        $script:PipelineStatus = "failed"
        $script:ErrorMessage = "validation_gate_failed"
        Write-Observability
        throw "Validation gate failed"
    }

    Write-Log "[4] GCS sync"
    if ($SyncToGcs -eq "true") {
        $script:GcsSyncStatus = "running"
        gcloud storage rsync --recursive --exclude=".*\.crc$" "$ProjectDir\data\bronze" "$Bucket/bronze" *>&1 | Tee-Object -FilePath $LogFile -Append
        Assert-NativeSuccess "bronze gcs sync"
        gcloud storage rsync --recursive --exclude=".*\.crc$" "$ProjectDir\data\silver" "$Bucket/silver" *>&1 | Tee-Object -FilePath $LogFile -Append
        Assert-NativeSuccess "silver gcs sync"
        gcloud storage rsync --recursive --delete-unmatched-destination-objects --exclude=".*\.crc$" "$ProjectDir\data\gold" "$Bucket/gold" *>&1 | Tee-Object -FilePath $LogFile -Append
        Assert-NativeSuccess "gold gcs sync"
        $script:GcsSyncStatus = "success"
    } else {
        $script:GcsSyncStatus = "skipped"
    }

    $script:PipelineStatus = "success"
    Write-Observability
    Assert-NativeSuccess "final observability"
    Write-Log "[SUCCESS] Daily pipeline completed"
} catch {
    $script:PipelineStatus = "failed"
    if ($script:ValidationStatus -eq "running") { $script:ValidationStatus = "failed" }
    if ($script:GcsSyncStatus -eq "running") { $script:GcsSyncStatus = "failed" }
    $script:ErrorMessage = $_.Exception.Message
    Write-Observability
    throw
}
