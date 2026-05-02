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
BRONZE_DATE_DIR="$PROJECT_DIR/data/bronze/source=batdongsan/crawl_date=$CRAWL_DATE"
SILVER_DATE_DIR="$PROJECT_DIR/data/silver/source=batdongsan/crawl_date=$CRAWL_DATE"

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
echo "[INFO] Start time: $(date -Is)"
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
  echo "[INFO] End time: $(date -Is)"
  echo "[SUCCESS] Smoke pipeline completed"
  echo "[INFO] Log file: $LOG_FILE"
  exit 0
fi

echo "[3] Silver to Gold Spark"
if [[ -z "${JAVA_HOME:-}" ]]; then
  echo "[WARN] JAVA_HOME is not set; Spark may fail if Java is unavailable"
fi
python -m transform.silver_to_gold

echo "[4] Validate Gold"
python -m validation.check_phase3

echo "[5] Sync to GCS bucket"
if [[ "$SYNC_TO_GCS" == "true" ]]; then
  gcloud storage rsync --recursive --exclude=".*\.crc$" "$PROJECT_DIR/data/bronze" "$BUCKET/bronze"
  gcloud storage rsync --recursive --exclude=".*\.crc$" "$PROJECT_DIR/data/silver" "$BUCKET/silver"
  gcloud storage rsync --recursive --delete-unmatched-destination-objects --exclude=".*\.crc$" "$PROJECT_DIR/data/gold" "$BUCKET/gold"
  gcloud storage rsync --recursive --exclude=".*\.crc$" "$PROJECT_DIR/data/logs" "$BUCKET/logs"
else
  echo "[INFO] SYNC_TO_GCS=false, skipping GCS sync"
fi

echo "[INFO] End time: $(date -Is)"
echo "[SUCCESS] Pipeline completed"
echo "[INFO] Log file: $LOG_FILE"
