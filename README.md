# Real Estate Crawler

This crawler collects real estate listings from batdongsan.com.vn and stores them in the Bronze layer to support a lakehouse pipeline.

The current goal is Phase 1:

```text
Web source -> Crawler -> Bronze raw HTML/text/metadata/log
```

CSV is not the primary storage format in the current flow.

## Setup

Use Windows PowerShell and the `.venv` environment.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
crawl4ai-setup
```

Quick check:

```powershell
python -c "from crawl4ai import AsyncWebCrawler; print('OK')"
```

## Crawl Configuration

The crawler reads configuration from:

```text
configs/crawl_targets.yaml
```

The YAML file contains:

```text
source
base_url
crawl_settings
targets
```

Important settings:

```yaml
crawl_settings:
  fetch_mode: crawl4ai
  max_pages_per_target: 1
  max_listings_per_target: 10
  request_delay_seconds: 5
  concurrency: 1
  save_images: false
  stop_on_block: true
  max_retries: 1
  retry_delay_seconds: 10
  crawler_version: v0.1
  parser_version: v0.1
```

Each target should include `business_type`, `category`, `property_type_group`, `city_slug`, `location_path`, and optionally `seed_url`. Batdongsan seed URLs should be built with the full location path, for example `ban-can-ho-chung-cu-phuong-cau-giay-tp-ha-noi`, not the old district-only form.

## Run the Crawler

```powershell
.\.venv\Scripts\Activate.ps1
python src\crawl.py
```

Run with a specific config:

```powershell
python src\crawl.py --config configs\crawl_targets.yaml
python src\crawl.py --config configs\crawl_targets_scale.yaml
python src\crawl.py --config configs\team\priority_a_ha_noi.yaml
```

`configs/crawl_targets.yaml` is for smaller tests. `configs/crawl_targets_scale.yaml` is for a moderate scale batch. `configs/team/priority_a_ha_noi.yaml` covers the priority A Hanoi locations across apartment, house, land, and villa/townhouse categories:

```text
max_pages_per_target = 1
max_listings_per_target = 20
4 locations x 4 categories x 20 = up to 320 listings/run
```

After a successful run, the terminal prints a `crawl_summary` with metrics such as:

The crawler also writes location/category audit files next to the crawl summary:

```text
data/bronze/source=batdongsan/crawl_date=YYYY-MM-DD/crawl_id=<crawl_id>/crawl_log/
    crawl_location_audit_<crawl_id>.json
    audit_sample_<crawl_id>.csv
```

Seed URLs are checked against the final URL after fetch. If a target redirects to a generic page such as `/nha-dat-ban`, the crawler prints a red error and skips detail crawling for that seed. Detail records also include `source_seed_url`, `final_seed_url`, `is_seed_url_valid`, `detail_location_raw`, `location_match_status`, `location_match_confidence`, `category_match_status`, and `category_match_confidence`.

```text
crawl_id
total_listing_urls_found
total_detail_pages_requested
success_count
failed_count
blocked_count
raw_html_file_count
metadata_file_count
crawl_success_rate
```

## Bronze Output

The main data is stored under:

```text
data/bronze/source=batdongsan/crawl_date=YYYY-MM-DD/
  crawl_id=<crawl_id>/
    raw_html/
    raw_text/
    raw_json/
    metadata/
    crawl_log/
```

Each successful listing has:

```text
raw_html/listing_id=<id>.html
raw_text/listing_id=<id>.txt
raw_json/listing_id=<id>.json
metadata/listing_id=<id>.json
```

Logs and summary are written per crawl run:

```text
crawl_log/crawl_log_<crawl_id>.jsonl
crawl_log/crawl_summary_<crawl_id>.json
```

The `crawl_id` partition prevents raw HTML and metadata from being overwritten when multiple batches run on the same day.

## Audit After Crawl

After each run, the crawler prints the `crawl_id` and an audit command. Run:

```powershell
python scripts\audit_bronze.py --crawl-id <crawl_id>
```

Go if:

```text
crawl_success_rate >= 0.8
blocked_count = 0 or low
raw_html_file_count = success_count
metadata_file_count = success_count
avg_html_size is reasonable
```

No-go if:

```text
blocked_count increases
HTML size is very small
success_count drops sharply
metadata is missing
```

## List Page Debugging

List page debug files are stored separately by `crawl_id` to avoid overwriting previous runs:

```text
data/debug/list_pages/crawl_id=<crawl_id>/
  ban-nha-rieng_cau-giay_p1.html
  ban-nha-rieng_cau-giay_p1.json
```

The `.html` file is the raw snapshot of the page. If opened directly in a browser, it may break layout or show script errors because it depends on batdongsan.com.vn domain resources, cookies, assets, and JavaScript.

Use the `.json` file to evaluate whether the crawl succeeded:

```json
{
  "http_status": 200,
  "html_length": 614173,
  "listing_urls_found": 30,
  "is_blocked": false,
  "error_message": null
}
```

If `http_status = 200`, `listing_urls_found > 0`, `is_blocked = false`, and `error_message = null`, then the list page crawl is considered healthy.

## Operational Notes

- Do not scale too quickly. Start with 5 listings per target, then 20 listings per target, then increase gradually.
- To reach 100-300 listings/day, prefer 2-5 small batches with the scale config instead of one very large batch.
- Do not bypass CAPTCHA or use proxy rotation to evade anti-bot protection.
- Images are not downloaded in the current version.
- Raw HTML in Bronze is kept so it can be parsed again later.
- The Phase 1 parser should stay minimal; the production parser belongs in the Silver/ETL phase.

## Design Docs

The guiding design documents are located in:

```text
docs/real_estate_agent_docs/
```
