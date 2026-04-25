# 05 - Bronze Data Contract

## Purpose

Bronze stores raw or near-raw data. It is for reprocessing, audit, debugging and lineage. Do not use Bronze directly for final analytics.

## Bronze principles

```text
Do not delete duplicates.
Do not delete records with missing price.
Do not delete records with missing location.
Do not overwrite raw files.
Always store crawl metadata.
Always preserve raw HTML if crawl succeeded.
```

## Folder contract

```text
data/bronze/source=<source_slug>/crawl_date=<YYYY-MM-DD>/
  raw_html/
  raw_text/
  raw_json/          # optional; raw extracted payload if available
  metadata/
  crawl_log/
```

## Metadata JSON contract

Required fields:

```yaml
listing_id: string
listing_url: string
source: string
scraped_at: timestamp
crawl_date: date
crawl_id: string
crawl_status: string
http_status: integer|null
raw_html_path: string|null
raw_text_path: string|null
raw_json_path: string|null
metadata_path: string|null
listing_business_type: string|null
crawl_category: string|null
crawl_category_label: string|null
property_type_group: string|null
crawl_city: string|null
crawl_city_label: string|null
crawl_district: string|null
crawl_district_label: string|null
crawl_seed_url: string|null
page_url: string|null
page_number: integer|null
fetch_mode: string
crawler_version: string
parser_version: string|null
error_message: string|null
retry_count: integer
```

## Crawl status values

```text
ok
blocked
failed_http
failed_timeout
failed_fetch
failed_storage
duplicate_url
missing_listing_id
```

## Crawl summary contract

```yaml
crawl_id: string
source: string
crawl_date: date
started_at: timestamp
finished_at: timestamp
total_listing_pages_requested: integer
listing_page_failed_count: integer
total_listing_urls_found: integer
total_detail_pages_requested: integer
success_count: integer
failed_count: integer
blocked_count: integer
http_403_count: integer
http_429_count: integer
listing_page_block_rate: float
crawl_success_rate: float
duplicate_url_count: integer
raw_html_file_count: integer
metadata_file_count: integer
avg_html_size: float
fetch_mode: string
request_delay_seconds: float
concurrency: integer
stop_on_block: boolean
```

## Acceptance tests

```text
[ ] Every successful listing has raw_html.
[ ] Every successful listing has metadata JSON.
[ ] crawl_summary exists per crawl_id.
[ ] crawl_log exists per crawl_id.
[ ] raw file paths in metadata exist.
[ ] raw_html_file_count equals success_count for current run.
[ ] metadata_file_count equals success_count for current run.
[ ] crawl_id is unique.
```
