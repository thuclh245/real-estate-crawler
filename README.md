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
  max_listings_per_target: 5
  request_delay_seconds: 5
  concurrency: 1
  save_images: false
  stop_on_block: true
  crawler_version: v0.1
  parser_version: v0.1
```

Each target should include `business_type`, `category`, `property_type_group`, `city`, `district`, and `seed_url`.

## Run the Crawler

```powershell
.\.venv\Scripts\Activate.ps1
python src\crawl.py
```

After a successful run, the terminal prints a `crawl_summary` with metrics such as:

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
- Do not bypass CAPTCHA or use proxy rotation to evade anti-bot protection.
- Images are not downloaded in the current version.
- Raw HTML in Bronze is kept so it can be parsed again later.
- The Phase 1 parser should stay minimal; the production parser belongs in the Silver/ETL phase.

## Design Docs

The guiding design documents are located in:

```text
docs/real_estate_agent_docs/
```
