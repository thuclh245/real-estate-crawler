#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$PROJECT_DIR"

BUCKET="${GCS_BUCKET:-gs://bigdata-subject-real-estate-lakehouse}"
CRAWL_DATE="${CRAWL_DATE:-}"
CRAWL_ID="${CRAWL_ID:-}"

SOURCE="${SOURCE:-}"

download_crawl_folder() {
	local layer="$1"
	local target_dir="$2"

	if [[ -n "$CRAWL_DATE" && -n "$CRAWL_ID" ]]; then
		local active_sources=()
		if [[ -n "$SOURCE" ]]; then
			active_sources+=("$SOURCE")
		else
			# Auto-detect sources by listing objects in bucket partition or using default active sources
			active_sources=("batdongsan" "nhatot")
		fi

		for src in "${active_sources[@]}"; do
			echo "[INFO] Checking $layer crawl folder in GCS for source $src..."
			if gcloud storage ls "$BUCKET/$layer/source=$src/crawl_date=$CRAWL_DATE/crawl_id=$CRAWL_ID" &>/dev/null; then
				echo "[INFO] Downloading GCS $layer folder for source $src..."
				mkdir -p "$target_dir/source=$src/crawl_date=$CRAWL_DATE"
				gcloud storage cp -r "$BUCKET/$layer/source=$src/crawl_date=$CRAWL_DATE/crawl_id=$CRAWL_ID" "$target_dir/source=$src/crawl_date=$CRAWL_DATE/"
			fi
		done
		return
	fi

	gcloud storage rsync --recursive --exclude=".*\.crc$" "$BUCKET/$layer" "$target_dir"
}

download_crawl_folder bronze data/bronze
download_crawl_folder silver data/silver
gcloud storage rsync --recursive --delete-unmatched-destination-objects --exclude=".*\.crc$" "$BUCKET/gold" data/gold
