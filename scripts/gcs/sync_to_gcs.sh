#!/usr/bin/env bash
set -euo pipefail

BUCKET="gs://bigdata-subject-real-estate-lakehouse"

CRAWL_DATE="${CRAWL_DATE:-}"
CRAWL_ID="${CRAWL_ID:-}"

upload_crawl_folder() {
	local layer="$1"
	local source_dir="$2"

	if [[ -n "$CRAWL_DATE" && -n "$CRAWL_ID" ]]; then
		local date_dir="$source_dir/source=batdongsan/crawl_date=$CRAWL_DATE"
		local crawl_dir="$date_dir/crawl_id=$CRAWL_ID"

		if [[ -d "$crawl_dir" ]]; then
			gcloud storage cp -r "$crawl_dir" "$BUCKET/$layer/source=batdongsan/crawl_date=$CRAWL_DATE/"
			return
		fi

		echo "[WARN] Missing crawl folder: $crawl_dir"
		return
	fi

	gcloud storage rsync --recursive --exclude=".*\.crc$" "$source_dir" "$BUCKET/$layer"
}

upload_crawl_folder bronze data/bronze
upload_crawl_folder silver data/silver
gcloud storage rsync --recursive --exclude=".*\.crc$" data/gold "$BUCKET/gold"
