$ProjectDir = if ($env:PROJECT_DIR) { $env:PROJECT_DIR } else { (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path }
Set-Location $ProjectDir

$BUCKET = $env:GCS_BUCKET
if (-not $BUCKET) {
	$BUCKET = "gs://bigdata-subject-real-estate-lakehouse"
}

$CRAWL_DATE = $env:CRAWL_DATE
$CRAWL_ID = $env:CRAWL_ID

if ($CRAWL_DATE -and $CRAWL_ID) {
	$bronzeCrawlDir = "data/bronze/source=batdongsan/crawl_date=$CRAWL_DATE/crawl_id=$CRAWL_ID"
	$silverCrawlDir = "data/silver/source=batdongsan/crawl_date=$CRAWL_DATE/crawl_id=$CRAWL_ID"

	if (Test-Path $bronzeCrawlDir) {
		gcloud storage cp -r $bronzeCrawlDir "$BUCKET/bronze/source=batdongsan/crawl_date=$CRAWL_DATE/"
	} else {
		Write-Warning "Missing crawl folder: $bronzeCrawlDir"
	}

	if (Test-Path $silverCrawlDir) {
		gcloud storage cp -r $silverCrawlDir "$BUCKET/silver/source=batdongsan/crawl_date=$CRAWL_DATE/"
	} else {
		Write-Warning "Missing crawl folder: $silverCrawlDir"
	}
} else {
	gcloud storage rsync --recursive --exclude=".*\.crc$" data/bronze "$BUCKET/bronze"
	gcloud storage rsync --recursive --exclude=".*\.crc$" data/silver "$BUCKET/silver"
}

gcloud storage rsync --recursive --delete-unmatched-destination-objects --exclude=".*\.crc$" data/gold "$BUCKET/gold"
