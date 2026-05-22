# Gold Schema

Gold stores analytical tables generated from all Silver snapshots by PySpark.

## Tables

| Table | Field | Type | Description | Computation Logic |
|---|---|---|---|---|
| gold_current_listings | dedup_key | string | Stable listing identity | source + listing_id |
| gold_current_listings | snapshot_date | date string | Latest observed snapshot date | max crawl_date per active listing |
| gold_current_listings | quality_score | numeric | Listing quality score | Derived from parse and quality flags |
| gold_current_listings | snapshot_status | string | Latest lifecycle status | new, active, changed_info, changed_price |
| gold_current_listings | price_change_pct | float | Latest price change percent | price delta / previous price |
| gold_listing_snapshots | dedup_key | string | Stable listing identity | source + listing_id |
| gold_listing_snapshots | snapshot_date | date string | Snapshot date | crawl_date |
| gold_listing_snapshots | duplicate_group_size | int | Duplicate group size in snapshot | window count by dedup key/date |
| gold_listing_snapshots | is_duplicate_in_snapshot | boolean | Duplicate marker | duplicate_group_size > 1 |
| gold_listing_snapshots | changed_fields | string | Fields that changed vs previous snapshot | Comparison across lagged values |
| gold_removed_listings | dedup_key | string | Listing removed from next snapshot | Previous active listing missing in current snapshot |
| gold_removed_listings | snapshot_date | date string | Removal detection date | Next snapshot date |
| gold_market_by_district_daily | crawl_date | date string | Aggregate date | snapshot date |
| gold_market_by_district_daily | district_norm | string | District grouping | normalized district |
| gold_market_by_district_daily | listing_count | int | Listing count | count active listings |
| gold_market_by_district_daily | median_unit_price_vnd_m2 | float | Median unit price | approximate median by district/date |
| gold_market_by_property_type_daily | property_type_group | string | Property group | normalized property type |
| gold_market_by_property_type_daily | listing_count | int | Listing count | count active listings |
| gold_data_quality_daily | parse_success_rate | float | Parse success by date | success records / total records |
| gold_data_quality_daily | duplicate_rate | float | Duplicate rate by date | duplicate records / total records |

## Partitioning

Gold tables are directory-based Spark outputs under:

```text
data/gold/{table_name}/
```

Some exported sample tables may also exist as CSV directories, but the canonical analytical outputs are parquet tables.
