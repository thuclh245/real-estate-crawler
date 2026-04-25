# 14 - Acceptance Checklists

## Phase 1 - Crawler + Bronze

```text
[ ] fetch_mode is configurable.
[ ] crawl4ai mode works.
[ ] stop_on_block works.
[ ] crawl_id is unique per run.
[ ] list pages are requested.
[ ] listing URLs are extracted.
[ ] detail pages are crawled.
[ ] raw_html saved.
[ ] raw_text saved if available.
[ ] metadata saved per listing.
[ ] crawl_log saved per crawl_id.
[ ] crawl_summary saved per crawl_id.
[ ] duplicate_url_count computed.
[ ] avg_html_size computed for current run.
[ ] raw_html_file_count equals success_count.
[ ] metadata_file_count equals success_count.
```

## Bronze

```text
[ ] Partition by source.
[ ] Partition by crawl_date.
[ ] Raw data not overwritten.
[ ] Raw path exists for each successful listing.
[ ] Metadata can trace listing back to crawl_id and source.
[ ] Parser can re-run from Bronze.
```

## Silver

```text
[ ] Unified schema exists.
[ ] price_value_vnd parsed when possible.
[ ] area_m2 parsed when possible.
[ ] location parsed or fallback from crawl_context.
[ ] missing_price_flag exists.
[ ] missing_area_flag exists.
[ ] missing_location_flag exists.
[ ] quality_score exists.
[ ] parser_version exists.
```

## Snapshot & Dedup

```text
[ ] Dedup by listing_id.
[ ] Dedup by normalized_url.
[ ] content_hash exists.
[ ] new listing detected.
[ ] price change detected.
[ ] removed/expired listing detected.
[ ] first_seen_at exists.
[ ] last_seen_at exists.
[ ] is_active exists.
```

## Gold

```text
[ ] gold_listing_current exists.
[ ] gold_listing_snapshot_fact exists.
[ ] gold_market_district_daily exists.
[ ] gold_data_quality_daily exists.
[ ] Gold generated from Silver.
```

## Spark ETL

```text
[ ] bronze_to_silver job runs.
[ ] silver_dedup job runs.
[ ] silver_to_gold_current job runs.
[ ] silver_to_gold_snapshot_fact job runs.
[ ] gold_aggregations job runs.
[ ] Jobs accept date parameter.
[ ] processing_time logged.
[ ] Output can be rerun by date.
```

## Dashboard

```text
[ ] Data Quality tab.
[ ] Market Overview tab.
[ ] Hanoi District Analysis tab.
[ ] Trend/Snapshot tab.
[ ] Filters: date, district, property_type, source.
```

## ML baseline

```text
[ ] Clean dataset generated from Gold.
[ ] Target is unit_price_vnd_m2.
[ ] Baseline model trained.
[ ] MAE/RMSE/R2 reported.
[ ] Feature importance or coefficients shown.
[ ] Limitations explained.
```
