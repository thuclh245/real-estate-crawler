# Real Estate Crawler

This crawler collects real estate listings from batdongsan.com.vn and stores them in the Bronze layer to support a lakehouse pipeline.

The current goal is Phase 1:

```text
Web source -> Crawler -> Bronze raw HTML/text/metadata/log
```

CSV is not the primary storage format in the current flow.

## Setup

Use a local `.venv` environment.

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
crawl4ai-setup
```

Linux/macOS Bash:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
crawl4ai-setup
```

If you see this error on Ubuntu:

```bash
bash: .venv/bin/activate: No such file or directory
```

install venv support and recreate `.venv`:

```bash
sudo apt update
sudo apt install -y python3.12-venv
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
crawl4ai-setup
```

Quick check:

Windows PowerShell:

```powershell
python -c "from crawl4ai import AsyncWebCrawler; print('OK')"
```

Linux/macOS Bash:

```bash
python -c "from crawl4ai import AsyncWebCrawler; print('OK')"
```

### Spark Setup for Gold ETL (Linux VM)

`transform.silver_to_gold` requires PySpark and Java runtime.

Install Python dependency:

```bash
source .venv/bin/activate
python -m pip install pyspark py4j
```

Install Java runtime (Ubuntu):

```bash
sudo apt update
sudo apt install -y openjdk-17-jre-headless
```

Set `JAVA_HOME` before running Gold ETL:

```bash
export PYTHONPATH=src
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"
python3 -m transform.silver_to_gold
```

Optional: persist `JAVA_HOME` for future sessions:

```bash
echo 'export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64' >> ~/.bashrc
echo 'export PATH="$JAVA_HOME/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Common errors and fix:

```text
ModuleNotFoundError: No module named 'py4j' or 'pyspark'
  -> source .venv/bin/activate && python -m pip install pyspark py4j

JAVA_HOME is not set / JAVA_GATEWAY_EXITED
  -> install openjdk-17-jre-headless and export JAVA_HOME as above
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

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src"
python -m crawler.crawl
```

Linux/macOS Bash:

```bash
source .venv/bin/activate
export PYTHONPATH=src
python -m crawler.crawl
```

Run with a specific config:

Windows PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m crawler.crawl --config configs\crawl_targets.yaml
python -m crawler.crawl --config configs\crawl_targets_scale.yaml
python -m crawler.crawl --config configs\team\priority_a_ha_noi.yaml
python -m crawler.crawl --config configs\team\priority_a_ha_noi_expand_01.yaml
```

Linux/macOS Bash:

```bash
export PYTHONPATH=src
python -m crawler.crawl --config configs/crawl_targets.yaml
python -m crawler.crawl --config configs/crawl_targets_scale.yaml
python -m crawler.crawl --config configs/team/priority_a_ha_noi.yaml
python -m crawler.crawl --config configs/team/priority_a_ha_noi_expand_01.yaml
```

Use `.\.venv\Scripts\python.exe` instead of `python` if PowerShell is not using the project virtual environment. On Linux/macOS, use `.venv/bin/python`.

Config purpose:

```text
configs/crawl_targets.yaml
  Small smoke test, 3 targets.

configs/crawl_targets_scale.yaml
  Moderate scale batch, 3 targets with more pages/listings.

configs/team/priority_a_ha_noi.yaml
  Priority A Hanoi batch 01:
  Thanh Xuân, Cầu Giấy, Đống Đa, Hà Đông.

configs/team/priority_a_ha_noi_expand_01.yaml
  Priority A Hanoi expanded batch 01:
  Hoàn Kiếm, Ba Đình, Hoàng Mai, Tây Hồ, Từ Liêm, Hai Bà Trưng.
```

`configs/team/priority_a_ha_noi.yaml` covers the first priority A Hanoi locations across apartment, house, land, and villa/townhouse categories:

```text
max_pages_per_target = 1
max_listings_per_target = 20
4 locations x 4 categories x 20 = up to 320 listings/run
```

`configs/team/priority_a_ha_noi_expand_01.yaml` adds six more Hanoi locations:

```text
max_pages_per_target = 1
max_listings_per_target = 20
6 locations x 4 categories x 20 = up to 480 listings/run
```

For group work, each member should run only one small config at a time. If the team splits work manually, copy a team config and reduce it to 2-3 locations per person.

After a successful run, the terminal prints a `crawl_summary` with metrics such as:

The crawler also writes location/category audit files next to the crawl summary:

```text
data/bronze/source=batdongsan/crawl_date=YYYY-MM-DD/crawl_id=<crawl_id>/crawl_log/
    crawl_location_audit_<crawl_id>.json
    audit_sample_<crawl_id>.csv
```

Seed URLs are checked against the final URL after fetch. If a target redirects to a generic page such as `/nha-dat-ban`, the crawler prints a red error and skips detail crawling for that seed. Detail records also include `source_seed_url`, `final_seed_url`, `is_seed_url_valid`, `listing_card_location_raw`, `listing_card_old_district_raw`, `detail_address_raw`, `breadcrumb_location_raw`, `location_evidence_text`, `location_evidence_source`, `location_match_status`, `location_match_confidence`, `category_match_status`, and `category_match_confidence`.

Location audit uses stronger evidence first: detail address block, listing card location, breadcrumb, detail URL, title/description, then seed URL fallback. If a match only comes from title or description, confidence is `medium` and `detail_location_raw` stays empty so it is not confused with a real address field.

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

Windows PowerShell:

```powershell
python scripts\audit_bronze.py --crawl-id <crawl_id>
```

Linux/macOS Bash:

```bash
python scripts/audit_bronze.py --crawl-id <crawl_id>
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

## Google Cloud Setup and Data Lakehouse Structure

### 1. Google Cloud Project

- Project ID: `bigdata-subject`
- Bucket name: `gs://bigdata-subject-real-estate-lakehouse`
- Region: `asia-southeast1`

The Google Cloud project is used for:

```text
Cloud Storage data lake
IAM access control
Pipeline sharing across team members
```

After installing Google Cloud CLI, authenticate and select the project.

If you are connected to a Linux VM via VS Code SSH, use no-browser login flow.

Windows PowerShell:

```powershell
gcloud auth login
gcloud config set project bigdata-subject
```

Linux/macOS Bash:

```bash
gcloud auth login
gcloud config set project bigdata-subject
```

Linux/macOS Bash (VS Code SSH / headless VM):

```bash
gcloud auth login --no-launch-browser
gcloud config set project bigdata-subject
```

When prompted, copy the URL from terminal, open it on your local browser, sign in with an account that has access to `bigdata-subject`, then paste the authorization code back into the VM terminal.

For local development with Google SDK libraries, also run:

Windows PowerShell:

```powershell
gcloud auth application-default login
```

Linux/macOS Bash:

```bash
gcloud auth application-default login
```

Linux/macOS Bash (VS Code SSH / headless VM):

```bash
gcloud auth application-default login --no-launch-browser
```

Check current auth/project on VM:

```bash
gcloud auth list
gcloud config get-value project
gcloud auth application-default print-access-token | head -c 20 && echo "..."
```

Check access:

Windows PowerShell:

```powershell
gcloud projects list
gcloud storage buckets list
gcloud storage ls gs://bigdata-subject-real-estate-lakehouse
```

Linux/macOS Bash:

```bash
gcloud projects list
gcloud storage buckets list
gcloud storage ls gs://bigdata-subject-real-estate-lakehouse
```

If access is denied on VM service account, run user login again and verify active account:

```bash
gcloud auth login --no-launch-browser
gcloud config set account <your_google_account>
gcloud config set project bigdata-subject
gcloud storage ls gs://bigdata-subject-real-estate-lakehouse
```

Upload a small test file:

Windows PowerShell:

```powershell
gcloud storage cp README.md gs://bigdata-subject-real-estate-lakehouse/test/README.md
gcloud storage ls gs://bigdata-subject-real-estate-lakehouse/test/
```

Linux/macOS Bash:

```bash
gcloud storage cp README.md gs://bigdata-subject-real-estate-lakehouse/test/README.md
gcloud storage ls gs://bigdata-subject-real-estate-lakehouse/test/
```

### 2. Lakehouse Data Layout on Cloud Storage

Data is organized by lakehouse layer:

```text
gs://bigdata-subject-real-estate-lakehouse/
  bronze/   # Raw crawl data
  silver/   # Cleaned listing snapshot data
  gold/     # Aggregated analytics tables
```

Google Cloud Storage is object storage. These are object prefixes, not physical folders.

### 3. Download Data from Cloud Storage to Local

Use this when a team member wants to pull shared data from the bucket before running analysis or ETL locally:

Windows PowerShell:

```powershell
gcloud storage rsync --recursive --exclude=".*\.crc$" gs://bigdata-subject-real-estate-lakehouse/bronze data/bronze
gcloud storage rsync --recursive --exclude=".*\.crc$" gs://bigdata-subject-real-estate-lakehouse/silver data/silver
gcloud storage rsync --recursive --exclude=".*\.crc$" gs://bigdata-subject-real-estate-lakehouse/gold data/gold
```

Or run the helper script:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\gcs\sync_from_gcs.ps1
```

Linux/macOS Bash:

```bash
mkdir -p data/bronze data/silver data/gold
gcloud storage rsync --recursive --exclude=".*\.crc$" gs://bigdata-subject-real-estate-lakehouse/bronze data/bronze
gcloud storage rsync --recursive --exclude=".*\.crc$" gs://bigdata-subject-real-estate-lakehouse/silver data/silver
gcloud storage rsync --recursive --exclude=".*\.crc$" gs://bigdata-subject-real-estate-lakehouse/gold data/gold
```

Quick local check after sync:

```bash
find data/bronze -maxdepth 3 -type d | head
find data/silver -maxdepth 3 -type d | head
find data/gold -maxdepth 3 -type d | head
```

If you see `Destination URL must name an existing directory`, create directories first with `mkdir -p data/bronze data/silver data/gold`.

Or run the helper script:

```bash
bash scripts/gcs/sync_from_gcs.sh
```

### 4. Upload Local Data to Cloud Storage

Use this after crawling or running ETL locally:

Windows PowerShell:

```powershell
gcloud storage rsync --recursive --exclude=".*\.crc$" data/bronze gs://bigdata-subject-real-estate-lakehouse/bronze
gcloud storage rsync --recursive --exclude=".*\.crc$" data/silver gs://bigdata-subject-real-estate-lakehouse/silver
gcloud storage rsync --recursive --exclude=".*\.crc$" data/gold gs://bigdata-subject-real-estate-lakehouse/gold
```

Or run the helper script:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\gcs\sync_to_gcs.ps1
```

Linux/macOS Bash:

```bash
gcloud storage rsync --recursive --exclude=".*\.crc$" data/bronze gs://bigdata-subject-real-estate-lakehouse/bronze
gcloud storage rsync --recursive --exclude=".*\.crc$" data/silver gs://bigdata-subject-real-estate-lakehouse/silver
gcloud storage rsync --recursive --exclude=".*\.crc$" data/gold gs://bigdata-subject-real-estate-lakehouse/gold
```

Or run the helper script:

```bash
bash scripts/gcs/sync_to_gcs.sh
```

### 5. Suggested Team Workflow

Before working locally:

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\gcs\sync_from_gcs.ps1
```

Linux/macOS Bash:

```bash
bash scripts/gcs/sync_from_gcs.sh
```

Run the local pipeline:

Windows PowerShell:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m crawler.crawl --config configs\crawl_targets_scale.yaml
.\.venv\Scripts\python.exe -m transform.bronze_to_silver --bronze-dir data\bronze\source=batdongsan\crawl_date=2026-04-25\crawl_id=<crawl_id> --silver-dir data\silver\source=batdongsan\crawl_date=2026-04-25\crawl_id=<crawl_id>
```

Phase 3 Gold should be run on Linux/VM because it uses Spark.

Linux/macOS Bash:

```bash
python3 -m venv .venv
source .venv/bin/activate
export PYTHONPATH=src
python -m crawler.crawl --config configs/crawl_targets_scale.yaml
python -m transform.bronze_to_silver --bronze-dir data/bronze/source=batdongsan/crawl_date=2026-04-25/crawl_id=<crawl_id> --silver-dir data/silver/source=batdongsan/crawl_date=2026-04-25/crawl_id=<crawl_id>
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"
python -m transform.silver_to_gold
python -m validation.check_phase3
```

After producing new data:

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\gcs\sync_to_gcs.ps1
```

Linux/macOS Bash:

```bash
bash scripts/gcs/sync_to_gcs.sh
```

### 6. Service Account Recommendation

For the team/project pipeline, create a service account such as:

```text
real-estate-pipeline-sa
```

Recommended roles:

```text
Storage Object Viewer
Storage Object Creator
```

For easier student project setup, `Storage Object Admin` is also acceptable, but it is broader than necessary.

On a Google Cloud VM, attach the service account to the VM so code can access Cloud Storage without downloading a JSON key file.

### 7. Phase 3 Gold Outputs

Run Phase 3:

Linux/macOS Bash:

```bash
export PYTHONPATH=src
python -m transform.silver_to_gold
python -m validation.check_phase3
```

Phase 3 is Spark-based. Prefer running this step on Linux/VM instead of Windows.

Gold outputs:

```text
data/gold/phase3_summary.json
data/gold/gold_current_listings/
data/gold/gold_listing_snapshots/
data/gold/gold_market_by_district_daily/
data/gold/gold_market_by_property_type_daily/
data/gold/gold_data_quality_daily/
data/gold/gold_removed_listings/
```

Important Gold fields:

```text
first_seen_date
last_seen_date
active_days
snapshot_status
is_price_changed
previous_price_vnd
current_price_vnd
price_change_vnd
price_change_pct
is_info_changed
changed_fields
```

`snapshot_status` can be:

```text
new             # First time the listing appears in the snapshot data
active          # Listing still exists and no tracked change is detected
changed_price   # price_vnd changed compared with the previous snapshot
changed_info    # non-price listing information changed
removed         # listing existed in the previous snapshot but not in the next one
```

`changed_fields` records which tracked fields changed across snapshots, for example:

```text
price_vnd,area_m2
title_raw,district_norm
```

Tracked fields for info change detection:

```text
price_vnd
area_m2
title_raw
description_raw
district_norm
property_type_group
```

`gold_removed_listings` keeps the last known listing information before the listing disappeared:

```text
dedup_key
snapshot_date
last_seen_before_removed
listing_id
listing_url
title_raw
price_vnd
area_m2
district_norm
property_type_group
snapshot_status
```

If code changes add new Gold columns such as `is_info_changed` or `changed_fields`, regenerate Gold on Linux/VM before validating:

```bash
export PYTHONPATH=src
python -m transform.silver_to_gold
python -m validation.check_phase3
```

`validation.check_phase3` is the official Phase 3 validation checklist. If it prints `PASS: Phase 3 validation checklist`, the Gold layer is ready for report/dashboard use.

The GCS sync scripts use `gcloud storage rsync --exclude=".*\.crc$"` so Spark checksum files are not uploaded or downloaded.

### 8. Phase 4 Dashboard

Phase 4 serves the Gold layer as a local analytics dashboard.

Install dashboard dependencies:

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Linux/macOS Bash:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Run dashboard:

Windows PowerShell:

```powershell
.\.venv\Scripts\streamlit.exe run dashboard\app.py
```

Linux/macOS Bash:

```bash
streamlit run dashboard/app.py
```

Open:

```text
http://localhost:8501
```

Dashboard tabs:

```text
Overview
Data Quality
Market
Listings Explorer
Snapshot Tracking
```

The dashboard reads:

```text
data/gold/phase3_summary.json
data/gold/gold_current_listings/
data/gold/gold_listing_snapshots/
data/gold/gold_market_by_district_daily/
data/gold/gold_market_by_property_type_daily/
data/gold/gold_data_quality_daily/
data/gold/gold_removed_listings/
```

Use dashboard screenshots in the report/demo after running Phase 3 and validating Gold.

### 9. Current Project Flow

```text
Crawl -> Bronze -> Bronze-to-Silver -> Silver-to-Gold -> Dashboard -> Sync to GCS
```

## Design Docs

The guiding design documents are located in:

```text
docs/real_estate_agent_docs/
```
