# 03 - Stage 2 DWH Star Schema

## Objective

Stage 2 adds an explicit dimensional warehouse for stable BI analysis while keeping current Gold analytical tables available.

## Modeling Principle

Use dimensional modeling for business-facing serving tables:

```text
business process
  -> grain
  -> dimensions
  -> facts
  -> measures
  -> conformed filters
```

## Business Processes

| Process | Grain | Primary fact candidate |
|---|---|---|
| Listing snapshot observation | One listing from one source on one snapshot date | `fact_listing_snapshot` |
| Listing lifecycle change | One observed change event for one listing snapshot | `fact_listing_change_event` |
| Data quality monitoring | One source and crawl date quality rollup | `fact_data_quality_daily` |
| Market aggregate serving | One date, location, property type aggregate | Existing Gold marts or BI aggregate views |

## Bus Matrix

| Business process | Date | Location | Property type | Source | Listing | Project | Quality status |
|---|---|---|---|---|---|---|---|
| Listing snapshot | X | X | X | X | X | Optional | X |
| Listing change event | X | X | X | X | X | Optional | X |
| Data quality daily | X | Optional | Optional | X |  |  | X |
| Market analytics | X | X | X | X |  | Optional | X |

## Warehouse Output Namespace

Use a distinct output namespace so DWH contracts do not break current Gold marts.

Recommended local layout:

```text
data/warehouse/
  dim_date/
  dim_location/
  dim_property_type/
  dim_source/
  dim_listing/
  fact_listing_snapshot/
  fact_listing_change_event/
  fact_data_quality_daily/
```

Recommended BigQuery dataset split:

```text
real_estate_wh.dim_*
real_estate_wh.fact_*
real_estate_serving.vw_*
```

## Core Dimensions

### `dim_date`

Grain:

```text
one calendar date
```

Required columns:

```text
date_key
date_value
day_of_month
day_of_week
week_of_year
month
month_name
quarter
year
is_weekend
```

Key rule:

```text
date_key = YYYYMMDD integer
```

### `dim_source`

Grain:

```text
one normalized source
```

Required columns:

```text
source_key
source_code
source_name
source_domain
source_type
is_active
first_onboarded_at
```

Starter source codes:

```text
batdongsan
alonhadat
nhatot
```

### `dim_location`

Grain:

```text
one conformed location member at the best trusted geographic level available
```

Required columns:

```text
location_key
country_code
country_name
city_code
city_name
district_code
district_name
ward_code
ward_name
location_level
location_confidence
location_match_method
is_reference_matched
```

Rules:

1. Do not fabricate exact ward or street when the source only supports district.
2. Reference data should control canonical location labels.
3. Unknown location must map to an explicit unknown member, not null foreign keys in published facts.

### `dim_property_type`

Grain:

```text
one conformed real estate property type
```

Required columns:

```text
property_type_key
business_type
property_type_group
property_type_code
property_type_label
is_residential
is_land
is_commercial
```

### `dim_listing`

Grain:

```text
one source listing identity
```

Required columns:

```text
listing_key
source_key
source_listing_id
source_listing_url
dedup_key
first_seen_date_key
last_seen_date_key
listing_identity_method
```

Rule:

```text
`dim_listing` represents source listing identity. Cross-source entity resolution may attach a separate property candidate id later, but must not erase source identity.
```

## Core Facts

### `fact_listing_snapshot`

Grain:

```text
one source listing observed on one snapshot date after daily dedup
```

Required foreign keys:

```text
snapshot_date_key
source_key
listing_key
location_key
property_type_key
```

Required measures and attributes:

```text
price_vnd
area_m2
unit_price_vnd_m2
bedroom_count
bathroom_count
frontage_width_m
quality_score
snapshot_status
is_new_listing
is_active_listing
is_removed_listing
is_price_changed
is_info_changed
price_change_vnd
price_change_pct
has_legal_info
has_car_access
is_price_negotiable
```

Additive measure rules:

| Measure | Additivity |
|---|---|
| listing row count | Additive over dimensions at one snapshot grain |
| price and unit price | Not additive; aggregate with median, avg, percentile |
| flags | Aggregate by count or rate |

### `fact_listing_change_event`

Grain:

```text
one change event detected for one source listing at one snapshot date
```

Required columns:

```text
event_key
snapshot_date_key
source_key
listing_key
location_key
property_type_key
event_type
changed_fields
previous_price_vnd
current_price_vnd
price_change_vnd
price_change_pct
```

Event types:

```text
new
price_changed
info_changed
removed
reactivated
```

`reactivated` is optional until the lifecycle logic supports it.

### `fact_data_quality_daily`

Grain:

```text
one source and crawl date quality rollup
```

Required columns:

```text
crawl_date_key
source_key
total_records
parse_success_count
parse_success_rate
duplicate_record_count
duplicate_rate
missing_price_count
missing_price_rate
missing_area_count
missing_area_rate
missing_location_count
missing_location_rate
quarantine_count
publish_blocked_flag
```

## Surrogate Keys

Production DWH tables use stable surrogate keys:

| Table | Key type |
|---|---|
| `dim_date` | Deterministic integer date key |
| `dim_source` | Small integer or deterministic mapping |
| `dim_location` | Managed surrogate key from canonical location member |
| `dim_property_type` | Managed surrogate key from conformed type member |
| `dim_listing` | Managed surrogate key from source identity |

The existing `dedup_key` remains a business identity aid. It does not replace all dimensional surrogate keys.

## Slowly Changing Dimensions

Recommended initial policy:

| Dimension | SCD policy |
|---|---|
| Date | Static |
| Source | Type 1 |
| Location | Type 1 for label correction, Type 2 only if administrative history is required |
| Property type | Type 1 |
| Listing | Snapshot facts carry volatile listing attributes; keep listing identity dimension narrow |

## Source to Warehouse Mapping

Warehouse facts must come from validated Silver or validated Gold snapshot outputs.

Recommended mapping path:

```text
Silver normalized listing rows
  -> daily dedup and lifecycle
  -> current Gold analytical marts
  -> warehouse dimension lookup
  -> warehouse fact write
```

## Required Validation

```text
[ ] Fact grain is unique by snapshot_date_key, source_key, listing_key.
[ ] Foreign keys resolve to dimensions or explicit unknown members.
[ ] Fact record count reconciles to validated daily-dedup snapshot output.
[ ] Price and area measures preserve null and negotiable semantics.
[ ] Dimensions have no duplicate business members.
[ ] Warehouse outputs are partitioned or clustered for date and source access patterns.
[ ] BigQuery serving views use stable documented columns.
```

## Stage 2 Exit Gate

Stage 2 is complete when this statement is true:

```text
The system exposes documented warehouse facts and conformed dimensions that can be used directly by Power BI without reverse-engineering raw Gold snapshot columns.
```

