# 13 - Agent Task Prompts

Use these prompts with a code agent. Replace variables in brackets.

## Prompt 1 - Fix Phase 1 Crawler Hardening

```text
You are working in my real-estate-crawler project. Read docs/00_PROJECT_CONTEXT.md, docs/02_PHASE1_CRAWLER_BRONZE.md, docs/03_PHASE1_CRAWLER_IMPLEMENTATION_TASKS.md, and docs/05_BRONZE_CONTRACT.md.

Task:
- Make crawl_id unique using batdongsan_YYYYMMDD_HHMMSS.
- Name crawl log and summary by crawl_id.
- Ensure each successful listing writes raw_html, raw_text if available, metadata JSON, and crawl_log record.
- Ensure summary metrics count only files/URLs written in the current run.
- Do not change Phase 3 parser logic.

Acceptance:
- Run crawler twice and verify two different crawl_id summaries.
- raw_html_file_count == success_count.
- metadata_file_count == success_count.
- duplicate_url_count is computed.
```

## Prompt 2 - Clean Parser for Phase 1

```text
Read docs/06_SILVER_PARSER_CONTRACT.md and current src/parser.py.

Task:
- Remove duplicate extract_basic_fields functions.
- Keep Phase 1 parser minimal: html_to_text and extract_listing_id only.
- Do not implement full price/location parser yet.

Acceptance:
- parser.py has no duplicate function names.
- crawler still runs and produces raw_text.
```

## Prompt 3 - Implement Silver Parser

```text
Read docs/06_SILVER_PARSER_CONTRACT.md.

Task:
Implement bronze_to_silver parser functions and Spark job to create silver_listing_snapshot.

Must parse:
- title
- description
- price_raw, price_value_vnd, price_type
- area_raw, area_m2
- breadcrumb/address/location with location_confidence
- bedrooms, bathrooms, floors, frontage, entrance_width, legal_status, furniture_status
- data quality flags

Acceptance:
- Output is Parquet under data/silver/silver_listing_snapshot/crawl_date=YYYY-MM-DD/.
- Missing values are flagged, not blindly filled.
```

## Prompt 4 - Implement Snapshot and Dedup

```text
Read docs/07_SNAPSHOT_DEDUP_CONTRACT.md.

Task:
Implement silver_dedup and lifecycle tracking.

Acceptance:
- Duplicate listing_id within same date detected.
- first_seen_at, last_seen_at, is_active computed.
- price_changed_flag computed.
```

## Prompt 5 - Implement Gold Tables

```text
Read docs/08_GOLD_TABLE_CONTRACT.md and docs/09_SPARK_ETL_JOBS.md.

Task:
Generate 4 Gold tables:
- gold_listing_current
- gold_listing_snapshot_fact
- gold_market_district_daily
- gold_data_quality_daily

Acceptance:
- All tables exist in data/gold/.
- Dashboard can read them.
```

## Prompt 6 - Build Streamlit Dashboard

```text
Read docs/10_DASHBOARD_SPEC.md.

Task:
Create Streamlit dashboard with 4 tabs: Data Quality, Market Overview, Hanoi District Analysis, Trend/Snapshot.

Acceptance:
- streamlit run dashboard/app.py works.
- Dashboard reads Gold tables.
```
