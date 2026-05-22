#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
BUCKET="${GCS_BUCKET:-gs://bigdata-subject-real-estate-lakehouse}"
CRAWL_CONFIGS="${CRAWL_CONFIGS:-configs/team/priority_a_ha_noi.yaml,configs/team/priority_a_ha_noi_expand_01.yaml}"
CRAWL_DATE="${CRAWL_DATE:-$(date +%Y-%m-%d)}"
PIPELINE_MODE="${PIPELINE_MODE:-full}"
SYNC_TO_GCS="${SYNC_TO_GCS:-true}"

if [[ "${1:-}" == "--mode" && -n "${2:-}" ]]; then
  PIPELINE_MODE="$2"
fi

RUN_ID="daily_$(date +%Y%m%d_%H%M%S)"
LOG_DIR="$PROJECT_DIR/data/logs/daily_pipeline"
LOG_FILE="$LOG_DIR/$RUN_ID.log"
BRONZE_DATE_DIR="$PROJECT_DIR/data/bronze/source=batdongsan/crawl_date=$CRAWL_DATE"
SILVER_DATE_DIR="$PROJECT_DIR/data/silver/source=batdongsan/crawl_date=$CRAWL_DATE"
START_TIME_ISO="$(date -Is)"
START_TIME_EPOCH="$(date +%s)"
PIPELINE_STATUS="running"
VALIDATION_STATUS="not_started"
GCS_SYNC_STATUS="not_started"
ERROR_MESSAGE=""
CRAWL_IDS_CREATED=""

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
  python - <<'PY'
import json
import os
from pathlib import Path

from observability import DailyRunSummary, DataQualityReport

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

run_crawl_and_silver() {
  local config_path="$1"
  local before_dirs after_dirs new_dirs
  before_dirs="$(find "$BRONZE_DATE_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort || true)"
  python -m crawler.crawl --config "$config_path"
  after_dirs="$(find "$BRONZE_DATE_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort || true)"
  new_dirs="$(comm -13 <(printf '%s\n' "$before_dirs" | sed '/^$/d' | sort) <(printf '%s\n' "$after_dirs" | sed '/^$/d' | sort) || true)"
  if [[ -z "$new_dirs" ]]; then
    echo "[ERROR] No new crawl_id directory found after $config_path"
    exit 1
  fi

  while IFS= read -r bronze_crawl_dir; do
    [[ -z "$bronze_crawl_dir" ]] && continue
    local crawl_id
    crawl_id="$(basename "$bronze_crawl_dir")"
    CRAWL_IDS_CREATED="${CRAWL_IDS_CREATED}${CRAWL_IDS_CREATED:+,}$crawl_id"
    python -m transform.bronze_to_silver \
      --bronze-dir "$bronze_crawl_dir" \
      --silver-dir "$SILVER_DATE_DIR/$crawl_id"
  done <<< "$new_dirs"
}

trap on_error ERR
mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

cd "$PROJECT_DIR"
source .venv/bin/activate
export PYTHONPATH=src

echo "[INFO] Run ID: $RUN_ID"
echo "[INFO] Mode: $PIPELINE_MODE"
echo "[INFO] Crawl date: $CRAWL_DATE"

IFS=',' read -r -a CRAWL_CONFIG_ARRAY <<< "$CRAWL_CONFIGS"
if [[ "$PIPELINE_MODE" == "smoke" ]]; then
  CRAWL_CONFIG_ARRAY=("${CRAWL_CONFIG_ARRAY[0]}")
fi

for crawl_config in "${CRAWL_CONFIG_ARRAY[@]}"; do
  echo "[1] Crawl + Bronze-to-Silver: $crawl_config"
  run_crawl_and_silver "$crawl_config"
done

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
python -m validation.check_phase3
VALIDATION_STATUS="pass"

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
