# 02 - Phase 1 Crawler + Bronze Ingestion Specification

## Goal

Phase 1 must create a reliable Bronze raw ingestion layer. It must not depend on CSV as the main data source.

Core rule:

```text
crawl first -> save raw HTML + metadata to Bronze -> parse officially later in Phase 3
```

## Current implementation status

Current working direction:

- `requests` mode returned HTTP 403 “Just a moment...” anti-bot pages.
- Crawler was updated to detect block and stop early.
- `crawl4ai` fetch adapter was added.
- After tuning block detection to avoid Cloudflare false positives, test run succeeded:

```text
total_listing_urls_found = 15
total_detail_pages_requested = 15
success_count = 15
failed_count = 0
blocked_count = 0
crawl_success_rate = 1.0
duplicate_url_count = 0
```

## Required behavior

For each target:

```text
1. Build or read seed_url.
2. Crawl listing page.
3. Extract listing URLs.
4. Deduplicate listing URLs within current run.
5. Crawl each detail page.
6. Save raw HTML.
7. Save raw text/markdown if available.
8. Save metadata JSON per listing.
9. Append crawl_log JSONL.
10. Write crawl_summary JSON.
```

## Safe crawling rules

```text
fetch_mode: crawl4ai
max_pages_per_target: 2 initially
max_listings_per_target: 20 initially
request_delay_seconds: 5
concurrency: 1
stop_on_block: true
save_images: false
```

Do not:

- bypass CAPTCHA
- rotate proxies to evade blocking
- retry indefinitely
- download real images in v1
- increase concurrency aggressively

## Crawl target strategy

Crawl by category + location context:

```text
ban-nha-rieng + ha-noi + cau-giay
ban-can-ho-chung-cu + ha-noi + thanh-xuan
ban-dat + ha-noi + ha-dong
```

Reason: if detail pages lack district/location, fallback can use `crawl_city`, `crawl_district`, `crawl_category`, `property_type_group`.

## Priority categories for v1

```text
ban-can-ho-chung-cu -> apartment
ban-nha-rieng -> private_house
ban-dat -> land
ban-nha-biet-thu-lien-ke -> villa_townhouse
```

## Bronze folder structure

Recommended local structure:

```text
data/
  bronze/
    source=batdongsan/
      crawl_date=YYYY-MM-DD/
        raw_html/
          listing_id=<id>.html
        raw_text/
          listing_id=<id>.txt
        raw_json/
          listing_id=<id>.json        # optional extracted/raw payload
        metadata/
          listing_id=<id>.json
        crawl_log/
          crawl_log_<crawl_id>.jsonl
          crawl_summary_<crawl_id>.json
```

## Metadata per listing

Required fields:

```text
listing_id
listing_url
source
scraped_at
crawl_date
crawl_id
crawl_status
http_status
raw_html_path
raw_text_path
raw_json_path or metadata_path
listing_business_type
crawl_category
crawl_category_label
property_type_group
crawl_city
crawl_city_label
crawl_district
crawl_district_label
crawl_seed_url
page_url
page_number
fetch_mode
crawler_version
parser_version   # null in Phase 1
error_message
retry_count
```

## Crawl summary fields

```text
crawl_id
source
crawl_date
started_at
finished_at
total_listing_pages_requested
listing_page_failed_count
total_listing_urls_found
total_detail_pages_requested
success_count
failed_count
blocked_count
http_403_count
http_429_count
listing_page_block_rate
crawl_success_rate
duplicate_url_count
raw_html_file_count
metadata_file_count
avg_html_size
request_delay_seconds
concurrency
fetch_mode
stop_on_block
```

## Phase 1 Definition of Done

Phase 1 test is done when:

```text
[ ] crawl4ai mode can fetch listing pages.
[ ] crawler extracts listing URLs.
[ ] crawler fetches detail pages.
[ ] raw_html files exist.
[ ] raw_text files exist if markdown/text is available.
[ ] metadata JSON exists for each successful listing.
[ ] crawl_log JSONL exists.
[ ] crawl_summary JSON exists.
[ ] crawl_id is unique per run.
[ ] duplicate_url_count is computed.
[ ] crawler does not depend on CSV.
[ ] parser.py is minimal and not duplicated.
```
