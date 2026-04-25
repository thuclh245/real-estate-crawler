# 09 - Spark Batch ETL Jobs

## Purpose

Use Spark batch jobs to transform Bronze -> Silver -> Gold.

## Why Spark

Spark is the core processing engine because the project requires:

- reading many files
- schema-based transformations
- deduplication
- aggregations
- joins with reference tables
- rerun by crawl_date
- scaling beyond local Pandas when data grows

## Job 1 - `bronze_to_silver.py`

Input:

```text
data/bronze/source=*/crawl_date=*/metadata/
data/bronze/source=*/crawl_date=*/raw_html/
data/bronze/source=*/crawl_date=*/raw_text/
```

Output:

```text
data/silver/silver_listing_snapshot/crawl_date=YYYY-MM-DD/
```

Tasks:

```text
read metadata JSON
join/load raw_text if needed
parse title/description
parse price
parse area
parse location
normalize property type
extract property features
add missing flags
add quality_score
write Parquet
```

## Job 2 - `silver_dedup.py`

Input:

```text
data/silver/silver_listing_snapshot/
```

Output:

```text
data/silver/silver_listing_snapshot_dedup/
```

Tasks:

```text
create normalized_url
create content_hash
dedup listing_id within same day
dedup URL
mark duplicate flags
keep best record
```

## Job 3 - `silver_to_gold_current.py`

Output:

```text
data/gold/gold_listing_current/
```

Tasks:

```text
latest snapshot per listing
first_seen_at
last_seen_at
is_active
days_observed
```

## Job 4 - `silver_to_gold_snapshot_fact.py`

Output:

```text
data/gold/gold_listing_snapshot_fact/
```

Tasks:

```text
is_new_listing
price_changed_flag
content_changed_flag
is_removed_listing
```

## Job 5 - `gold_aggregations.py`

Outputs:

```text
data/gold/gold_market_district_daily/
data/gold/gold_data_quality_daily/
```

Tasks:

```text
aggregate listing count
aggregate active/new/removed/price_changed
compute median/avg price and unit price
compute missing rates
compute processing_time_seconds
compute storage_size_by_layer if possible
```

## CLI pattern

Each ETL job should support:

```bash
python etl/bronze_to_silver.py --crawl-date 2026-04-25
python etl/gold_aggregations.py --snapshot-date 2026-04-25
```

## Acceptance tests

```text
[ ] Each job can run independently.
[ ] Each job accepts crawl_date/snapshot_date.
[ ] Each output is partitioned by date if appropriate.
[ ] Each job logs processing_time_seconds.
[ ] Pipeline can rerun one date without recrawling.
```
