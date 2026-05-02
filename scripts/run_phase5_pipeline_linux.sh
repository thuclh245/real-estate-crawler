#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
BUCKET="${GCS_BUCKET:-gs://bigdata-subject-real-estate-lakehouse}"
CRAWL_CONFIG="${CRAWL_CONFIG:-configs/crawl_targets.yaml}"
CRAWL_CONFIGS="${CRAWL_CONFIGS:-configs/team/priority_a_ha_noi.yaml,configs/team/priority_a_ha_noi_expand_01.yaml}"
CRAWL_DATE="${CRAWL_DATE:-$(date +%Y-%m-%d)}"
SYNC_TO_GCS="${SYNC_TO_GCS:-true}"
PIPELINE_MODE="${PIPELINE_MODE:-full}"

RUN_ID="daily_$(date +%Y%m%d_%H%M%S)"
LOG_DIR="$PROJECT_DIR/data/logs/daily_pipeline"
LOG_FILE="$LOG_DIR/$RUN_ID.log"
SUMMARY_DIR="$LOG_DIR/run_date=$CRAWL_DATE"
SUMMARY_FILE="$SUMMARY_DIR/daily_run_summary.json"
BRONZE_DATE_DIR="$PROJECT_DIR/data/bronze/source=batdongsan/crawl_date=$CRAWL_DATE"
SILVER_DATE_DIR="$PROJECT_DIR/data/silver/source=batdongsan/crawl_date=$CRAWL_DATE"
START_TIME_ISO="$(date -Is)"
START_TIME_EPOCH="$(date +%s)"
PIPELINE_STATUS="running"
VALIDATION_STATUS="not_started"
GCS_SYNC_STATUS="not_started"
PIPELINE_ERROR_MESSAGE=""
CRAWL_IDS_CREATED=""

write_daily_summary() {
  set +e
  mkdir -p "$SUMMARY_DIR"

  local end_time_iso
  local end_time_epoch
  local duration_seconds
  end_time_iso="$(date -Is)"
  end_time_epoch="$(date +%s)"
  duration_seconds=$((end_time_epoch - START_TIME_EPOCH))

  SUMMARY_FILE="$SUMMARY_FILE" \
  RUN_ID="$RUN_ID" \
  RUN_DATE="$CRAWL_DATE" \
  START_TIME="$START_TIME_ISO" \
  END_TIME="$end_time_iso" \
  DURATION_SECONDS="$duration_seconds" \
  PIPELINE_STATUS="$PIPELINE_STATUS" \
  VALIDATION_STATUS="$VALIDATION_STATUS" \
  GCS_SYNC_STATUS="$GCS_SYNC_STATUS" \
  PIPELINE_ERROR_MESSAGE="$PIPELINE_ERROR_MESSAGE" \
  PIPELINE_MODE="$PIPELINE_MODE" \
  CRAWL_CONFIGS="$CRAWL_CONFIGS" \
  CRAWL_IDS_CREATED="$CRAWL_IDS_CREATED" \
  LOG_FILE="$LOG_FILE" \
  BUCKET="$BUCKET" \
  python - <<'PY'
import json
import os
from pathlib import Path


summary_path = Path(os.environ["SUMMARY_FILE"])
gold_summary_path = Path("data/gold/phase3_summary.json")

gold_summary = {}
if gold_summary_path.exists():
    gold_summary = json.loads(gold_summary_path.read_text(encoding="utf-8"))


def from_gold(key, default=None):
    return gold_summary.get(key, default)


run_summary = {
    "summary_schema_version": "daily_run_summary_v1",
    "run_id": os.environ["RUN_ID"],
    "run_date": os.environ["RUN_DATE"],
    "pipeline_mode": os.environ["PIPELINE_MODE"],
    "pipeline_status": os.environ["PIPELINE_STATUS"],
    "validation_status": os.environ["VALIDATION_STATUS"],
    "gcs_sync_status": os.environ["GCS_SYNC_STATUS"],
    "error_message": os.environ.get("PIPELINE_ERROR_MESSAGE") or None,
    "start_time": os.environ["START_TIME"],
    "end_time": os.environ["END_TIME"],
    "duration_seconds": int(os.environ["DURATION_SECONDS"]),
    "crawl_configs": [
        item.strip()
        for item in os.environ.get("CRAWL_CONFIGS", "").split(",")
        if item.strip()
    ],
    "crawl_ids_created": [
        item.strip()
        for item in os.environ.get("CRAWL_IDS_CREATED", "").split(",")
        if item.strip()
    ],
    "log_file": os.environ["LOG_FILE"],
    "gcs_bucket": os.environ["BUCKET"],
    "total_silver_records": from_gold("total_silver_records"),
    "total_current_listings": from_gold("total_current_listings"),
    "duplicate_record_count": from_gold("duplicate_record_count"),
    "duplicate_rate": from_gold("duplicate_rate"),
    "parse_success_rate": from_gold("parse_success_rate"),
    "missing_price_rate": from_gold("missing_price_rate"),
    "missing_area_rate": from_gold("missing_area_rate"),
    "missing_location_rate": from_gold("missing_location_rate"),
    "snapshot_dates": from_gold("snapshot_dates", []),
    "gold_tables_created": from_gold("gold_tables_created", []),
    "phase3_summary_created_at": from_gold("created_at"),
}

summary_path.write_text(
    json.dumps(run_summary, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print(f"[INFO] Daily run summary written to: {summary_path}")
PY

  set -e
}

on_error() {
  local exit_code=$?
  PIPELINE_STATUS="failed"
  if [[ "$VALIDATION_STATUS" == "running" ]]; then
    VALIDATION_STATUS="failed"
  fi
  if [[ "$GCS_SYNC_STATUS" == "running" || "$GCS_SYNC_STATUS" == "data_synced_pending_log_sync" ]]; then
    GCS_SYNC_STATUS="failed"
  fi
  PIPELINE_ERROR_MESSAGE="command_failed_exit_code_$exit_code"
  write_daily_summary
  echo "[ERROR] Pipeline failed with exit code $exit_code"
  echo "[INFO] Daily run summary: $SUMMARY_FILE"
  exit "$exit_code"
}

trap on_error ERR

run_crawl_and_process() {
  local config_path="$1"
  local config_label
  config_label="$(basename "$config_path")"

  echo "[INFO] Running crawl config: $config_path"

  local before_dirs after_dirs new_dirs
  before_dirs="$(find "$BRONZE_DATE_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort || true)"

  python -m crawler.crawl --config "$config_path"

  after_dirs="$(find "$BRONZE_DATE_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort || true)"
  new_dirs="$(comm -13 <(printf '%s\n' "$before_dirs" | sed '/^$/d' | sort) <(printf '%s\n' "$after_dirs" | sed '/^$/d' | sort) || true)"

  if [[ -z "$new_dirs" ]]; then
    echo "[ERROR] No new crawl_id directory found after running $config_label"
    exit 1
  fi

  while IFS= read -r bronze_crawl_dir; do
    [[ -z "$bronze_crawl_dir" ]] && continue
    local latest_crawl_id
    latest_crawl_id="$(basename "$bronze_crawl_dir")"
    local silver_crawl_dir="$SILVER_DATE_DIR/$latest_crawl_id"

    echo "[INFO] Config: $config_label"
    echo "[INFO] Latest crawl_id: $latest_crawl_id"
    echo "[INFO] Bronze crawl dir: $bronze_crawl_dir"
    echo "[INFO] Silver crawl dir: $silver_crawl_dir"
    CRAWL_IDS_CREATED="${CRAWL_IDS_CREATED}${CRAWL_IDS_CREATED:+,}$latest_crawl_id"

    echo "[2] Bronze to Silver"
    python -m transform.bronze_to_silver \
      --bronze-dir "$bronze_crawl_dir" \
      --silver-dir "$silver_crawl_dir"
  done <<< "$new_dirs"
}

mkdir -p "$LOG_DIR"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "======================================"
echo "DAILY REAL ESTATE PIPELINE"
echo "Runtime: Linux / Google Cloud VM"
echo "======================================"
echo "[INFO] Run ID: $RUN_ID"
echo "[INFO] Start time: $START_TIME_ISO"
echo "[INFO] Project dir: $PROJECT_DIR"
echo "[INFO] Crawl date: $CRAWL_DATE"
echo "[INFO] PYTHONPATH: src"

cd "$PROJECT_DIR"

if [[ ! -f ".venv/bin/activate" ]]; then
  echo "[ERROR] Missing .venv/bin/activate in $PROJECT_DIR"
  exit 1
fi

source .venv/bin/activate
export PYTHONPATH=src

if ! command -v gcloud >/dev/null 2>&1; then
  echo "[ERROR] gcloud CLI is not available"
  exit 1
fi

echo "[INFO] Python: $(python --version)"

IFS=',' read -r -a CRAWL_CONFIG_ARRAY <<< "$CRAWL_CONFIGS"
if [[ "$PIPELINE_MODE" == "smoke" ]]; then
  CRAWL_CONFIG_ARRAY=("${CRAWL_CONFIG_ARRAY[0]}")
  echo "[INFO] PIPELINE_MODE=smoke: running one crawl config and stopping after Bronze->Silver"
fi

for crawl_config in "${CRAWL_CONFIG_ARRAY[@]}"; do
  echo "[1] Crawl Bronze"
  run_crawl_and_process "$crawl_config"
done

if [[ "$PIPELINE_MODE" == "smoke" ]]; then
  echo "[INFO] Smoke test completed"
  PIPELINE_STATUS="success"
  VALIDATION_STATUS="skipped"
  GCS_SYNC_STATUS="skipped"
  write_daily_summary
  echo "[INFO] End time: $(date -Is)"
  echo "[SUCCESS] Smoke pipeline completed"
  echo "[INFO] Log file: $LOG_FILE"
  echo "[INFO] Daily run summary: $SUMMARY_FILE"
  exit 0
fi

echo "[3] Silver to Gold Spark"
if [[ -z "${JAVA_HOME:-}" ]]; then
  echo "[WARN] JAVA_HOME is not set; Spark may fail if Java is unavailable"
fi
python -m transform.silver_to_gold

echo "[4] Validate Gold"
VALIDATION_STATUS="running"
python -m validation.check_phase3
VALIDATION_STATUS="pass"

echo "[5] Sync to GCS bucket"
if [[ "$SYNC_TO_GCS" == "true" ]]; then
  GCS_SYNC_STATUS="running"
  gcloud storage rsync --recursive --exclude=".*\.crc$" "$PROJECT_DIR/data/bronze" "$BUCKET/bronze"
  gcloud storage rsync --recursive --exclude=".*\.crc$" "$PROJECT_DIR/data/silver" "$BUCKET/silver"
  gcloud storage rsync --recursive --delete-unmatched-destination-objects --exclude=".*\.crc$" "$PROJECT_DIR/data/gold" "$BUCKET/gold"
  GCS_SYNC_STATUS="data_synced_pending_log_sync"
  PIPELINE_STATUS="success"
  write_daily_summary
  gcloud storage rsync --recursive --exclude=".*\.crc$" "$PROJECT_DIR/data/logs" "$BUCKET/logs"
  GCS_SYNC_STATUS="success"
  write_daily_summary
  gcloud storage rsync --recursive --exclude=".*\.crc$" "$PROJECT_DIR/data/logs" "$BUCKET/logs"
else
  echo "[INFO] SYNC_TO_GCS=false, skipping GCS sync"
  GCS_SYNC_STATUS="skipped"
  PIPELINE_STATUS="success"
  write_daily_summary
fi

echo "[INFO] End time: $(date -Is)"
echo "[SUCCESS] Pipeline completed"
echo "[INFO] Log file: $LOG_FILE"
echo "[INFO] Daily run summary: $SUMMARY_FILE"
