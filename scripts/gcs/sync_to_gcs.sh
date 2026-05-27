#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$PROJECT_DIR"

BUCKET="${GCS_BUCKET:-gs://bigdata-subject-real-estate-lakehouse}"

CRAWL_DATE="${CRAWL_DATE:-}"
CRAWL_ID="${CRAWL_ID:-}"

SOURCE="${SOURCE:-}"

upload_crawl_folder() {
	local layer="$1"
	local source_dir="$2"

	if [[ -n "$CRAWL_DATE" && -n "$CRAWL_ID" ]]; then
		local active_sources=()
		if [[ -n "$SOURCE" ]]; then
			active_sources+=("$SOURCE")
		else
			# Auto-detect sources from folders if not specified
			for src_path in "$source_dir"/source=*; do
				if [[ -d "$src_path" ]]; then
					active_sources+=("$(basename "$src_path" | cut -d= -f2)")
				fi
			done
		fi

		for src in "${active_sources[@]}"; do
			local date_dir="$source_dir/source=$src/crawl_date=$CRAWL_DATE"
			local crawl_dir="$date_dir/crawl_id=$CRAWL_ID"

			if [[ -d "$crawl_dir" ]]; then
				echo "[INFO] Uploading $layer folder: $crawl_dir"
				gcloud storage cp -r "$crawl_dir" "$BUCKET/$layer/source=$src/crawl_date=$CRAWL_DATE/"
			fi
		done
		return
	fi

	gcloud storage rsync --recursive --exclude=".*\.crc$" "$source_dir" "$BUCKET/$layer"
}

upload_crawl_folder bronze data/bronze
upload_crawl_folder silver data/silver
gcloud storage rsync --recursive --delete-unmatched-destination-objects --exclude=".*\.crc$" data/gold "$BUCKET/gold"
