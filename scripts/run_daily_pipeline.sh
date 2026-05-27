#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
BUCKET="${GCS_BUCKET:-gs://bigdata-subject-real-estate-lakehouse}"
CRAWL_CONFIGS="${CRAWL_CONFIGS:-configs/team/batdongsan_house_150.yaml,configs/sources/nhatot.yaml}"
CRAWL_DATE="${CRAWL_DATE:-$(date +%Y-%m-%d)}"
PIPELINE_MODE="${PIPELINE_MODE:-full}"
SYNC_TO_GCS="${SYNC_TO_GCS:-true}"
PIPELINE_LOG_DIR="$PROJECT_DIR/data/logs/daily_pipeline"
RUN_ID="${RUN_ID:-daily_$(date +%Y%m%d_%H%M%S)}"

if [[ "${1:-}" == "--mode" && -n "${2:-}" ]]; then
  PIPELINE_MODE="$2"
fi

LOG_DIR="$PIPELINE_LOG_DIR"
LOG_FILE="$LOG_DIR/$RUN_ID.log"
START_TIME_ISO="$(date -Is)"
START_TIME_EPOCH="$(date +%s)"
PIPELINE_STATUS="running"
VALIDATION_STATUS="not_started"
GCS_SYNC_STATUS="not_started"
ERROR_MESSAGE=""
CRAWL_IDS_CREATED=""
SOURCE_NAMES_CREATED=""
INPUT_SILVER_PARTITIONS=""

LOCKFILE="$PROJECT_DIR/data/daily_run.lock"
GCS_LOCK="$BUCKET/locks/daily_run.lock"

acquire_lock() {
  if [[ -f "$LOCKFILE" ]]; then
    local pid
    pid=$(cat "$LOCKFILE")
    if kill -0 "$pid" 2>/dev/null; then
      echo "[ERROR] Another local pipeline run is already executing (PID: $pid). Aborting."
      exit 3
    fi
  fi
  
  mkdir -p "$(dirname "$LOCKFILE")"
  echo "$$" > "$LOCKFILE"

  if [[ "$SYNC_TO_GCS" == "true" ]]; then
    echo "[INFO] Checking GCS run lock..."
    if gcloud storage ls "$GCS_LOCK" &>/dev/null; then
      echo "[ERROR] Another pipeline run is active in GCS ($GCS_LOCK). Aborting."
      rm -f "$LOCKFILE"
      exit 4
    fi
    echo "[INFO] Acquiring GCS run lock..."
    gcloud storage cp "$LOCKFILE" "$GCS_LOCK" &>/dev/null
  fi
}

release_lock() {
  echo "[INFO] Releasing pipeline run locks..."
  rm -f "$LOCKFILE"
  if [[ "$SYNC_TO_GCS" == "true" ]]; then
    gcloud storage rm "$GCS_LOCK" &>/dev/null || true
  fi
}

write_observability() {
  set +e
  local end_time_iso end_time_epoch duration_seconds
  end_time_iso="$(date -Is)"
  end_time_epoch="$(date +%s)"
  duration_seconds=$((end_time_epoch - START_TIME_EPOCH))

  RUN_ID="$RUN_ID" \
  RUN_DATE="$CRAWL_DATE" \
  PIPELINE_MODE="$PIPELINE_MODE" \
  PIPELINE_STATUS="$PIPELINE_STATUS" \
  VALIDATION_STATUS="$VALIDATION_STATUS" \
  GCS_SYNC_STATUS="$GCS_SYNC_STATUS" \
  ERROR_MESSAGE="$ERROR_MESSAGE" \
  START_TIME="$START_TIME_ISO" \
  END_TIME="$end_time_iso" \
  DURATION_SECONDS="$duration_seconds" \
  CRAWL_CONFIGS="$CRAWL_CONFIGS" \
  CRAWL_IDS_CREATED="$CRAWL_IDS_CREATED" \
  SOURCE_NAMES_CREATED="$SOURCE_NAMES_CREATED" \
  INPUT_SILVER_PARTITIONS="$INPUT_SILVER_PARTITIONS" \
  python - <<'PY'
import json
import os
from pathlib import Path

from observability import DailyRunSummary, DataQualityReport, ProductionRunSummary
from validation.publish_gate import evaluate_publish_gate

gold_summary_path = Path("data/gold/phase3_summary.json")
gold_summary = {}
if gold_summary_path.exists():
    gold_summary = json.loads(gold_summary_path.read_text(encoding="utf-8"))

summary = DailyRunSummary().generate_summary(
    run_id=os.environ["RUN_ID"],
    run_date=os.environ["RUN_DATE"],
    pipeline_status=os.environ["PIPELINE_STATUS"],
    validation_status=os.environ["VALIDATION_STATUS"],
    gcs_sync_status=os.environ["GCS_SYNC_STATUS"],
    start_time=os.environ["START_TIME"],
    end_time=os.environ["END_TIME"],
    duration_seconds=int(os.environ["DURATION_SECONDS"]),
    error_message=os.environ.get("ERROR_MESSAGE") or None,
    gold_summary=gold_summary,
    crawl_configs=[x.strip() for x in os.environ.get("CRAWL_CONFIGS", "").split(",") if x.strip()],
    crawl_ids_created=[x.strip() for x in os.environ.get("CRAWL_IDS_CREATED", "").split(",") if x.strip()],
    pipeline_mode=os.environ["PIPELINE_MODE"],
)
DailyRunSummary().write_summary(summary)
decision = evaluate_publish_gate(
    pipeline_mode=os.environ["PIPELINE_MODE"],
    run_class="production" if os.environ["PIPELINE_MODE"] == "full" else "smoke",
    pipeline_status=os.environ["PIPELINE_STATUS"],
    validation_status=os.environ["VALIDATION_STATUS"],
    silver_records_written=summary["total_silver_records"],
)
production_summary = ProductionRunSummary().generate_summary(
    run_id=os.environ["RUN_ID"],
    run_date=os.environ["RUN_DATE"],
    pipeline_status=os.environ["PIPELINE_STATUS"],
    validation_status=os.environ["VALIDATION_STATUS"],
    start_time=os.environ["START_TIME"],
    end_time=os.environ["END_TIME"],
    duration_seconds=int(os.environ["DURATION_SECONDS"]),
    pipeline_mode=os.environ["PIPELINE_MODE"],
    run_class="production" if os.environ["PIPELINE_MODE"] == "full" else "smoke",
    source_names=[x.strip() for x in os.environ.get("SOURCE_NAMES_CREATED", "").split(",") if x.strip()],
    crawl_ids_created=summary["crawl_ids_created"],
    crawl_configs=summary["crawl_configs"],
    gold_summary=gold_summary,
    publish_status=decision.status,
    publish_block_reason=decision.block_reason,
    input_silver_partitions=[x.strip() for x in os.environ.get("INPUT_SILVER_PARTITIONS", "").split(",") if x.strip()],
    published_outputs=["data/gold"] if decision.status == "published" else [],
    error_message=os.environ.get("ERROR_MESSAGE") or None,
)
ProductionRunSummary().write_summary(production_summary)

history = []
for path in sorted(Path("data/logs/daily_pipeline").glob("run_date=*/daily_run_summary.json")):
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        continue
    if row.get("run_date") != summary["run_date"]:
        history.append(row)

report = DataQualityReport()
metrics = {
    "parse_success_rate": summary["parse_success_rate"],
    "duplicate_rate": summary["duplicate_rate"],
    "missing_price_rate": summary["missing_price_rate"],
    "missing_area_rate": summary["missing_area_rate"],
    "missing_location_rate": summary["missing_location_rate"],
    "total_records": summary["total_silver_records"],
    "total_current_listings": summary["total_current_listings"],
}
comparison = report.compute_comparison(metrics, history)
quality_level = report.classify_quality(
    metrics["parse_success_rate"],
    metrics["duplicate_rate"],
    baseline_metrics=(comparison or {}).get("baseline_metrics") if comparison else None,
    current_metrics=metrics,
)
for path in report.write_reports(
    summary["run_date"],
    "data/reports",
    include_json=True,
    metrics=metrics,
    comparison=comparison,
    quality_level=quality_level,
):
    print(f"Data quality report written to: {path}")
PY
  set -e
}

on_error() {
  local exit_code=$?
  PIPELINE_STATUS="failed"
  ERROR_MESSAGE="command_failed_exit_code_$exit_code"
  if [[ "$VALIDATION_STATUS" == "running" ]]; then VALIDATION_STATUS="failed"; fi
  if [[ "$GCS_SYNC_STATUS" == "running" ]]; then GCS_SYNC_STATUS="failed"; fi
  write_observability
  echo "[ERROR] Pipeline failed with exit code $exit_code"
  exit "$exit_code"
}

run_sources_to_silver() {
  local summary_path="$LOG_DIR/$RUN_ID.sources_to_silver.json"
  local runner_args=(--base-dir "$PROJECT_DIR/data" --summary-output "$summary_path")
  for config_path in "$@"; do
    runner_args+=(--config "$config_path")
  done
  python -m pipeline.sources_to_silver "${runner_args[@]}"
  CRAWL_IDS_CREATED="$(python -c "import json,sys; data=json.load(open(sys.argv[1], encoding='utf-8')); print(','.join(run['crawl_id'] for run in data['runs']))" "$summary_path")"
  SOURCE_NAMES_CREATED="$(python -c "import json,sys; data=json.load(open(sys.argv[1], encoding='utf-8')); print(','.join(sorted(set(run['source'] for run in data['runs']))))" "$summary_path")"
  INPUT_SILVER_PARTITIONS="$(python -c "import json,sys; data=json.load(open(sys.argv[1], encoding='utf-8')); print(','.join(f\"source={run['source']}/crawl_date={run['crawl_date']}/crawl_id={run['crawl_id']}\" for run in data['runs']))" "$summary_path")"
}

trap on_error ERR
trap release_lock EXIT
acquire_lock

mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

cd "$PROJECT_DIR"
source .venv/bin/activate
export PYTHONPATH=src
export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"
export SPARK_MASTER="${SPARK_MASTER:-local[2]}"
export SPARK_DRIVER_MEMORY="${SPARK_DRIVER_MEMORY:-2g}"
export SPARK_DRIVER_MAX_RESULT_SIZE="${SPARK_DRIVER_MAX_RESULT_SIZE:-1g}"
export SPARK_SQL_SHUFFLE_PARTITIONS="${SPARK_SQL_SHUFFLE_PARTITIONS:-8}"
export SPARK_DEFAULT_PARALLELISM="${SPARK_DEFAULT_PARALLELISM:-8}"

echo "[INFO] Run ID: $RUN_ID"
echo "[INFO] Mode: $PIPELINE_MODE"
echo "[INFO] Crawl date: $CRAWL_DATE"
echo "[INFO] Spark master: $SPARK_MASTER"
echo "[INFO] Spark driver memory: $SPARK_DRIVER_MEMORY"
echo "[INFO] Spark shuffle partitions: $SPARK_SQL_SHUFFLE_PARTITIONS"

IFS=',' read -r -a CRAWL_CONFIG_ARRAY <<< "$CRAWL_CONFIGS"
if [[ "$PIPELINE_MODE" == "smoke" ]]; then
  CRAWL_CONFIG_ARRAY=("${CRAWL_CONFIG_ARRAY[0]}")
fi

PREFLIGHT_ARGS=(--run-id "$RUN_ID" --output-dir "$PROJECT_DIR/data/logs/preflight")
for crawl_config in "${CRAWL_CONFIG_ARRAY[@]}"; do
  PREFLIGHT_ARGS+=(--config "$crawl_config")
done
if [[ "$PIPELINE_MODE" == "full" ]]; then
  PREFLIGHT_ARGS+=(--require-spark)
fi
python -m src.validation.preflight "${PREFLIGHT_ARGS[@]}"

if [[ "$PIPELINE_MODE" == "transform" || "$PIPELINE_MODE" == "no-crawl" ]]; then
  echo "[1] Running Bronze-to-Silver on existing Bronze data (NO CRAWL)"
  python scripts/tools/run_bronze_to_silver_all.py
else
  echo "[1] Source-aware Crawl + Bronze-to-Silver"
  run_sources_to_silver "${CRAWL_CONFIG_ARRAY[@]}"
fi

if [[ "$PIPELINE_MODE" == "smoke" ]]; then
  PIPELINE_STATUS="success"
  VALIDATION_STATUS="skipped"
  GCS_SYNC_STATUS="skipped"
  write_observability
  exit 0
fi

echo "[2] Silver-to-Gold"
python -m transform.silver_to_gold

echo "[3] Validation"
VALIDATION_STATUS="running"
python -m validation.check_gold_readiness
VALIDATION_STATUS="pass"

if [[ "$VALIDATION_STATUS" != "pass" ]]; then
  PIPELINE_STATUS="failed"
  ERROR_MESSAGE="validation_gate_failed"
  write_observability
  echo "[ERROR] Validation gate failed"
  exit 1
fi

echo "[4] GCS sync"
if [[ "$SYNC_TO_GCS" == "true" ]]; then
  GCS_SYNC_STATUS="running"
  gcloud storage rsync --recursive --exclude=".*\.crc$" "$PROJECT_DIR/data/bronze" "$BUCKET/bronze"
  gcloud storage rsync --recursive --exclude=".*\.crc$" "$PROJECT_DIR/data/silver" "$BUCKET/silver"
  gcloud storage rsync --recursive --delete-unmatched-destination-objects --exclude=".*\.crc$" "$PROJECT_DIR/data/gold" "$BUCKET/gold"
  GCS_SYNC_STATUS="success"
else
  GCS_SYNC_STATUS="skipped"
fi

PIPELINE_STATUS="success"
write_observability
if [[ "$SYNC_TO_GCS" == "true" ]]; then
  gcloud storage rsync --recursive --exclude=".*\.crc$" "$PROJECT_DIR/data/logs" "$BUCKET/logs"
  gcloud storage rsync --recursive --exclude=".*\.crc$" "$PROJECT_DIR/data/reports" "$BUCKET/reports"
fi

echo "[SUCCESS] Daily pipeline completed"
