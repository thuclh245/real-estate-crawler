$BUCKET = $env:GCS_BUCKET
if (-not $BUCKET) {
	$BUCKET = "gs://bigdata-subject-real-estate-lakehouse"
}

$CRAWL_DATE = $env:CRAWL_DATE
$CRAWL_ID = $env:CRAWL_ID

if ($CRAWL_DATE -and $CRAWL_ID) {
	New-Item -ItemType Directory -Force -Path "data/bronze/source=batdongsan/crawl_date=$CRAWL_DATE" | Out-Null
	New-Item -ItemType Directory -Force -Path "data/silver/source=batdongsan/crawl_date=$CRAWL_DATE" | Out-Null

	gcloud storage cp -r "$BUCKET/bronze/source=batdongsan/crawl_date=$CRAWL_DATE/crawl_id=$CRAWL_ID" "data/bronze/source=batdongsan/crawl_date=$CRAWL_DATE/"
	gcloud storage cp -r "$BUCKET/silver/source=batdongsan/crawl_date=$CRAWL_DATE/crawl_id=$CRAWL_ID" "data/silver/source=batdongsan/crawl_date=$CRAWL_DATE/"
}
else {
	gcloud storage rsync --recursive --exclude=".*\.crc$" "$BUCKET/bronze" data/bronze
	gcloud storage rsync --recursive --exclude=".*\.crc$" "$BUCKET/silver" data/silver
}

gcloud storage rsync --recursive --exclude=".*\.crc$" "$BUCKET/gold" data/gold
