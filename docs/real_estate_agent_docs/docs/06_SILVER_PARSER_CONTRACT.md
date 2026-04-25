# 06 - Silver Parser and Schema Contract

## Purpose

Silver converts raw Bronze files into a standardized listing snapshot table. It preserves raw fields and adds normalized fields + quality flags.

## Main table

```text
silver_listing_snapshot
```

## Input

```text
data/bronze/source=*/crawl_date=*/raw_html/
data/bronze/source=*/crawl_date=*/raw_text/
data/bronze/source=*/crawl_date=*/metadata/
```

## Output

```text
data/silver/silver_listing_snapshot/crawl_date=YYYY-MM-DD/
```

Format: Parquet preferred.

## Required column groups

### Crawl metadata

```text
crawl_id
source
crawl_date
snapshot_date
scraped_at
parser_version
listing_id
listing_url
crawl_category
crawl_city
crawl_district
property_type_group
```

### Listing content

```text
title
description
content_hash
image_count
has_image
image_urls_raw
```

### Time fields

```text
posted_date
expired_date
```

### Location fields

```text
province
city
district
ward_old
ward_new
street
project_name
full_address
breadcrumb
location_level
location_parse_method
location_confidence
missing_location_flag
```

### Price fields

```text
price_raw
price_value_vnd
price_type
currency
unit_price_raw
unit_price_vnd_m2
market_min_unit_price_vnd_m2
market_common_unit_price_vnd_m2
market_max_unit_price_vnd_m2
description_price_raw
description_price_value_vnd
price_confidence
missing_price_flag
ambiguous_price_flag
```

### Area fields

```text
area_raw
area_m2
missing_area_flag
```

### Property features

```text
property_type
bedrooms
bathrooms
toilets
floors
frontage_m
entrance_width_m
house_direction
balcony_direction
legal_status
furniture_status
amenities
```

### Seller metadata

```text
seller_type
seller_years_on_platform
seller_active_listing_count
has_broker_certificate
phone_masked
```

Do not store real phone number.

### Data quality fields

```text
is_valid_record
is_valid_for_count_analysis
is_valid_for_price_analysis
is_valid_for_unit_price_analysis
is_valid_for_ml
duplicate_flag
quality_score
quality_errors
```

## Location parse priority

```text
1. Detail address
2. Breadcrumb
3. URL slug
4. Crawl context
5. Title
6. Description
```

## Location confidence

```text
high: address/breadcrumb clearly has city + district + ward
medium: district from crawl_context or URL; street/title inference
low: weak inference from title/description
unknown: cannot determine
```

## Price type values

```text
fixed_total_price
unit_price
negotiable
range_price
hidden_in_description
unknown
```

## Missing value handling

Never fill missing values blindly.

For missing price:

```text
price_value_vnd = null
missing_price_flag = true
is_valid_for_price_analysis = false
is_valid_for_count_analysis = true
```

For missing area:

```text
area_m2 = null
missing_area_flag = true
is_valid_for_unit_price_analysis = false
```

For missing location:

```text
district = null
missing_location_flag = true
location_confidence = unknown
is_valid_for_district_analysis = false
```

## Acceptance tests

```text
[ ] Silver reads from Bronze, not CSV.
[ ] Raw fields are preserved where useful.
[ ] price_value_vnd parses common values: tỷ, triệu, thỏa thuận.
[ ] area_m2 parses m² and m2.
[ ] district can fallback from crawl_context.
[ ] missing flags are set.
[ ] quality_score exists.
[ ] parser_version exists.
```
