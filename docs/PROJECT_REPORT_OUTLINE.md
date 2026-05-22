# Project Report Outline

Target length: 10 pages.

## 1. Giới thiệu (1 page)

- Problem: real estate listings are semi-structured and change daily.
- Goal: build a lakehouse pipeline from crawl to dashboard.
- Scope: Batdongsan source, Bronze/Silver/Gold layers, Streamlit dashboard, GCS backup.

Suggested figure: high-level pipeline diagram from `docs/architecture/pipeline_architecture.md`.

## 2. Kiến trúc hệ thống (1.5 pages)

- Explain Crawl → Bronze → Silver → Gold → Dashboard → GCS.
- Mention technologies: Crawl4AI, Python, PySpark, Streamlit, Google Cloud Storage.
- Explain why each layer exists and what contract it owns.

Suggested figure: Mermaid architecture diagram.

## 3. Thiết kế dữ liệu (1.5 pages)

- Bronze partitioning and raw artifact contract.
- Silver normalized listing schema and enrichment fields.
- Gold lifecycle and market analytics tables.

Suggested tables:

- `docs/schema/bronze_schema.md`
- `docs/schema/silver_schema.md`
- `docs/schema/gold_schema.md`

## 4. Pipeline xử lý (1.5 pages)

- Crawl configuration strategy and daily target volume.
- Bronze-to-Silver parsing and quality flags.
- Silver-to-Gold deduplication, lifecycle tracking, and aggregate generation.
- Validation and GCS sync.

Suggested evidence: latest `daily_run_summary.json`.

## 5. Kết quả và Dashboard (1.5 pages)

- Overview tab: total listings, records, duplicate rate, parse success.
- Data Quality tab: quality trends.
- Pipeline Health tab: daily run history and observability metrics.
- Listings Explorer: filtering by enriched features.
- Snapshot Tracking: changed and removed listings.

Suggested screenshots:

- `docs/screenshots/overview_{date}.png`
- `docs/screenshots/pipeline_health_{date}.png`
- `docs/screenshots/listings_explorer_{date}.png`

## 6. Data Quality và Observability (1 page)

- Daily Run Summary schema.
- Data Quality Report markdown/json.
- Rolling baseline comparison and tolerance-based classification.
- Handling failed runs and corrupted summary files.

Suggested table: latest quality report metrics.

## 7. Kết luận và hướng phát triển (1 page)

- Summarize achieved pipeline layers.
- Discuss limitations: source website changes, parser coverage, VM/Spark runtime.
- Future work: more sources, ML price model, alerting, scheduled dashboard screenshots.

## Required Figures and Tables

| Item | Path |
|---|---|
| Pipeline architecture | `docs/architecture/pipeline_architecture.md` |
| Bronze schema | `docs/schema/bronze_schema.md` |
| Silver schema | `docs/schema/silver_schema.md` |
| Gold schema | `docs/schema/gold_schema.md` |
| Dashboard screenshots | `docs/screenshots/` |
| Pipeline summary | `data/logs/daily_pipeline/run_date=*/daily_run_summary.json` |
| Data quality report | `data/reports/data_quality_report_YYYY-MM-DD.md` |
