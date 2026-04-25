# 10 - Dashboard Specification

## Tool recommendation

Use Streamlit for prototype.

## Data source

Dashboard must read Gold tables, not Bronze.

```text
data/gold/gold_listing_current/
data/gold/gold_listing_snapshot_fact/
data/gold/gold_market_district_daily/
data/gold/gold_data_quality_daily/
```

## Tab 1 - Data Quality

Metrics:

```text
total_records
crawl_success_rate
parse_success_rate
duplicate_rate
missing_price_rate
missing_area_rate
missing_location_rate
processing_time_seconds
```

Charts:

```text
records_per_day line chart
missing rate by field bar chart
duplicate rate by source/category
crawl errors table
```

## Tab 2 - Market Overview

Metrics:

```text
total_active_listings
median_price
median_unit_price_vnd_m2
top_property_type
top_district
```

Charts:

```text
listing count by property_type
listing count by city/district
price distribution
area distribution
```

## Tab 3 - Hanoi District Analysis

Metrics:

```text
listing_count_by_district
median_unit_price_by_district
median_area_by_district
valid_price_count_by_district
```

Charts:

```text
bar: listing count by district
bar: median unit price by district
stacked bar: property_type by district
table: clean top listings
```

## Tab 4 - Trend / Snapshot

Metrics:

```text
new_listing_count
removed_listing_count
price_changed_count
active_listing_count
```

Charts:

```text
line: active listings by day
line: new listings by day
line: price changes by day
line: median unit price by day/district
```

## Filters

```text
date range
city
district
property_type
price range
area range
source
```

## Acceptance tests

```text
[ ] App starts with `streamlit run dashboard/app.py`.
[ ] Dashboard reads Gold.
[ ] Data Quality tab works.
[ ] Market Overview tab works.
[ ] Hanoi District Analysis tab works.
[ ] Trend tab works.
[ ] Filters apply to charts.
```
