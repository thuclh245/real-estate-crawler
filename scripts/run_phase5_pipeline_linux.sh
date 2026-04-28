#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
BUCKET="${GCS_BUCKET:-gs://bigdata-subject-real-estate-lakehouse}"
CRAWL_CONFIG="${CRAWL_CONFIG:-configs/crawl_targets.yaml}"
CRAWL_DATE="${CRAWL_DATE:-$(date +%Y-%m-%d)}"
SYNC_TO_GCS="${SYNC_TO_GCS:-true}"

RUN_ID="daily_$(date +%Y%m%d_%H%M%S)"
LOG_DIR="$PROJECT_DIR/data/logs/daily_pipeline"
LOG_FILE="$LOG_DIR/$RUN_ID.log"
BRONZE_DATE_DIR="$PROJECT_DIR/data/bronze/source=batdongsan/crawl_date=$CRAWL_DATE"
SILVER_DATE_DIR="$PROJECT_DIR/data/silver/source=batdongsan/crawl_date=$CRAWL_DATE"

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

echo "[1] Crawl Bronze"
python -m crawler.crawl --config "$CRAWL_CONFIG"

LATEST_CRAWL_ID_DIR="$(find "$BRONZE_DATE_DIR" -mindepth 1 -maxdepth 1 -type d | sort | tail -n 1 || true)"
if [[ -z "$LATEST_CRAWL_ID_DIR" ]]; then
  echo "[ERROR] No crawl_id directory found under $BRONZE_DATE_DIR"
  exit 1
fi

LATEST_CRAWL_ID="$(basename "$LATEST_CRAWL_ID_DIR")"
BRONZE_CRAWL_DIR="$LATEST_CRAWL_ID_DIR"
SILVER_CRAWL_DIR="$SILVER_DATE_DIR/$LATEST_CRAWL_ID"

echo "[INFO] Latest crawl_id: $LATEST_CRAWL_ID"
echo "[INFO] Bronze crawl dir: $BRONZE_CRAWL_DIR"
echo "[INFO] Silver crawl dir: $SILVER_CRAWL_DIR"

echo "[2] Bronze to Silver"
python -m transform.bronze_to_silver \
  --bronze-dir "$BRONZE_CRAWL_DIR" \
  --silver-dir "$SILVER_CRAWL_DIR"

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
  gcloud storage rsync --recursive --exclude=".*\.crc$" "$PROJECT_DIR/data/gold" "$BUCKET/gold"
  gcloud storage rsync --recursive --exclude=".*\.crc$" "$PROJECT_DIR/data/logs" "$BUCKET/logs"
else
  echo "[INFO] SYNC_TO_GCS=false, skipping GCS sync"
fi

echo "[INFO] End time: $(date -Is)"
echo "[SUCCESS] Pipeline completed"
echo "[INFO] Log file: $LOG_FILE"
