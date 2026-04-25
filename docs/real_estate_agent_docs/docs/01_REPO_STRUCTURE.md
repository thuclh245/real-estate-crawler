# 01 - Recommended Repository Structure

## Target repository

```text
real-estate-crawler/
  configs/
    crawl_targets.yaml

  src/
    crawl.py
    fetcher.py
    url_builder.py
    parser.py
    storage.py
    logger.py
    utils.py

  etl/
    bronze_to_silver.py
    silver_dedup.py
    silver_to_gold_current.py
    silver_to_gold_snapshot_fact.py
    gold_aggregations.py

  dashboard/
    app.py
    pages/
      1_Data_Quality.py
      2_Market_Overview.py
      3_Hanoi_District_Analysis.py
      4_Trend_Snapshot.py

  notebooks/
    01_eda_bronze.ipynb
    02_silver_quality_check.ipynb
    03_ml_baseline.ipynb

  docs/
    ... documentation pack ...

  data/
    bronze/
    silver/
    gold/

  logs/
  requirements.txt
  README.md
```

## Module responsibilities

### `src/crawl.py`

Main crawler orchestration:

- read config
- generate seed URLs
- crawl list pages
- extract listing URLs
- crawl detail pages
- save raw HTML/text/metadata
- write crawl log and summary

### `src/fetcher.py`

Fetch adapter layer:

- `fetch_mode: requests`
- `fetch_mode: crawl4ai`
- return common `FetchResult`

### `src/url_builder.py`

Build list page URLs from category + district + page number. Should support `seed_url` override from config.

### `src/parser.py`

Phase 1: keep minimal.

- `html_to_text()`
- `extract_listing_id()` if needed

Phase 3: add proper parse functions.

### `src/storage.py`

Save/read local files:

- raw HTML
- raw text
- metadata JSON
- JSONL logs

### `etl/`

Spark batch jobs. Each file should be independently runnable and rerunnable by `crawl_date`.

### `dashboard/`

Streamlit dashboard reading Gold tables.

## File naming rules

Use deterministic names:

```text
listing_id=<id>.html
listing_id=<id>.txt
listing_id=<id>.json
crawl_log_<crawl_id>.jsonl
crawl_summary_<crawl_id>.json
```

Never use only `crawl_date` for logs/summaries if multiple runs per day are possible.

## Important convention

`crawl_id` must be unique per run:

```text
batdongsan_YYYYMMDD_HHMMSS
```
