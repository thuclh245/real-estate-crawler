# 08 - Gold Tables Contract

## Purpose

Gold stores curated data for dashboard, reports and optional ML.

## Gold table 1: `gold_listing_current`

One latest row per listing.

Required columns:

```text
listing_id
source
listing_url
title
latest_price_value_vnd
price_raw
price_type
area_m2
unit_price_vnd_m2
city
district
ward_old
ward_new
street
project_name
property_type
bedrooms
bathrooms
floors
frontage_m
entrance_width_m
legal_status
furniture_status
image_count
first_seen_at
last_seen_at
is_active
days_observed
quality_score
is_valid_for_price_analysis
is_valid_for_ml
```

## Gold table 2: `gold_listing_snapshot_fact`

Historical snapshot fact.

Required columns:

```text
snapshot_date
source
listing_id
price_value_vnd
area_m2
unit_price_vnd_m2
city
district
ward_old
ward_new
property_type
content_hash
is_seen
is_new_listing
price_changed_flag
content_changed_flag
is_removed_listing
quality_score
```

## Gold table 3: `gold_market_district_daily`

Aggregated by date + district + property type.

Required columns:

```text
snapshot_date
city
district
property_type
listing_count
active_listing_count
new_listing_count
removed_listing_count
price_changed_count
median_price_value_vnd
avg_price_value_vnd
median_unit_price_vnd_m2
avg_unit_price_vnd_m2
median_area_m2
avg_area_m2
valid_price_count
valid_area_count
```

## Gold table 4: `gold_data_quality_daily`

Pipeline and data quality metrics.

Required columns:

```text
crawl_date
source
crawl_category
crawl_city
crawl_district
total_urls
total_records
successful_crawls
failed_crawls
crawl_success_rate
parse_success_rate
duplicate_rate
missing_price_rate
missing_area_rate
missing_location_rate
valid_price_records
valid_location_records
processing_time_seconds
bronze_size_mb
silver_size_mb
gold_size_mb
```

## Acceptance tests

```text
[ ] All 4 Gold tables exist.
[ ] Gold tables are generated from Silver, not directly from Bronze raw HTML.
[ ] Dashboard can read Gold tables.
[ ] Data quality metrics are populated.
[ ] Records can be traced back to crawl_id/source.
```
