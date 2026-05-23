param(
    [ValidateSet("full", "smoke")]
    [string]$Mode = $env:PIPELINE_MODE
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($Mode)) { $Mode = "full" }

$ProjectDir = if ($env:PROJECT_DIR) { $env:PROJECT_DIR } else { (Resolve-Path (Join-Path $PSScriptRoot "..")).Path }
$Bucket = if ($env:GCS_BUCKET) { $env:GCS_BUCKET } else { "gs://bigdata-subject-real-estate-lakehouse" }
$CrawlConfigsRaw = if ($env:CRAWL_CONFIGS) { $env:CRAWL_CONFIGS } else { "configs/team/priority_a_ha_noi.yaml,configs/team/priority_a_ha_noi_expand_01.yaml" }
$CrawlDate = if ($env:CRAWL_DATE) { $env:CRAWL_DATE } else { Get-Date -Format "yyyy-MM-dd" }
$SyncToGcs = if ($env:SYNC_TO_GCS) { $env:SYNC_TO_GCS } else { "false" }

$RunId = "daily_" + (Get-Date -Format "yyyyMMdd_HHmmss")
$LogDir = Join-Path $ProjectDir "data\logs\daily_pipeline"
$LogFile = Join-Path $LogDir "$RunId.log"
$BronzeDateDir = Join-Path $ProjectDir "data\bronze\source=batdongsan\crawl_date=$CrawlDate"
$SilverDateDir = Join-Path $ProjectDir "data\silver\source=batdongsan\crawl_date=$CrawlDate"
$StartTime = Get-Date
$PipelineStatus = "running"
$ValidationStatus = "not_started"
$GcsSyncStatus = "not_started"
$ErrorMessage = ""
$CrawlIdsCreated = New-Object System.Collections.Generic.List[string]

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$env:PYTHONPATH = "src"

function Write-Log {
    param([string]$Message)
    $Message | Tee-Object -FilePath $LogFile -Append
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

    python -c @"
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
    source_names=['batdongsan'],
    crawl_ids_created=summary['crawl_ids_created'],
    crawl_configs=summary['crawl_configs'],
    gold_summary=gold_summary,
    publish_status=decision.status,
    publish_block_reason=decision.block_reason,
    input_silver_partitions=[
        f"source=batdongsan/crawl_date={os.environ['OBS_RUN_DATE']}/{crawl_id}"
        for crawl_id in summary['crawl_ids_created']
    ],
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
}

function Invoke-CrawlAndSilver {
    param([string]$ConfigPath)
    Write-Log "[1] Crawl + Bronze-to-Silver: $ConfigPath"
    $before = @()
    if (Test-Path $BronzeDateDir) {
        $before = Get-ChildItem $BronzeDateDir -Directory | ForEach-Object { $_.FullName }
    }
    python -m crawler.crawl --config $ConfigPath *>&1 | Tee-Object -FilePath $LogFile -Append
    $after = @()
    if (Test-Path $BronzeDateDir) {
        $after = Get-ChildItem $BronzeDateDir -Directory | ForEach-Object { $_.FullName }
    }
    $newDirs = $after | Where-Object { $before -notcontains $_ }
    if (-not $newDirs) { throw "No new crawl_id directory found after $ConfigPath" }
    foreach ($bronzeDir in $newDirs) {
        $crawlId = Split-Path $bronzeDir -Leaf
        $CrawlIdsCreated.Add($crawlId) | Out-Null
        python -m transform.bronze_to_silver --bronze-dir $bronzeDir --silver-dir (Join-Path $SilverDateDir $crawlId) *>&1 | Tee-Object -FilePath $LogFile -Append
    }
}

try {
    Set-Location $ProjectDir
    Write-Log "[INFO] Run ID: $RunId"
    Write-Log "[INFO] Mode: $Mode"
    Write-Log "[INFO] Crawl date: $CrawlDate"

    $configs = $CrawlConfigsRaw.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    if ($Mode -eq "smoke") { $configs = @($configs[0]) }
    $preflightArgs = @("-m", "src.validation.preflight", "--run-id", $RunId)
    foreach ($config in $configs) { $preflightArgs += @("--config", $config) }
    if ($Mode -eq "full") { $preflightArgs += "--require-spark" }
    python @preflightArgs *>&1 | Tee-Object -FilePath $LogFile -Append
    foreach ($config in $configs) { Invoke-CrawlAndSilver $config }

    if ($Mode -eq "smoke") {
        $script:PipelineStatus = "success"
        $script:ValidationStatus = "skipped"
        $script:GcsSyncStatus = "skipped"
        Write-Observability
        exit 0
    }

    Write-Log "[2] Silver-to-Gold"
    python -m transform.silver_to_gold *>&1 | Tee-Object -FilePath $LogFile -Append

    Write-Log "[3] Validation"
    $script:ValidationStatus = "running"
    python -m validation.check_phase3 *>&1 | Tee-Object -FilePath $LogFile -Append
    $script:ValidationStatus = "pass"

    Write-Log "[4] GCS sync"
    if ($SyncToGcs -eq "true") {
        $script:GcsSyncStatus = "running"
        gcloud storage rsync --recursive --exclude=".*\.crc$" "$ProjectDir\data\bronze" "$Bucket/bronze" *>&1 | Tee-Object -FilePath $LogFile -Append
        gcloud storage rsync --recursive --exclude=".*\.crc$" "$ProjectDir\data\silver" "$Bucket/silver" *>&1 | Tee-Object -FilePath $LogFile -Append
        gcloud storage rsync --recursive --delete-unmatched-destination-objects --exclude=".*\.crc$" "$ProjectDir\data\gold" "$Bucket/gold" *>&1 | Tee-Object -FilePath $LogFile -Append
        $script:GcsSyncStatus = "success"
    } else {
        $script:GcsSyncStatus = "skipped"
    }

    $script:PipelineStatus = "success"
    Write-Observability
    Write-Log "[SUCCESS] Daily pipeline completed"
} catch {
    $script:PipelineStatus = "failed"
    if ($script:ValidationStatus -eq "running") { $script:ValidationStatus = "failed" }
    if ($script:GcsSyncStatus -eq "running") { $script:GcsSyncStatus = "failed" }
    $script:ErrorMessage = $_.Exception.Message
    Write-Observability
    throw
}
