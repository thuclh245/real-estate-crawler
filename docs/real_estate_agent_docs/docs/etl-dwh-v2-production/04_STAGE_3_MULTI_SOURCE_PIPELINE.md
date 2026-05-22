# 04 - Stage 3 Multi-Source Pipeline

## Objective

Stage 3 promotes multi-source support from experiments to production ingestion.

The current production pipeline is Batdongsan-centered. Existing Alonhadat and Nhatot scripts and test artifacts are useful discovery inputs, but they are not production onboarding by themselves.

## Source Strategy

| Source | V2 role |
|---|---|
| Batdongsan | Baseline production source |
| Alonhadat | Candidate second production source |
| Nhatot | Candidate production source after contract fit and legal/operational review |

## Design Rule

Source-specific behavior belongs behind adapters and parsers. Shared downstream logic consumes normalized contracts.

```text
source-specific fetch, URL, card parsing, and detail parsing
  -> source adapter output
  -> shared Bronze contract
  -> source parser mapping
  -> shared Silver listing contract
```

## Recommended Package Structure

```text
src/crawler/sources/
  base.py
  batdongsan/
    adapter.py
    parser.py
    url_builder.py
  alonhadat/
    adapter.py
    parser.py
    url_builder.py
  nhatot/
    adapter.py
    parser.py
    url_builder.py
```

## Adapter Contract

### Required Adapter Responsibilities

Each source adapter must:

1. Read a source-specific crawl config.
2. Build or validate listing page URLs.
3. Fetch listing pages and detail pages using approved fetch modes.
4. Detect blocked, failed, redirected, or unusable responses.
5. Persist Bronze raw artifacts.
6. Emit crawl audit and run summary fields in a shared shape.
7. Preserve enough source metadata for parser reprocessing.

### Required Adapter Interface

Conceptual interface:

```text
SourceAdapter
  source_code
  load_targets(config)
  build_seed_url(target, page_number)
  fetch_listing_page(url, context)
  extract_listing_entries(page_artifact, context)
  fetch_detail_page(listing_entry, context)
  write_bronze_artifacts(detail_artifact, context)
  summarize_run(context)
```

## Bronze Contract

Bronze remains source-specific raw evidence with shared partitioning:

```text
data/bronze/source=<source_code>/crawl_date=YYYY-MM-DD/crawl_id=<crawl_id>/
  raw_html/
  raw_text/
  raw_json/
  metadata/
  crawl_log/
```

Minimum Bronze metadata fields:

```text
source_code
source_domain
crawl_id
crawl_date
scraped_at
source_listing_id
listing_url
final_detail_url
http_status
fetch_mode
crawl_status
raw_html_path
raw_text_path
raw_json_path
metadata_path
source_target_key
source_category_raw
source_location_context
parser_version
crawler_version
retry_count
error_message
```

## Silver Conformed Listing Contract

Every promoted source must map to a shared Silver schema.

### Required Identity Columns

```text
source
source_code
crawl_date
crawl_id
listing_id
listing_url
dedup_key
dedup_method
processed_at
parser_version
```

### Required Business Columns

```text
title_raw
description_raw
price_raw
price_vnd
price_unit
area_m2
unit_price_vnd_m2
business_type
property_type_group
city_norm
district_norm
ward_norm
project_name
bedroom_count
bathroom_count
```

### Required Quality Columns

```text
parse_status
parse_error_message
is_missing_price
is_missing_area
is_missing_location
is_invalid_price
is_invalid_area
is_outlier_price
is_outlier_area
location_confidence
```

Sources may add extra raw-derived fields, but DWH and BI must depend on the conformed set.

## Source Conformance Rules

### Price

Normalize source wording into:

```text
price_vnd
price_unit
is_price_negotiable
```

Do not convert negotiable price into zero.

### Area

Normalize usable property area into `area_m2`. Preserve raw source text if source exposes multiple area meanings.

### Property Type

Map source categories into conformed property groups before warehouse output:

```text
apartment
house
land
villa_townhouse
commercial
other
unknown
```

### Location

Use canonical reference location labels when available. Preserve source location text and confidence.

## Cross-Source Dedup

V2 must distinguish two concepts:

| Concept | Meaning |
|---|---|
| Source listing identity | One listing URL or listing id within one source |
| Cross-source property candidate | Possible same real-world property exposed on different sources |

### Required Initial Policy

1. Dedup source snapshots first within each source.
2. Do not merge cross-source records into one listing without confidence evidence.
3. Generate an optional cross-source candidate table for review or analytics.

Candidate matching signals may include:

```text
normalized title tokens
price and area proximity
district and property type
project or building name
bedroom count
phone or seller signals when legally and technically available
```

Suggested output:

```text
data/gold/cross_source_listing_candidates/
```

## Source Scorecard

Each source must publish scorecard metrics:

```text
listing_pages_requested
detail_pages_requested
success_count
failed_count
blocked_count
http_403_count
http_429_count
parse_success_rate
missing_price_rate
missing_area_rate
missing_location_rate
duplicate_rate
quarantine_rate
```

## Onboarding Gate for a New Source

```text
[ ] Bronze artifacts retain raw evidence.
[ ] Parser can re-run from Bronze.
[ ] Silver contract maps required identity, business, and quality columns.
[ ] Source scorecard is generated.
[ ] Warehouse facts preserve source_key and listing_key.
[ ] BI filters can separate source behavior.
[ ] Source-specific failure patterns are documented.
[ ] Legal and access restrictions are respected.
```

## Stage 3 Exit Gate

Stage 3 is complete when this statement is true:

```text
At least one additional source besides Batdongsan reaches validated Bronze, Silver, warehouse, and BI serving outputs with source lineage and quality evidence preserved.
```

