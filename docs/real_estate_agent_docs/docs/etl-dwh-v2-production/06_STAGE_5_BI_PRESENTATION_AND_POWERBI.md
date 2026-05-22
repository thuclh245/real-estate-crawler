# 06 - Stage 5 BI Presentation and Power BI

## Objective

Stage 5 adds a business BI presentation layer without deleting the current Streamlit engineering dashboard.

## Role Split

| Surface | Primary audience | Primary purpose |
|---|---|---|
| Power BI | Business reviewers, report readers, market analysts | Market analytics and DWH-facing reporting |
| Streamlit | Engineers, project operators, data QA reviewers | Pipeline health, quality inspection, run diagnostics, listing exploration |

## Data Source Policy

### Development

Power BI drafts may use exported CSV or Parquet copies from validated local outputs.

### Production

Published Power BI reports should read stable serving tables or views:

```text
BigQuery warehouse dimensions
BigQuery warehouse facts
BigQuery serving views
```

Power BI must not depend on Spark CSV samples that are truncated for quick inspection.

## Recommended BI Model

```text
dim_date                1 -> many  fact_listing_snapshot
dim_source              1 -> many  fact_listing_snapshot
dim_location            1 -> many  fact_listing_snapshot
dim_property_type       1 -> many  fact_listing_snapshot
dim_listing             1 -> many  fact_listing_snapshot

dim_date                1 -> many  fact_listing_change_event
dim_source              1 -> many  fact_data_quality_daily
```

## Power BI Report Pages

### Page 1 - Executive Overview

Purpose:

```text
Give a trusted market and pipeline headline view.
```

Required KPI cards:

```text
current listing count
snapshot listing count
median listing price
median unit price per m2
new listing count
removed listing count
price changed count
latest data freshness date
```

Required visuals:

```text
listing count trend
listing distribution by property type
top districts by listing count
top districts by median unit price
```

### Page 2 - Market Analytics

Required visuals:

```text
district by property type matrix
median unit price by district
median area by property type
price distribution
unit price trend by selected district
```

Required filters:

```text
date range
district
property type
source
business type
```

### Page 3 - Listing Lifecycle

Required visuals:

```text
new vs active vs changed vs removed by date
price change count trend
price change amount distribution
changed listing detail table
removed listing detail table
```

### Page 4 - Data Quality

Required visuals:

```text
parse success rate by date and source
missing price rate
missing area rate
missing location rate
duplicate rate
quarantine count
publish blocked flag
```

### Page 5 - Source Comparison

This page becomes available after Stage 3.

Required visuals:

```text
record volume by source
quality scorecard by source
missing and duplicate rate comparison
listing price distribution by source
source coverage by district and property type
```

## Measures

Power BI measures should prefer DAX over repeated calculated columns for reusable metrics.

Minimum measure catalog:

```text
Listing Count
Active Listing Count
New Listing Count
Removed Listing Count
Price Changed Count
Median Price VND
Median Unit Price VND Per M2
Median Area M2
Parse Success Rate
Duplicate Rate
Missing Price Rate
Missing Area Rate
Data Freshness Days
```

## Serving Views

Recommended serving views:

```text
vw_listing_snapshot_bi
vw_listing_change_event_bi
vw_market_district_daily_bi
vw_data_quality_daily_bi
vw_source_scorecard_bi
```

Serving views may flatten common dimension labels for Power BI convenience while warehouse facts and dimensions remain authoritative.

## Refresh Rules

```text
report refresh occurs only after published serving tables are updated
freshness marker is visible in the report
failed pipeline runs do not silently refresh business reports with partial data
```

## Power BI Export Path for Early Implementation

If BigQuery serving is not ready yet, use a controlled export path:

```text
data/powerbi/
  dim_date.csv
  dim_source.csv
  dim_location.csv
  dim_property_type.csv
  dim_listing.csv
  fact_listing_snapshot.csv
  fact_listing_change_event.csv
  fact_data_quality_daily.csv
```

The export must come from validated warehouse outputs and must include a data freshness note.

## Streamlit Changes in V2

Keep Streamlit useful for operations:

```text
Pipeline Health
Data Quality
Run history
Source scorecards
Validation status
Quarantine summaries
Listings Explorer
Snapshot inspection
```

Do not force Streamlit to become the only BI report when Power BI is available.

## Stage 5 Acceptance

```text
[ ] Power BI model uses stable warehouse/serving data.
[ ] Report pages separate business analytics from technical run diagnostics.
[ ] Date, district, property type, and source filters work.
[ ] Data freshness is visible.
[ ] Quality page explains quality rates and blocked publication.
[ ] Streamlit still works for technical inspection.
```

## Stage 5 Exit Gate

Stage 5 is complete when this statement is true:

```text
Business analytics are available through a governed Power BI model while engineering diagnostics remain observable through Streamlit and run artifacts.
```

