#!/usr/bin/env bash
set -euo pipefail

BUCKET="${GCS_BUCKET:-gs://bigdata-subject-real-estate-lakehouse}"
CRAWL_DATE="${CRAWL_DATE:-}"
CRAWL_ID="${CRAWL_ID:-}"

download_crawl_folder() {
	local layer="$1"
	local target_dir="$2"

	if [[ -n "$CRAWL_DATE" && -n "$CRAWL_ID" ]]; then
		mkdir -p "$target_dir/source=batdongsan/crawl_date=$CRAWL_DATE"
		gcloud storage cp -r "$BUCKET/$layer/source=batdongsan/crawl_date=$CRAWL_DATE/crawl_id=$CRAWL_ID" "$target_dir/source=batdongsan/crawl_date=$CRAWL_DATE/"
		return
	fi

	gcloud storage rsync --recursive --exclude=".*\.crc$" "$BUCKET/$layer" "$target_dir"
}

download_crawl_folder bronze data/bronze
download_crawl_folder silver data/silver
gcloud storage rsync --recursive --delete-unmatched-destination-objects --exclude=".*\.crc$" "$BUCKET/gold" data/gold
